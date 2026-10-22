import asyncio
import io
import json
import threading
from pathlib import Path

import httpx
import pytest
from docx import Document
from pydantic import ValidationError

DIMENSIONS = ["basic_requirements", "professional_skills", "professional_quality", "development_potential"]


def contradictory(raw=(80, 60, 70, 90)):
    return {"overall_score": 99, "overall_score_computed": 99, "match_level": "高度匹配", "dimensions": {
        key: {"raw_score": score, "weight": 99, "weighted_score": 99} for key, score in zip(DIMENSIONS, raw)
    }}


def run(awaitable):
    return asyncio.run(awaitable)


@pytest.mark.parametrize("fenced", [False, True])
def test_clean_json_preserves_strings(modules, fenced):
    expected = {"url": "https://example.com/path//x", "text": "你好，世界！O'Reilly：测试。/*不删除*/ //保留", "escaped": 'say "hi"'}
    text = json.dumps(expected, ensure_ascii=False)
    if fenced:
        text = "```json\n" + text + "\n```"
    assert json.loads(modules["ai_client"].clean_json(text)) == expected


@pytest.mark.parametrize("text, expected", [
    ('解释\n{"url":"https://example.com", // comment\n"label":"保留，标点。",}\n完成', {"url": "https://example.com", "label": "保留，标点。"}),
    ("{'title': '你好，世界。', 'scores': [1,2,],}", {"title": "你好，世界。", "scores": [1, 2]}),
    ('{"score"：85，"text"："你好，世界！"}', {"score": 85, "text": "你好，世界！"}),
    ("{'title': '保留外层', 'scores': [1,2]}", {"title": "保留外层", "scores": [1, 2]}),
])
def test_clean_json_fallback(modules, text, expected):
    assert json.loads(modules["ai_client"].clean_json(text)) == expected


def test_match_uses_raw_scores_and_fixed_weights(modules, monkeypatch):
    match = modules["module3_match"]
    monkeypatch.setattr(match, "get_profile", lambda _: None)
    monkeypatch.setattr(match, "chat", lambda *a, **k: json.dumps(contradictory()))
    result = run(match.match_score(match.MatchRequest(student_profile={}, student_info={}, target_job="Python")))["match_result"]
    assert result["overall_score"] == result["overall_score_computed"] == 71.5
    assert result["match_level"] == "较好匹配"
    assert [result["dimensions"][key]["weight"] for key in DIMENSIONS] == [25, 40, 20, 15]
    assert [result["dimensions"][key]["weighted_score"] for key in DIMENSIONS] == [20, 24, 14, 13.5]


@pytest.mark.parametrize("raw, expected", [((-1, 150, "NaN", "Infinity"), 40), ((None, "80", {}, []), 32)])
def test_match_bounds_invalid_model_scores(modules, monkeypatch, raw, expected):
    match = modules["module3_match"]
    monkeypatch.setattr(match, "get_profile", lambda _: None)
    monkeypatch.setattr(match, "chat", lambda *a, **k: json.dumps(contradictory(raw)))
    result = run(match.match_score(match.MatchRequest(student_profile={}, student_info={}, target_job="Python")))["match_result"]
    assert result["overall_score"] == expected
    assert all(0 <= result["dimensions"][key]["raw_score"] <= 100 for key in DIMENSIONS)


