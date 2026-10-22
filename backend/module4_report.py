"""
module4_report.py — 模块4：职业报告生成
接口：
  POST /api/report/generate         生成6章节报告
  POST /api/report/polish           AI润色单章节
  POST /api/report/check            完整性检查
  POST /api/report/export/markdown  导出Markdown文件
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from validation import RequiredText
from module3_match import normalize_match_result
from typing import List, Optional, Dict, Literal
from fastapi.responses import StreamingResponse
import json, os, re, asyncio
from datetime import datetime

from ai_client import chat, clean_json
from starlette.concurrency import run_in_threadpool

router   = APIRouter()
from settings import DATA_DIR

REQUIRED_SECTIONS = [
    "executive_summary","section1_career_exploration","section2_career_goals",
    "section3_action_plan","section4_competitive_strategy","section5_resources","conclusion",
]

def load_graph():
    with open(os.path.join(DATA_DIR, "job_graph.json"), "r", encoding="utf-8") as f:
        return json.load(f)

def get_paths(job_name):
    g = load_graph()
    def match(d):
        for k, v in d.items():
            if job_name in k or k in job_name: return v
        return []
    return match(g.get("vertical_paths", {})), match(g.get("lateral_paths", {}))


class ReportRequest(BaseModel):
    section_keys: Optional[List[Literal["executive_summary", "section1_career_exploration", "section2_career_goals", "section3_action_plan", "section4_competitive_strategy", "section5_resources", "conclusion"]]] = Field(default=None, min_length=1, max_length=7)
    student_info:    Dict
    student_profile: Dict
    target_job:      RequiredText
    match_result:    Optional[Dict] = None
    career_goals:    Optional[str]  = None
    personal_values: Optional[List[str]] = []
    special_notes:   Optional[str]  = None

class PolishRequest(BaseModel):
    section_key:     str
    section_content: str
    polish_type:     str = "comprehensive"


# ═══════════════════════════════════════════════════════════════════
# ── 章节独立生成辅助函数 ────────────────────────────────────────
def _build_ctx(req, path_ctx, match_ctx):
    """构建各章节共用的上下文摘要"""
    return {
        "name":    req.student_info.get("name", "同学"),
        "job":     req.target_job,
        "info":    json.dumps(req.student_info,    ensure_ascii=False),
        "profile": json.dumps(req.student_profile, ensure_ascii=False)[:600],
        "match":   match_ctx,
        "path":    path_ctx[:500],
        "goals":   req.career_goals or "未填写",
        "values":  ", ".join(req.personal_values) if req.personal_values else "未填写",
        "notes":   req.special_notes or "无",
    }

def _safe_parse(text: str) -> dict:
    """两层 JSON 解析兜底"""
    cleaned = clean_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fixed = re.sub(r",[ \t\n]*([}\]])", r"\1", cleaned)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail="报告解析失败: " + str(e))

def _has_section_content(key, value):
    if key in ("executive_summary", "conclusion"):
        return isinstance(value, str) and bool(value.strip()) and not value.strip().startswith("[该章节生成失败")
    def substantive(item):
        if isinstance(item, str):
            return bool(item.strip())
        if isinstance(item, list):
            return any(substantive(child) for child in item)
        if isinstance(item, dict):
            return any(substantive(child) for name, child in item.items()
                       if name not in {"title", "error", "message", "status", "code"})
        return False
    return isinstance(value, dict) and substantive(value)


async def _gen_section(key: str, prompt: str, system: str, max_tokens: int, retries: int = 2):
    """生成单章节，失败自动重试一次"""
    def validated(value):
        if key in ("executive_summary", "conclusion"):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("章节正文必须是非空文字")
        elif not _has_section_content(key, value):
            raise ValueError("章节内容必须是非空JSON对象")
        return value

    last_err = None
    for attempt in range(retries):
        try:
            text   = await run_in_threadpool(chat, prompt, system=system, max_tokens=max_tokens)
            parsed = _safe_parse(text)
            # 情况1：AI 返回 {"section4_competitive_strategy": {...}} → 提取内部值
            if isinstance(parsed, dict) and key in parsed:
                return validated(parsed[key])
            # 情况2：AI 直接返回内部对象（不含外层 key）→ 直接使用
            # 用特征字段判断：如果包含该章节的已知子字段，说明是直接返回的内容
            KNOWN_SUBKEYS = {
                "executive_summary":            [],          # 字符串，无子字段
                "section1_career_exploration":  ["match_overview", "skill_gap_analysis"],
                "section2_career_goals":        ["short_term_goal", "long_term_vision"],
                "section3_action_plan":         ["short_term_plan", "evaluation_cycle"],
                "section4_competitive_strategy":["core_advantages", "differentiation_strategy"],
                "section5_resources":           ["online_courses", "certifications"],
                "conclusion":                   [],          # 字符串，无子字段
            }
            subkeys = KNOWN_SUBKEYS.get(key, [])
            if isinstance(parsed, dict) and subkeys and any(sk in parsed for sk in subkeys):
                return validated(parsed)  # AI 直接返回了内容层
            # 情况3：字符串类型章节（executive_summary / conclusion）
            if key in ("executive_summary", "conclusion") and isinstance(parsed, dict):
                # 尝试找值为字符串的字段
                for v in parsed.values():
                    if isinstance(v, str) and len(v) > 20:
                        return validated(v)
            return validated(parsed)
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
    raise HTTPException(status_code=500, detail=f"{key} 生成失败: {last_err}")


# POST /api/report/generate
# ═══════════════════════════════════════════════════════════════════
@router.post("/generate")
async def generate_report(req: ReportRequest, stream: bool = False):
    if not stream:
        return await _generate_report(req)
    async def events():
        queue = asyncio.Queue()
        async def work():
            try:
                result = await _generate_report(req, queue.put)
                await queue.put({"type": "complete", "data": result})
            except Exception:
                await queue.put({"type": "error", "message": "报告生成失败，请稍后重试"})
        task = asyncio.create_task(work())
        try:
            while True:
                item = await queue.get()
                yield json.dumps(item, ensure_ascii=False) + "\n"
                if item["type"] in ("complete", "error"):
                    break
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


async def _generate_report(req: ReportRequest, progress=None):
    vpath, lpath = get_paths(req.target_job)
    path_ctx  = json.dumps({"vertical": vpath, "lateral": lpath}, ensure_ascii=False)
    canonical_match = normalize_match_result(req.match_result) if req.match_result else None
    if canonical_match:
        # Scores precede optional detail so context limits cannot remove them.
        match_ctx = json.dumps({"overall_score": canonical_match["overall_score"], "match_level": canonical_match["match_level"], "dimensions": canonical_match["dimensions"]}, ensure_ascii=False)[:1200]
        score_instruction = f"【权威匹配评分】综合匹配分：{canonical_match['overall_score']}；等级：{canonical_match['match_level']}。不得重新计算、修改或杜撰综合匹配分；涉及匹配评分时必须使用上述分数。\n"
    else:
        match_ctx = "（未进行人岗匹配）"
        score_instruction = "未进行人岗匹配，不得杜撰综合匹配分。\n"
    today     = datetime.now().strftime("%Y年%m月%d日")
    ctx       = _build_ctx(req, path_ctx, match_ctx)
    system    = "你是资深职业规划顾问。严格按JSON格式输出，只输出JSON不输出其他内容。"

    # 反馈重生成时在每个章节 prompt 前置用户反馈
    feedback_prefix = ""
    if req.special_notes and "用户反馈" in req.special_notes:
        feedback_prefix = f"【用户反馈，最高优先级，必须体现在输出中】{req.special_notes}\n\n"

    # 7个章节的独立 prompt，使用自然语言描述要求，避免AI原样输出占位符
    section_tasks = [
        ("executive_summary", 700,
         f"""{feedback_prefix}请为以下学生撰写职业规划报告的执行摘要，约200字，涵盖核心竞争力、目标岗位适配度、关键能力缺口、最优先行动建议。
