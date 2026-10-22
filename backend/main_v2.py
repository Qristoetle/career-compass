"""
main_v2.py — 后端主入口
启动命令：
  python main_v2.py
或：
  uvicorn main_v2:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn, os
from settings import DATA_DIR

from module1_jobs   import router as jobs_router
from module2_student import router as student_router
from module3_match  import router as match_router
from module4_report import router as report_router
from ai_client      import get_provider_info, PROVIDERS, _AUTO_ORDER

app = FastAPI(
    title="职途罗盘 API",
    description="大学生职业规划智能体 — 支持 DeepSeek / Claude 双模型",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router,    prefix="/api/jobs",    tags=["模块1-岗位数据"])
app.include_router(student_router, prefix="/api/student", tags=["模块2-学生画像"])
app.include_router(match_router,   prefix="/api/match",   tags=["模块3-人岗匹配"])
app.include_router(report_router,  prefix="/api/report",  tags=["模块4-职业报告"])


@app.get("/")
async def root():
    return {"status": "running", "version": "2.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    data_dir = DATA_DIR
    files    = ["jobs_cleaned.json", "job_profiles.json", "job_graph.json"]
    checks   = {f: os.path.exists(os.path.join(data_dir, f)) for f in files}
    ai_info  = get_provider_info()

    return {
        "status":    "healthy" if all(checks.values()) and ai_info["key_set"] else "degraded",
        "data_dir":  data_dir,
        "data_files": checks,
        "ai":        ai_info,
    }


# ── 模型切换接口 ───────────────────────────────────────────────────

class ProviderSwitch(BaseModel):
    provider: str

@app.get("/api/ai/provider")
async def get_ai_provider():
    """获取当前使用的 AI 模型"""
    info = get_provider_info()
    return info

@app.post("/api/ai/provider")
async def switch_ai_provider(body: ProviderSwitch):
    """切换 AI 模型（运行时生效，无需重启）"""
    pid = body.provider.strip().lower()
    if pid not in PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的模型 '{pid}'，可选：{', '.join(_AUTO_ORDER)}"
        )
    cfg = PROVIDERS[pid]
    key = os.environ.get(cfg["env_key"], "").strip()
    if not key:
        raise HTTPException(
            status_code=400,
            detail=f"{cfg['name']} 未配置 API Key（{cfg['env_key']}），请先在 .env 中填写"
        )
    # 运行时切换：设置环境变量，ai_client 每次调用都重新读取
    os.environ["AI_PROVIDER"] = pid
    return {
        "provider":    pid,
        "name":        cfg["name"],
        "model":       cfg["model"],
        "key_set":     True,
        "message":     f"已切换到 {cfg['name']}",
    }

@app.get("/api/ai/providers")
async def list_ai_providers():
    """列出所有支持的模型及其配置状态"""
    result = []
    current = get_provider_info()["provider"]
    for pid in _AUTO_ORDER:
        cfg = PROVIDERS[pid]
        key = os.environ.get(cfg["env_key"], "").strip()
        result.append({
            "id":        pid,
            "name":      cfg["name"],
            "model":     cfg["model"],
            "available": bool(key),
            "current":   pid == current,
        })
    return {"providers": result}


if __name__ == "__main__":
    uvicorn.run("main_v2:app", host="0.0.0.0", port=8000, reload=True)