"""Offline browser regressions using fictional responses from the local test run."""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from urllib.request import urlopen

import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = json.loads(Path(__file__).with_name('fixtures.json').read_text(encoding='utf-8'))


@pytest.fixture(scope='session')
def frontend_url():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        ['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(port), '--strictPort'],
        cwd=ROOT/'frontend', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
    url = f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:
                with urlopen(url, timeout=1):
                    break
            except OSError:
                if process.poll() is not None:
                    pytest.fail('Vite stopped before becoming ready; run npm ci in frontend')
                time.sleep(.1)
        else:
            pytest.fail('Vite did not become ready')
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as p:
        chrome = os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
        default_chrome = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        if not chrome and default_chrome.exists():
            chrome = str(default_chrome)
        instance = p.chromium.launch(**({'executable_path': chrome} if chrome else {}))
        yield instance
        instance.close()


@pytest.fixture
def app(browser, frontend_url):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(4000)
    state = {'requests': [], 'errors': [], 'report_error': False, 'polish_error': False}
    page.on('pageerror', lambda error: state['errors'].append(str(error)))

    def api(route):
        path = route.request.url.split('/api/', 1)[1].split('?', 1)[0]
        payload = route.request.post_data_json if route.request.post_data else None
        state['requests'].append((path, payload))
        status = 200
        if path == 'ai/provider':
            data = {'provider': 'deepseek', 'key_set': True, 'name': 'DeepSeek', 'model': 'deepseek-chat'}
        elif path == 'ai/providers':
            data = {'providers': [{'id': 'deepseek', 'available': True, 'current': True}]}
        elif path == 'student/analyze':
            data = FIXTURES['profile']
        elif path == 'jobs/recommend':
            data = FIXTURES['recommend']
        elif path == 'jobs/list':
            data = {'total': 1, 'page': 1, 'page_size': 12, 'jobs': [{
                'job_id': 'TEST-001', 'title': '前端开发工程师', 'company_name': '虚构测试企业',
                'city': '杭州', 'salary_min': 8000, 'salary_max': 12000, 'industry': ['互联网'],
            }]}
        elif path == 'jobs/profiles/list':
            data = {'profiles': [], 'total': 0}
        elif path == 'match/score':
            data = FIXTURES['match']
        elif path == 'report/generate':
            data = dict(FIXTURES['report'])
            if state['report_error']:
                data.update(has_errors=True, errors=['section5_resources: test failure'])
                data['report'] = {**data['report'], 'section5_resources': '[该章节生成失败，可点击重试或手动编辑]'}
        elif path == 'report/polish':
            status, data = (503, {'detail': '测试：模型服务暂不可用'}) if state['polish_error'] else (200, {'polished': '这是已经润色的测试执行摘要，保留原有结论和行动建议。'})
        elif path.startswith('report/export/'):
            route.fulfill(status=200, content_type='text/markdown', body=json.dumps(payload['report'], ensure_ascii=False))
            return
        else:
            status, data = 404, {'detail': f'Unexpected test request: {path}'}
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data, ensure_ascii=False))

    page.route('**/api/**', api)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.route('https://fonts.gstatic.com/**', lambda route: route.abort())
    page.goto(frontend_url)
    yield page, state
    context.close()


def button(page, name):
    return page.get_by_role('button', name=name, exact=True).first


def complete_profile(page):
    page.get_by_placeholder('张三', exact=True).fill('测试同学')
    page.get_by_placeholder('计算机科学与技术', exact=True).fill('计算机科学与技术')
    button(page, '下一步：生成能力画像 →').click()
    button(page, '生成我的能力画像').click()
    expect(button(page, '下一步：探索岗位 →')).to_be_visible()


def complete_match(page):
    complete_profile(page)
    button(page, '下一步：探索岗位 →').click()
    page.get_by_text('前端开发工程师', exact=True).last.click()
    button(page, '下一步：人岗匹配 →').click()
    button(page, '开始四维度匹配分析').click()
    expect(button(page, '生成职业规划报告 →')).to_be_visible()


def complete_report(page):
    complete_match(page)
    button(page, '生成职业规划报告 →').click()
    button(page, '◇ 生成我的职业规划报告').click()
    expect(button(page, '⬇ Word')).to_be_visible()


def test_whitespace_required_fields_are_rejected(app):
    page, _ = app
    page.get_by_placeholder('张三', exact=True).fill('   ')
    page.get_by_placeholder('计算机科学与技术', exact=True).fill('\u3000\u3000')
    expect(button(page, '下一步：生成能力画像 →')).to_be_disabled()


def test_skill_can_be_added_with_enter(app):
    page, _ = app
    button(page, '技能证书').click()
    field = page.get_by_placeholder(re.compile('技能|Python|JavaScript')).first
    field.fill('TypeScript-回车测试')
    field.press('Enter')
    expect(page.get_by_text('TypeScript-回车测试', exact=False).last).to_be_visible()


