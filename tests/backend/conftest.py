import importlib
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))


@pytest.fixture
def modules(monkeypatch):
    # Never read developer credentials, even when the suite runs next to a .env.
    exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: False if Path(path).name == ".env" else exists(path))
    for key in ("AI_PROVIDER", "DATA_DIR", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "DASHSCOPE_API_KEY", "MOONSHOT_API_KEY", "ZHIPUAI_API_KEY", "DEEPSEEK_MODEL", "CLAUDE_MODEL", "QWEN_MODEL", "KIMI_MODEL", "GLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    names = ["settings", "ai_client", "module1_jobs", "module2_student", "module3_match", "module4_report", "main_v2"]
    for name in names:
        sys.modules.pop(name, None)
    result = {name: importlib.import_module(name) for name in names if name != "settings"}
    yield result
    for module in result.values():
        for value in vars(module).values():
            if hasattr(value, "cache_clear"):
                value.cache_clear()
    for name in names:
        sys.modules.pop(name, None)