def test_data_paths_work_from_repository_root(modules, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    for name in ["module1_jobs", "module2_student", "module3_match", "module4_report"]:
        assert Path(modules[name].DATA_DIR) == root / "backend" / "data"
    assert run(modules["main_v2"].health())["data_files"] == {name: True for name in ["jobs_cleaned.json", "job_profiles.json", "job_graph.json"]}


def test_data_dir_relative_and_absolute_settings(modules, monkeypatch, tmp_path):
    import importlib
    settings = importlib.import_module("settings")
    monkeypatch.setenv("DATA_DIR", "custom-data")
    importlib.reload(settings)
    assert Path(settings.DATA_DIR) == Path(settings.__file__).parent / "custom-data"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    importlib.reload(settings)
    assert Path(settings.DATA_DIR) == tmp_path


def test_provider_auto_selection_and_no_secret_prefix(modules, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-secret-for-test")
    main = modules["main_v2"]
    info = run(main.get_ai_provider())
    assert info["provider"] == "qwen"
    providers = run(main.list_ai_providers())["providers"]
    assert [p["id"] for p in providers if p["current"]] == ["qwen"]
    switched = run(main.switch_ai_provider(main.ProviderSwitch(provider="qwen")))
    for response in [info, switched, run(main.health())]:
        assert "key_preview" not in json.dumps(response)
        assert "fake-sec" not in json.dumps(response)


def test_invalid_provider_status_does_not_echo_environment(modules, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "private-env-value")
    info = modules["ai_client"].get_provider_info()
    assert info["key_set"] is False
    assert "private-env-value" not in json.dumps(info)
    assert not any(p["current"] for p in run(modules["main_v2"].list_ai_providers())["providers"])


@pytest.mark.parametrize("field", ["name", "major"])
def test_student_rejects_blank_required_text(modules, field):
    data = {"name": "同学", "major": "计算机", "university": "", field: " \t "}
    with pytest.raises(ValidationError):
        modules["module2_student"].StudentInput(**data)


def test_student_trims_text_and_allows_optional_university(modules):
    student = modules["module2_student"].StudentInput(name=" 同学 ", major=" 计算机 ", university="", target_jobs=[" Python "])
    assert (student.name, student.major, student.university, student.target_jobs) == ("同学", "计算机", "", ["Python"])


@pytest.mark.parametrize("module, model, extra", [
    ("module3_match", "MatchRequest", {"student_info": {}, "student_profile": {}, "target_job": " "}),
    ("module3_match", "BatchMatchRequest", {"student_info": {}, "student_profile": {}, "target_jobs": []}),
    ("module3_match", "BatchMatchRequest", {"student_info": {}, "student_profile": {}, "target_jobs": [" "]}),
    ("module4_report", "ReportRequest", {"student_info": {}, "student_profile": {}, "target_job": " "}),
])
def test_required_target_jobs(modules, module, model, extra):
    with pytest.raises(ValidationError):
        getattr(modules[module], model)(**extra)


def test_report_normalizes_old_scores_and_exports_metadata(modules, monkeypatch):
    report = modules["module4_report"]
    prompts = []
    monkeypatch.setattr(report, "get_paths", lambda _: ([], []))
    async def fake_section(key, prompt, *args):
        prompts.append(prompt)
        return "AI声称匹配99分，建议学习2个月。" if key in ("executive_summary", "conclusion") else {}
    monkeypatch.setattr(report, "_gen_section", fake_section)
    old = {"long_text": "x" * 1000, **contradictory()}
    response = run(report.generate_report(report.ReportRequest(student_info={"name": "同学"}, student_profile={}, target_job="Python", match_result=old)))
    assert response["report"]["match_score"] == 71.5
    assert response["report"]["match_level"] == "较好匹配"
    assert all("71.5" in prompt for prompt in prompts)
    assert all("不得重新计算" in prompt for prompt in prompts)
    assert "2个月" in response["report"]["executive_summary"]
    md = run(report.export_markdown(response)).body.decode()
    assert "71.5" in md and "较好匹配" in md
    doc = Document(io.BytesIO(run(report.export_word(response)).body))
    assert "71.5" in "\n".join(p.text for p in doc.paragraphs)


def test_partial_failure_is_incomplete_and_markdown_exportable(modules):
    report = modules["module4_report"]
    data = {key: "[该章节生成失败，可点击重试或手动编辑]" for key in report.REQUIRED_SECTIONS}
    result = run(report.check_completeness({"report": data, "has_errors": True}))
    assert result["is_complete"] is False
    assert not result["ok_sections"]
    assert run(report.export_markdown({"report": data})).status_code == 200


def test_report_requests_are_parallel_and_health_remains_responsive(modules, monkeypatch):
    report = modules["module4_report"]
    release = threading.Event()
    monkeypatch.setattr(report, "get_paths", lambda _: ([], []))
    started = set()
    lock = threading.Lock()
    def blocked_chat(prompt, **kwargs):
        with lock:
            started.add(threading.get_ident())
        assert release.wait(2), "event loop blocked while AI request is pending"
        return '{"executive_summary":"测试章节内容超过二十个字符保证能正常提取生成结果"}'
    monkeypatch.setattr(report, "chat", blocked_chat)
    async def scenario():
        task = asyncio.create_task(report.generate_report(report.ReportRequest(student_info={}, student_profile={}, target_job="Python")))
        try:
            for _ in range(100):
                if len(started) >= 7:
                    break
                await asyncio.sleep(0.005)
            assert len(started) == 7, "all seven requests should start before any finishes"
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=modules["main_v2"].app), base_url="http://test") as client:
                response = await asyncio.wait_for(client.get("/health"), 0.5)
                assert response.status_code == 200
        finally:
            release.set()
            await task
    run(scenario())