@pytest.mark.parametrize('width', [320, 390, 768])
def test_all_steps_fit_narrow_screens(app, width):
    page, state = app
    page.set_viewport_size({'width': width, 'height': 844})
    def fits(step):
        dimensions = page.evaluate('({viewport:innerWidth, width:document.documentElement.scrollWidth})')
        assert dimensions['width'] <= width + 1, (step, dimensions)
    fits('信息录入')
    complete_profile(page)
    fits('能力画像')
    button(page, '下一步：探索岗位 →').click()
    expect(page.get_by_text('前端开发工程师', exact=True).last).to_be_visible()
    fits('岗位探索')
    page.get_by_text('前端开发工程师', exact=True).last.click()
    button(page, '下一步：人岗匹配 →').click()
    button(page, '开始四维度匹配分析').click()
    expect(button(page, '生成职业规划报告 →')).to_be_visible()
    fits('人岗匹配')
    button(page, '生成职业规划报告 →').click()
    button(page, '◇ 生成我的职业规划报告').click()
    expect(button(page, '⬇ Word')).to_be_visible()
    for label in ['执行摘要', '职业探索', '职业目标', '行动计划', '竞争策略', '资源推荐']:
        page.get_by_role('button', name=re.compile(label+'$')).first.click()
        fits(label)
    assert not state['errors']


def test_changed_student_invalidates_old_profile(app):
    page, _ = app
    complete_profile(page)
    page.get_by_role('button', name=re.compile('信息录入$')).click()
    page.get_by_placeholder('计算机科学与技术', exact=True).fill('软件工程')
    button(page, '下一步：生成能力画像 →').click()
    expect(button(page, '生成我的能力画像')).to_be_visible()


def test_report_survives_back_navigation_and_editing(app, tmp_path):
    page, state = app
    complete_report(page)
    page.get_by_role('button', name=re.compile('执行摘要$')).first.click()
    button(page, '✏ 编辑').click()
    page.locator('textarea').fill('这是用户手动修改的执行摘要，返回其他步骤后必须保留。')
    button(page, '✓ 保存').click()
    page.get_by_role('button', name=re.compile('人岗匹配$')).click()
    button(page, '生成职业规划报告 →').click()
    expect(button(page, '⬇ Word')).to_be_visible()
    expect(page.get_by_text('这是用户手动修改的执行摘要，返回其他步骤后必须保留。', exact=True)).to_be_visible()
    with page.expect_download() as event:
        button(page, '⬇ Markdown').click()
    event.value.save_as(tmp_path/'report.md')
    assert '这是用户手动修改的执行摘要' in (tmp_path/'report.md').read_text(encoding='utf-8')
    assert len([p for p, _ in state['requests'] if p == 'report/generate']) == 1


def test_failed_polishing_explains_the_error(app):
    page, state = app
    complete_report(page)
    state['polish_error'] = True
    button(page, '✨ 润色').click()
    expect(page.get_by_text(re.compile('模型服务暂不可用'))).to_be_visible()
    assert not state['errors']


def test_partial_report_failure_has_a_visible_warning(app):
    page, state = app
    complete_match(page)
    state['report_error'] = True
    button(page, '生成职业规划报告 →').click()
    button(page, '◇ 生成我的职业规划报告').click()
    expect(button(page, '⬇ Word')).to_be_visible()
    expect(page.get_by_text(re.compile('部分章节.*失败|部分章节.*未完成'))).to_be_visible()


def test_nested_report_edit_updates_visible_section(app):
    page, _ = app
    complete_report(page)
    page.get_by_role('button', name=re.compile('职业探索$')).first.click()
    button(page, '✏ 编辑').click()
    page.locator('textarea').fill('职业探索正文已修订，保存后必须显示在正确章节中。')
    button(page, '✓ 保存').click()
    expect(page.get_by_text('职业探索正文已修订，保存后必须显示在正确章节中。', exact=True)).to_be_visible()


def test_report_editor_keeps_focus_while_typing(app):
    page, _ = app
    complete_report(page)
    button(page, '✏ 编辑').click()
    field = page.locator('textarea')
    field.fill('')
    field.press_sequentially('React works', delay=15)
    expect(field).to_have_value('React works')


def test_polish_retry_does_not_regenerate_the_whole_report(app):
    page, state = app
    complete_report(page)
    state['polish_error'] = True
    button(page, '✨ 润色').click()
    expect(page.get_by_text(re.compile('模型服务暂不可用'))).to_be_visible()
    state['polish_error'] = False
    button(page, '重试').click()
    expect(page.get_by_text('这是已经润色的测试执行摘要，保留原有结论和行动建议。', exact=True)).to_be_visible()
    assert len([p for p, _ in state['requests'] if p == 'report/generate']) == 1
