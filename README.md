# 职途罗盘 | Career Compass

基于 AI 的大学生职业规划智能体，整理自服务外包项目正式交付材料。

项目围绕岗位数据、学生画像、人岗匹配与职业报告四个模块，连接招聘信息、岗位能力要求和职业发展路径。此仓库是团队项目的作品集整理版，具体团队分工以原交付材料为准。

## 项目内容

- 岗位数据查询、岗位画像与职业路径知识图谱。
- 学生画像及简历解析。
- 人岗匹配、能力差距分析和职业报告。
- 统一 AI 调用层，通过环境变量配置模型服务。

## 技术栈

React 18、Vite 5、FastAPI、Pydantic、Python、JSON 知识库。

## 目录

```text
backend/         API、业务模块与公开样例知识库
frontend/        React 界面与前端构建配置
data_process/    清洗、岗位画像及图谱生成脚本
docs/            原始架构说明、正式展示 PPT、整理说明
```

查看 [项目展示 PPT](docs/career-compass-presentation.pptx)、[原始架构说明](docs/architecture-original.md) 或 [材料来源与整理记录](docs/migration-notes.md)。原始架构说明描述完整交付项目；本公开版本的数据范围见下文。

## 本地运行

建议使用 Python 3.10 及以上、Node.js 18 及以上。以下命令使用 Windows PowerShell。

后端，在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
cd backend
python main_v2.py
```

在 `backend/.env` 中填写自己的模型服务密钥。AI 生成、简历分析和报告功能需要有效的模型服务配置；未配置时不能完整体验这些功能。

前端，在另一个终端执行：

```powershell
cd frontend
npm ci
npm run dev
```

界面地址为 `http://localhost:5173`，API 文档为 `http://localhost:8000/docs`。前端通过 Vite 将 `/api` 请求转发至本机后端。

## 数据说明

公开版本保留岗位画像和职业路径图谱，并附带 12 条精简岗位样例。样例中的企业名称、企业介绍、岗位原文及来源链接已替换或移除；样例只用于演示，不代表完整招聘市场。

完整招聘 Excel、完整招聘明细、真实 API 密钥和演示视频保存在原始交付材料中，未纳入公开仓库。岗位画像统计来自原交付数据，不能用精简样例重现。数据处理脚本需要自行准备符合其输入格式的数据，并另外安装 `data_process/requirements.txt` 中的依赖。

## 使用与归属

本项目用于学习与作品展示，职业建议需要结合个人情况判断。没有额外授予第三方素材或团队代码的开放许可；相关权益仍归原作者或权利人所有。

## 维护与回归检查

`DATA_DIR` 未设置时使用 `backend/data`；相对路径始终以 `backend` 为基准，绝对路径可用于指定自己的完整数据目录。不要提交真实密钥和完整私有数据。

后台离线检查：安装 `backend/requirements-dev.txt`，在仓库根目录执行 `python -m pytest tests/backend -q`。

页面检查：先在 `frontend` 执行 `npm ci`，再安装 `tests/browser/requirements.txt`、执行 `python -m playwright install chromium`，回到仓库根目录执行 `python -m pytest tests/browser -q`。页面测试使用虚构数据，不调用真实模型；本机可通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指定浏览器。

[本轮维护与测试结果](docs/testing/2026-10-22-maintenance-results.md)。

### 草稿和模型选择

页面将填写信息、分析结果和报告自动保存在当前浏览器，7 天后过期；可使用“清除本机草稿”清除。草稿不会同步到其他设备，共用电脑使用后请清除；浏览器禁用存储或空间不足时会提示保存失败。

模型选择仅影响当前标签页，刷新后保留。API 调用者可通过 `X-AI-Provider` 请求头选择已配置模型；`POST /api/ai/provider` 只校验选择，不再修改服务器的默认配置。

报告生成支持 `POST /api/report/generate?stream=true` 返回逐行 JSON 事件，事件类型为 `section`、`complete` 或 `error`；不加参数仍返回原有 JSON。请求体可传 `section_keys` 指定需要重新生成的章节，页面将保留其他章节和手动编辑的内容。