学生：{ctx['name']}  目标岗位：{ctx['job']}
能力画像摘要：{ctx['profile']}
匹配结果：{ctx['match']}
只输出以下JSON，字段值必须是真实生成的文字内容：
{{"executive_summary":"此处填写200字执行摘要正文"}}"""),

        ("section1_career_exploration", 1100,
         f"""{feedback_prefix}请为以下学生生成第一章"职业探索与岗位匹配"的内容，所有文字字段必须填写真实分析内容。
学生：{ctx['name']}  目标岗位：{ctx['job']}
能力画像：{ctx['profile']}  匹配结果：{ctx['match']}  转岗路径参考：{ctx['path']}
只输出以下JSON，所有字符串字段必须填写真实内容（不得保留示例文字）：
{{"section1_career_exploration":{{"title":"第一章 职业探索与岗位匹配","match_overview":"此处填写150字综合匹配结论","skill_gap_analysis":"此处填写3个核心技能缺口分析","opportunity_analysis":"此处填写100字行业机遇","risk_analysis":"此处填写100字竞争风险","visualization_data":[{{"dimension":"专业技能","student_score":70,"job_requirement":85}}],"transfer_options":[{{"target":"转岗方向名称","difficulty":"较易","reason":"适合原因说明"}}]}}}}"""),

        ("section2_career_goals", 1100,
         f"""{feedback_prefix}请为以下学生生成第二章"职业目标与发展路径"，所有文字字段必须填写真实内容。