def test_polish_preserves_structured_sections(modules, monkeypatch):
    report = modules["module4_report"]
    original = {"title": "行动计划", "actions": [{"action": "学习Python", "weeks": 8}]}
    polished = {"title": "行动计划", "actions": [{"action": "系统学习Python", "weeks": 8}]}
    prompts = []
    def fake_chat(prompt, **kwargs):
        prompts.append(prompt)
        return json.dumps(polished)
    monkeypatch.setattr(report, "chat", fake_chat)
    response = run(report.polish_section(report.PolishRequest(section_key="section3_action_plan", section_content=json.dumps(original))))
    assert response["polished"] == polished
    assert "JSON" in prompts[0]


def test_polish_rejects_destroyed_structure(modules, monkeypatch):
    report = modules["module4_report"]
    monkeypatch.setattr(report, "chat", lambda *a, **kw: '{"description":"structure lost"}')
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        run(report.polish_section(report.PolishRequest(section_key="section3_action_plan", section_content='{"actions":[{"action":"study","weeks":8}]}')))


@pytest.mark.parametrize("endpoint,payload", [
    ("/api/student/analyze", {"name": " 同学 ", "major": "计算机", "university": ""}),
    ("/api/jobs/recommend", {"student_info": {}, "student_profile": {}}),
    ("/api/match/score", {"student_info": {}, "student_profile": {}, "target_job": "Python"}),
    ("/api/report/polish", {"section_key": "executive_summary", "section_content": "原始章节文字"}),
    ("/api/student/upload-resume", None),
])
def test_ai_endpoints_release_event_loop(modules, monkeypatch, endpoint, payload):
    release = threading.Event()
    started = threading.Event()
    loop_thread = threading.get_ident()
    def blocked_chat(*args, **kwargs):
        started.set()
        assert threading.get_ident() != loop_thread, "AI call must run outside event loop thread"
        assert release.wait(2), "health could not release pending request"
        return '{}'
    for name in ["module1_jobs", "module2_student", "module3_match", "module4_report"]:
        monkeypatch.setattr(modules[name], "chat", blocked_chat)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=modules["main_v2"].app), base_url="http://test") as client:
            kwargs = {"json": payload} if payload is not None else {"files": {"file": ("resume.txt", b"Test resume", "text/plain")}}
            task = asyncio.create_task(client.post(endpoint, **kwargs))
            try:
                for _ in range(100):
                    if started.is_set():
                        break
                    await asyncio.sleep(0.005)
                assert started.is_set()
                assert (await asyncio.wait_for(client.get("/health"), 0.5)).status_code == 200
            finally:
                release.set()
                response = await task
            assert response.status_code == 200, response.text
    run(scenario())


def test_job_graph_required_name(modules):
    with pytest.raises(ValidationError):
        modules["module1_jobs"].JobNameRequest(job_name=" \t")


def test_report_retries_invalid_json(modules, monkeypatch):
    report = modules["module4_report"]
    responses = iter(["invalid JSON", '{"executive_summary":"有效摘要内容"}'])
    monkeypatch.setattr(report, "chat", lambda *a, **kw: next(responses))
    assert run(report._gen_section("executive_summary", "prompt", "system", 100)) == "有效摘要内容"


@pytest.mark.parametrize("content", ["this should have been an object", {}, []])
def test_report_rejects_invalid_section_shapes(modules, monkeypatch, content):
    report = modules["module4_report"]
    monkeypatch.setattr(report, "chat", lambda *a, **kw: json.dumps({"section1_career_exploration": content}))
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        run(report._gen_section("section1_career_exploration", "prompt", "system", 100, retries=1))