学生：{ctx['name']}  目标岗位：{ctx['job']}
职业目标：{ctx['goals']}  价值观：{ctx['values']}  晋升路径参考：{ctx['path']}
只输出以下JSON，所有字符串字段必须填写真实内容：
{{"section2_career_goals":{{"title":"第二章 职业目标与发展路径","short_term_goal":{{"timeline":"毕业后1-2年","position":"此处填写目标职级","description":"此处填写100字描述","key_milestones":["里程碑1（含可量化指标）","里程碑2"]}},"mid_term_goal":{{"timeline":"3-5年","position":"此处填写目标职级","description":"此处填写100字描述","key_milestones":["里程碑1","里程碑2"]}},"long_term_vision":"此处填写50字长期愿景","career_path_description":"此处填写150字职业发展路径叙述","salary_growth_forecast":[{{"period":"入职期0-2年","expected_salary":"此处填写薪资区间"}},{{"period":"成长期2-4年","expected_salary":"此处填写薪资区间"}},{{"period":"成熟期4-6年","expected_salary":"此处填写薪资区间"}}]}}}}"""),

        ("section3_action_plan", 1300,
         f"""{feedback_prefix}请为以下学生生成第三章"行动计划"，所有字段必须填写真实可操作的内容。
学生：{ctx['name']}  目标岗位：{ctx['job']}
能力画像：{ctx['profile']}  匹配分析：{ctx['match']}
只输出以下JSON，所有字段必须填写真实内容：
{{"section3_action_plan":{{"title":"第三章 行动计划","short_term_plan":{{"timeline":"未来6个月","goals":["具体目标1","具体目标2"],"actions":[{{"category":"技能提升","action":"具体学习行动","resource":"推荐学习资源","deadline":"3个月内","success_metric":"可量化完成标准"}}]}},"mid_term_plan":{{"timeline":"6个月-2年","goals":["具体阶段目标"],"actions":[{{"category":"实践提升","action":"具体行动","resource":"资源","deadline":"时间","success_metric":"衡量指标"}}]}},"evaluation_cycle":"每3个月复盘一次，结合市场动态调整","evaluation_metrics":["指标1","指标2","指标3"],"adjustment_triggers":["触发调整的情形1","情形2"],"adjustment_strategy":"此处填写100字动态调整策略"}}}}"""),

        ("section4_competitive_strategy", 900,
         f"""{feedback_prefix}请为以下学生生成第四章"差异化竞争策略"，所有字段必须填写真实内容。
学生：{ctx['name']}  目标岗位：{ctx['job']}
能力画像：{ctx['profile']}  特别关注：{ctx['notes']}
只输出以下JSON，所有字段必须填写真实内容：
{{"section4_competitive_strategy":{{"title":"第四章 差异化竞争策略","core_advantages":["核心优势1的详细描述（约100字）","核心优势2的描述"],"differentiation_strategy":"此处填写150字差异化定位策略","improvement_priority":[{{"rank":1,"item":"最优先提升项名称","method":"具体提升方法","expected_outcome":"预期达到的效果"}}]}}}}"""),

        ("section5_resources", 900,
         f"""{feedback_prefix}请为以下学生生成第五章"学习资源推荐"，推荐真实可用的课程和证书。