def test_report_partial_generation_can_be_checked_and_exported(modules, monkeypatch):
    report = modules["module4_report"]
    async def fake_section(key, *args):
        if key == "section1_career_exploration":
            raise RuntimeError("offline simulated failure")
        if key in ("executive_summary", "conclusion"):
            return "完整的执行摘要或结论章节文字内容"
        return {"title": "章节", "evaluation_metrics": ["复盘"], "adjustment_strategy": "定期调整"}
    monkeypatch.setattr(report, "_gen_section", fake_section)
    response = run(report.generate_report(report.ReportRequest(student_info={}, student_profile={}, target_job="Python")))
    assert response["has_errors"] is True
    assert "section1_career_exploration" in response["errors"][0]
    assert run(report.check_completeness(response))["is_complete"] is False
    assert run(report.export_markdown(response)).status_code == 200
    assert run(report.export_word(response)).status_code == 200


def test_data_dir_dotenv_loaded_before_shared_setting(modules, monkeypatch, tmp_path):
    import importlib
    settings = importlib.import_module("settings")
    backend_env = Path(settings.__file__).parent / ".env"
    real_open = open
    real_exists = __import__("os").path.exists
    monkeypatch.setattr("os.path.exists", lambda path: True if Path(path) == backend_env else real_exists(path))
    def fake_open(path, *args, **kwargs):
        if Path(path) == backend_env:
            return io.StringIO("DATA_DIR=dotenv-data\n")
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr("builtins.open", fake_open)
    monkeypatch.delenv("DATA_DIR", raising=False)
    importlib.reload(settings)
    assert Path(settings.DATA_DIR) == Path(settings.__file__).parent / "dotenv-data"


def test_provider_status_explicit_missing_key_and_auto_none(modules, monkeypatch):
    main = modules["main_v2"]
    for explicit in [None, "qwen", " QWEN "]:
        if explicit is None:
            monkeypatch.delenv("AI_PROVIDER", raising=False)
        else:
            monkeypatch.setenv("AI_PROVIDER", explicit)
        assert run(main.get_ai_provider())["key_set"] is False
        assert not any(p["current"] for p in run(main.list_ai_providers())["providers"])
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")
    assert [p["id"] for p in run(main.list_ai_providers())["providers"] if p["current"]] == ["qwen"]


def test_completeness_rejects_wrong_section_types(modules):
    report = modules["module4_report"]
    data = {key: "a long unexpected section string" for key in report.REQUIRED_SECTIONS}
    data["executive_summary"] = {"text": "must be narrative"}
    checked = run(report.check_completeness(data))
    assert checked["is_complete"] is False
    assert "section1_career_exploration" in checked["incomplete_sections"]
    assert "executive_summary" in checked["incomplete_sections"]


@pytest.mark.parametrize("method", ["export_markdown", "export_word"])
def test_exports_tolerate_partial_nested_chapters(modules, method):
    report = modules["module4_report"]
    data = {
        "section1_career_exploration": {"title": "第一章", "transfer_options": [None, "incomplete"]},
        "section2_career_goals": {"short_term_goal": "failed nested goal", "mid_term_goal": None, "salary_growth_forecast": [None, "incomplete"]},
        "section3_action_plan": {"short_term_plan": "failed nested plan", "mid_term_plan": {"actions": [None, "incomplete"]}},
        "section4_competitive_strategy": {"improvement_priority": [None, "incomplete"]},
        "section5_resources": {"online_courses": [None, "incomplete"], "certifications": [None, "incomplete"]},
    }
    assert run(getattr(report, method)({"report": data})).status_code == 200


@pytest.mark.parametrize("content", [{"error": "model refused"}, {"title": "章节标题"}, {"match_overview": None}])
def test_report_rejects_no_substantive_content(modules, monkeypatch, content):
    report = modules["module4_report"]
    monkeypatch.setattr(report, "chat", lambda *a, **kw: json.dumps({"section1_career_exploration": content}))
    with pytest.raises(Exception):
        run(report._gen_section("section1_career_exploration", "prompt", "system", 100, retries=1))
    checked = run(report.check_completeness({"section1_career_exploration": content}))
    assert "section1_career_exploration" in checked["incomplete_sections"]