学生：{ctx['name']}  目标岗位：{ctx['job']}
能力画像：{ctx['profile'][:300]}
只输出以下JSON，所有字段必须填写真实内容：
{{"section5_resources":{{"title":"第五章 学习资源推荐","online_courses":[{{"platform":"真实平台名称","course":"真实课程名","purpose":"学习目的说明","duration_weeks":8}}],"certifications":[{{"cert_name":"真实证书名称","issuing_body":"颁发机构","priority":"高","prep_weeks":12}}],"practice_projects":["项目建议1","项目建议2","项目建议3"],"communities":["推荐社区或组织"],"networking_advice":"此处填写50字人脉建设建议"}}}}"""),

        ("conclusion", 400,
         f"""{feedback_prefix}请为{ctx['name']}同学撰写职业规划报告的总结与激励语，约150字，回顾核心优势，以积极正向语气作结，直接称呼学生姓名。
目标岗位：{ctx['job']}  职业目标：{ctx['goals']}
只输出以下JSON：
{{"conclusion":"此处填写150字个性化总结激励语正文"}}"""),
    ]

    report_data = {
        "report_title": f"{ctx['name']}职业生涯发展规划报告",
        "generated_at": today,
        "match_score": canonical_match["overall_score"] if canonical_match else None,
        "match_level": canonical_match["match_level"] if canonical_match else None,
    }
    errors = []

    # ── 并行生成所有章节 ──────────────────────────────────────────
    # 用 asyncio.gather 同时发起7个AI请求，总时长取决于最慢的单章
    # 约15-25秒（原串行70-90秒），大幅提升用户体验
    async def _safe_gen(key, prompt, max_tokens):
        """包装一层异常处理，确保单章失败不影响其他章节"""
        try:
            result = await _gen_section(key, score_instruction + prompt, system, max_tokens)
            if progress:
                await progress({"type": "section", "key": key, "ok": True})
            return key, result, None
        except Exception as e:
            if progress:
                await progress({"type": "section", "key": key, "ok": False})
            return key, f"[该章节生成失败，可点击重试或手动编辑]", str(e)[:80]

    # 并发执行
    results = await asyncio.gather(*[
        _safe_gen(key, prompt, max_tokens)
        for key, max_tokens, prompt in section_tasks if req.section_keys is None or key in req.section_keys
    ])

    for key, result, err in results:
        report_data[key] = result
        if err:
            errors.append(f"{key}: {err}")

    return {
        "student_name": ctx["name"],
        "target_job":   req.target_job,
        "report":       report_data,
        "errors":       errors,
        "has_errors":   len(errors) > 0,
    }


# ═══════════════════════════════════════════════════════════════════
# POST /api/report/polish
# ═══════════════════════════════════════════════════════════════════
@router.post("/polish")
async def polish_section(req: PolishRequest):
    instructions = {
        "comprehensive": "全面优化语言表达、逻辑结构和内容完整性，保持专业正式风格",
        "grammar":        "仅修正语法错误和不流畅表达，不改变内容和结构",
        "concise":        "精简至原文80%，保留核心信息",
        "expand":         "丰富细节和举例，扩展至原文120%",
    }
    instruction = instructions.get(req.polish_type, instructions["comprehensive"])
    prompt = f"请对以下职业规划报告章节进行润色，要求：{instruction}\n直接返回润色后的内容，不添加任何说明。\n\n原内容：\n{req.section_content}"
    try:
        original_data = json.loads(req.section_content)
    except json.JSONDecodeError:
        original_data = None
    structured = isinstance(original_data, (dict, list))
    if structured:
        prompt = f"请润色以下JSON中的文字内容，要求：{instruction}。严格保持全部字段名称、层级、数组长度、数值和数据类型，只返回JSON。\n{req.section_content}"

    def preserves_structure(original, updated):
        if type(original) is not type(updated):
            return False
        if isinstance(original, dict):
            return original.keys() == updated.keys() and all(preserves_structure(v, updated[k]) for k, v in original.items())
        if isinstance(original, list):
            return len(original) == len(updated) and all(preserves_structure(a, b) for a, b in zip(original, updated))
        return isinstance(original, str) or original == updated

    try:
        polished = await run_in_threadpool(chat, prompt, max_tokens=2000)
        if structured:
            polished = json.loads(clean_json(polished))
            if not preserves_structure(original_data, polished):
                raise ValueError("润色结果改变了章节结构或数值，请重试")
        return {
            "section_key": req.section_key,
            "polish_type": req.polish_type,
            "original":    req.section_content,
            "polished":    polished,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"润色失败: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# POST /api/report/check
# ═══════════════════════════════════════════════════════════════════
@router.post("/check")
async def check_completeness(report: Dict):
    data = report.get("report", report)
    missing, incomplete, ok = [], [], []

    def empty(v):
        if v is None: return True
        if isinstance(v, str) and v.strip().startswith("[该章节生成失败"): return True
        if isinstance(v, str)  and len(v.strip()) < 10: return True
        if isinstance(v, list) and len(v) == 0: return True
        if isinstance(v, dict) and len(v) == 0: return True
        return False

    for sec in REQUIRED_SECTIONS:
        if sec not in data:           missing.append(sec)
        elif sec in ("executive_summary", "conclusion") and not isinstance(data[sec], str):
            incomplete.append(sec)
        elif sec not in ("executive_summary", "conclusion") and not isinstance(data[sec], dict):
            incomplete.append(sec)
        elif empty(data[sec]) or not _has_section_content(sec, data[sec]): incomplete.append(sec)
        else:                         ok.append(sec)

    s3 = data.get("section3_action_plan", {})
    if isinstance(s3, dict):
        if not s3.get("evaluation_metrics"):
            incomplete.append("section3_action_plan.evaluation_metrics（动态调整指标缺失）")
        if not s3.get("adjustment_strategy"):
            incomplete.append("section3_action_plan.adjustment_strategy（调整策略缺失）")

    score = max(0, min(100, int(len(ok) / len(REQUIRED_SECTIONS) * 100) - len(incomplete) * 5))
    return {
        "completeness_score":  score,
        "is_complete":         len(missing) == 0 and len(incomplete) == 0,
        "ok_sections":         ok,
        "missing_sections":    missing,
        "incomplete_sections": incomplete,
        "suggestions":         [f"缺失，请补充：{s}" for s in missing] + [f"不完整，请完善：{s}" for s in incomplete],
    }


# ═══════════════════════════════════════════════════════════════════
# POST /api/report/export/markdown
# ═══════════════════════════════════════════════════════════════════
@router.post("/export/markdown")
async def export_markdown(report: Dict):
    data = report.get("report", report)
    name = report.get("student_name", "同学")
    job  = report.get("target_job", "目标岗位")

    def li(items):
        if not items: return ""
        if isinstance(items, str): return f"- {items}\n"
        return "".join(f"- {i}\n" for i in items if i)

    def sd(v):
        return v if isinstance(v, dict) else {}

    def ss(v):
        if isinstance(v, str): return v
        return ""

    def records(value):
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    L = []
    L.append(f"# {data.get('report_title', f'{name}职业生涯发展规划报告')}\n\n")
    L.append(f"> 生成时间：{data.get('generated_at','')}　目标岗位：**{job}**\n\n---\n\n")
    if data.get("match_score") is not None:
        L.append(f"> 综合匹配分（系统计算）：**{data['match_score']} / 100**　匹配等级：**{data.get('match_level', '')}**\n\n")
    L.append(f"## 执行摘要\n\n{data.get('executive_summary','')}\n\n")

    s1 = sd(data.get("section1_career_exploration", {}))
    if s1:
        L.append(f"## {s1.get('title','第一章')}\n\n")
        L.append(f"{s1.get('match_overview','')}\n\n")
        L.append(f"**技能差距**：{s1.get('skill_gap_analysis','')}\n\n")
        L.append(f"**行业机遇**：{s1.get('opportunity_analysis','')}\n\n")
        L.append(f"**竞争风险**：{s1.get('risk_analysis','')}\n\n")

    s2 = sd(data.get("section2_career_goals", {}))
    if s2:
        L.append(f"## {s2.get('title','第二章')}\n\n")
        st = sd(s2.get("short_term_goal", {}))
        if st:
            L.append(f"### 短期目标（{st.get('timeline','')}）\n\n**{st.get('position','')}**\n\n{st.get('description','')}\n\n")
            L.append("**里程碑：**\n"); L.append(li(st.get("key_milestones",[])))
        mt = sd(s2.get("mid_term_goal", {}))
        if mt:
            L.append(f"\n### 中期目标（{mt.get('timeline','')}）\n\n**{mt.get('position','')}**\n\n{mt.get('description','')}\n\n")
        L.append(f"\n**长期愿景**：{s2.get('long_term_vision','')}\n\n")
        if s2.get("salary_growth_forecast"):
            L.append("### 薪资成长预测\n\n| 阶段 | 预期薪资 |\n|------|----------|\n")
            for r in records(s2["salary_growth_forecast"]):
                L.append(f"| {r.get('period','')} | {r.get('expected_salary','')} |\n")
            L.append("\n")

    s3 = sd(data.get("section3_action_plan", {}))
    if s3:
        L.append(f"## {s3.get('title','第三章')}\n\n")
        for pk, pl in [("short_term_plan","短期计划（6个月）"),("mid_term_plan","中期计划（6个月-2年）")]:
            plan = sd(s3.get(pk, {}))
            if plan:
                L.append(f"### {pl}\n\n")
                L.append(li(plan.get("goals",[])))
                L.append("\n| 类别 | 行动 | 资源 | 时间 | 衡量指标 |\n|------|------|------|------|----------|\n")
                for a in records(plan.get("actions",[])):
                    L.append(f"| {a.get('category','')} | {a.get('action','')} | {a.get('resource','')} | {a.get('deadline','')} | {a.get('success_metric','')} |\n")
                L.append("\n")
        L.append(f"**评估周期**：{s3.get('evaluation_cycle','')}\n\n")
        L.append("**评估指标：**\n"); L.append(li(s3.get("evaluation_metrics",[])))
        L.append(f"\n**调整策略**：{s3.get('adjustment_strategy','')}\n\n")

    s4 = sd(data.get("section4_competitive_strategy", {}))
    if s4:
        L.append(f"## {s4.get('title','第四章')}\n\n")
        L.append(li(s4.get("core_advantages",[])))
        L.append(f"\n{s4.get('differentiation_strategy','')}\n\n")

    s5 = sd(data.get("section5_resources", {}))
    if s5:
        L.append(f"## {s5.get('title','第五章')}\n\n")
        L.append("| 平台 | 课程 | 目的 |\n|------|------|------|\n")
        for c in records(s5.get("online_courses",[])):
            L.append(f"| {c.get('platform','')} | {c.get('course','')} | {c.get('purpose','')} |\n")
        L.append("\n| 证书 | 机构 | 优先级 |\n|------|------|--------|\n")
        for c in records(s5.get("certifications",[])):
            L.append(f"| {c.get('cert_name','')} | {c.get('issuing_body','')} | {c.get('priority','')} |\n")
        L.append("\n")

    L.append(f"---\n\n## 总结\n\n{data.get('conclusion','')}\n")

    content  = "".join(L)
    from urllib.parse import quote
    filename     = f"{name}_{job}_职业规划报告.md"
    filename_enc = quote(filename, safe="")
    disposition  = "attachment; filename=report.md; filename*=UTF-8''" + filename_enc
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": disposition}
    )

# ═══════════════════════════════════════════════════════════════════
# POST /api/report/export/word  — 导出 Word 文档（.docx）
# ═══════════════════════════════════════════════════════════════════
@router.post("/export/word")
async def export_word(report: Dict):
    try:
        from docx import Document as DocxDocument
        from docx.shared import Pt, RGBColor, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        import io
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="缺少依赖包，请执行: pip install python-docx"
        )

    data = report.get("report", report)
    name = report.get("student_name", "同学")
    job  = report.get("target_job", "目标岗位")

    def sd(v):
        return v if isinstance(v, dict) else {}

    def ss(v):
        if isinstance(v, str): return v
        return ""

    def li_text(items):
        if not items: return []
        if isinstance(items, str): return [items]
        return [str(i) for i in items if i]

    doc = DocxDocument()

    # ── 页面设置 ──
    section = doc.sections[0]
    section.page_width  = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = section.right_margin   = Cm(2.5)
    section.top_margin  = section.bottom_margin  = Cm(2.5)

    # ── 字体颜色辅助 ──
    def set_color(run, hex_color):
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        run.font.color.rgb = RGBColor(r, g, b)

    def add_heading(text, level=1, color="1F3864"):
        h = doc.add_heading(text, level=level)
        h.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in h.runs:
            set_color(run, color)
            run.font.name = "微软雅黑"
            run.font.bold = True
        return h

    def add_paragraph(text, bold=False, color=None, size=11):
        p = doc.add_paragraph()
        run = p.add_run(str(text))
        run.font.name = "微软雅黑"
        run.font.size = Pt(size)
        run.bold = bold
        if color:
            set_color(run, color)
        return p

    def add_bullet(text, color=None):
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(str(text))
        run.font.name = "微软雅黑"
        run.font.size = Pt(10.5)
        if color:
            set_color(run, color)

    def add_table(headers, rows, col_widths=None):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        # 表头
        hrow = t.rows[0]
        for i, h in enumerate(headers):
            cell = hrow.cells[i]
            cell.text = h
            for run in cell.paragraphs[0].runs:
                run.font.bold = True
                run.font.name = "微软雅黑"
                run.font.size = Pt(10)
                set_color(run, "FFFFFF")
            # 表头背景蓝色
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "2E75B6")
            tcPr.append(shd)
        # 数据行
        for ri, row in enumerate(rows):
            tr = t.add_row()
            fill = "F2F2F2" if ri % 2 == 0 else "FFFFFF"
            for i, val in enumerate(row):
                cell = tr.cells[i]
                cell.text = str(val or "")
                for run in cell.paragraphs[0].runs:
                    run.font.name = "微软雅黑"
                    run.font.size = Pt(10)
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:fill"), fill)
                tcPr.append(shd)
        doc.add_paragraph()
        return t

    # ══ 封面 ══
    doc.add_paragraph()
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run(data.get("report_title", f"{name}职业生涯发展规划报告"))
    title_run.font.name = "微软雅黑"
    title_run.font.size = Pt(22)
    title_run.bold = True
    set_color(title_run, "1F3864")

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub_p.add_run(f"生成时间：{data.get('generated_at','')}　　目标岗位：{job}")
    sub_run.font.name = "微软雅黑"
    sub_run.font.size = Pt(11)
    set_color(sub_run, "595959")
    if data.get("match_score") is not None:
        add_paragraph(f"综合匹配分（系统计算）：{data['match_score']} / 100　匹配等级：{data.get('match_level', '')}", bold=True)
    doc.add_paragraph()

    # ══ 执行摘要 ══
    add_heading("执行摘要", level=1)
    add_paragraph(ss(data.get("executive_summary", "")), size=11)
    doc.add_paragraph()

    # ══ 第一章 ══
    s1 = sd(data.get("section1_career_exploration", {}))
    if s1:
        add_heading(s1.get("title", "第一章 职业探索与岗位匹配"), level=1)
        if s1.get("match_overview"):
            add_paragraph(ss(s1["match_overview"]))
        for label, key in [("技能差距", "skill_gap_analysis"),
                            ("行业机遇", "opportunity_analysis"),
                            ("竞争风险", "risk_analysis")]:
            if s1.get(key):
                p = doc.add_paragraph()
                p.add_run(f"{label}：").bold = True
                p.runs[0].font.name = "微软雅黑"
                p.add_run(ss(s1[key])).font.name = "微软雅黑"
        if s1.get("transfer_options"):
            add_heading("转岗路径参考", level=2, color="2E75B6")
            opts = s1["transfer_options"]
            if isinstance(opts, list):
                add_table(
                    ["目标岗位", "难度", "适合原因"],
                    [[o.get("target",""), o.get("difficulty",""), o.get("reason","")] for o in opts if isinstance(o, dict)]
                )
        doc.add_paragraph()

    # ══ 第二章 ══
    s2 = sd(data.get("section2_career_goals", {}))
    if s2:
        add_heading(s2.get("title", "第二章 职业目标与发展路径"), level=1)
        for goal_key, label in [("short_term_goal","短期目标"),("mid_term_goal","中期目标")]:
            g = sd(s2.get(goal_key, {}))
            if g:
                add_heading(f"{label}（{g.get('timeline','')}）", level=2, color="2E75B6")
                add_paragraph(f"目标职级：{g.get('position','')}", bold=True)
                add_paragraph(ss(g.get("description","")))
                for ms in li_text(g.get("key_milestones",[])):
                    add_bullet(ms)
        if s2.get("long_term_vision"):
            add_heading("长期愿景", level=2, color="2E75B6")
            add_paragraph(ss(s2["long_term_vision"]))
        if s2.get("salary_growth_forecast"):
            add_heading("薪资成长预测", level=2, color="2E75B6")
            rows = []
            for r in s2["salary_growth_forecast"]:
                if isinstance(r, dict):
                    rows.append([r.get("period",""), r.get("expected_salary","")])
            if rows:
                add_table(["阶段", "预期薪资"], rows)
        doc.add_paragraph()

    # ══ 第三章 ══
    s3 = sd(data.get("section3_action_plan", {}))
    if s3:
        add_heading(s3.get("title", "第三章 行动计划"), level=1)
        for pk, pl in [("short_term_plan","短期计划（6个月）"),("mid_term_plan","中期计划（6个月-2年）")]:
            plan = sd(s3.get(pk, {}))
            if plan:
                add_heading(pl, level=2, color="2E75B6")
                for g in li_text(plan.get("goals",[])):
                    add_bullet(g, color="375623")
                actions = plan.get("actions", [])
                if actions and isinstance(actions, list):
                    add_table(
                        ["类别", "行动", "资源", "时间", "衡量指标"],
                        [[a.get("category",""), a.get("action",""), a.get("resource",""),
                          a.get("deadline",""), a.get("success_metric","")] for a in actions if isinstance(a, dict)]
                    )
        if s3.get("evaluation_cycle"):
            p = doc.add_paragraph()
            p.add_run("评估周期：").bold = True
            p.runs[0].font.name = "微软雅黑"
            p.add_run(ss(s3["evaluation_cycle"])).font.name = "微软雅黑"
        for m in li_text(s3.get("evaluation_metrics",[])):
            add_bullet(m)
        if s3.get("adjustment_strategy"):
            p = doc.add_paragraph()
            p.add_run("调整策略：").bold = True
            p.runs[0].font.name = "微软雅黑"
            p.add_run(ss(s3["adjustment_strategy"])).font.name = "微软雅黑"
        doc.add_paragraph()

    # ══ 第四章 ══
    s4 = sd(data.get("section4_competitive_strategy", {}))
    if s4:
        add_heading(s4.get("title", "第四章 差异化竞争策略"), level=1)
        if s4.get("core_advantages"):
            add_heading("核心竞争优势", level=2, color="2E75B6")
            for a in li_text(s4["core_advantages"]):
                add_bullet(a)
        if s4.get("differentiation_strategy"):
            add_heading("差异化竞争策略", level=2, color="2E75B6")
            add_paragraph(ss(s4["differentiation_strategy"]))
        if s4.get("improvement_priority"):
            add_heading("重点提升计划", level=2, color="2E75B6")
            rows = []
            for item in s4["improvement_priority"]:
                if isinstance(item, dict):
                    rows.append([f"P{item.get('rank','')} {item.get('item','')}",
                                 item.get("method",""), item.get("expected_outcome","")])
            if rows:
                add_table(["提升项", "方法", "预期效果"], rows)
        doc.add_paragraph()

    # ══ 第五章 ══
    s5 = sd(data.get("section5_resources", {}))
    if s5:
        add_heading(s5.get("title", "第五章 学习资源推荐"), level=1)
        courses = s5.get("online_courses", [])
        if courses and isinstance(courses, list):
            add_heading("推荐在线课程", level=2, color="2E75B6")
            add_table(
                ["平台", "课程", "学习目的", "预计周数"],
                [[c.get("platform",""), c.get("course",""), c.get("purpose",""),
                  str(c.get("duration_weeks",""))] for c in courses if isinstance(c, dict)]
            )
        certs = s5.get("certifications", [])
        if certs and isinstance(certs, list):
            add_heading("推荐证书", level=2, color="2E75B6")
            add_table(
                ["证书", "机构", "优先级", "备考周数"],
                [[c.get("cert_name",""), c.get("issuing_body",""), c.get("priority",""),
                  str(c.get("prep_weeks",""))] for c in certs if isinstance(c, dict)]
            )
        for proj in li_text(s5.get("practice_projects",[])):
            add_bullet(proj)
        if s5.get("networking_advice"):
            add_paragraph(ss(s5["networking_advice"]), color="595959")
        doc.add_paragraph()

    # ══ 总结 ══
    add_heading("总结与激励", level=1)
    add_paragraph(ss(data.get("conclusion", "")), size=11)

    # ── 序列化为字节流 ──
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    from urllib.parse import quote
    filename     = f"{name}_{job}_职业规划报告.docx"
    filename_enc = quote(filename, safe="")
    disposition  = "attachment; filename=report.docx; filename*=UTF-8''" + filename_enc
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": disposition}
    )
