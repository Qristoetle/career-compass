"""
ai_client.py — 统一 AI 调用层 v3.0
支持 5 个主流大模型，只需修改 .env 即可切换，无需改动任何业务代码。

支持模型：
  deepseek  DeepSeek-V3       DEEPSEEK_API_KEY
  claude    Claude 3.5 Sonnet ANTHROPIC_API_KEY
  qwen      通义千问 Plus     DASHSCOPE_API_KEY
  kimi      Kimi moonshot     MOONSHOT_API_KEY
  glm       GLM-4-Flash       ZHIPUAI_API_KEY

切换方式（三选一，优先级从高到低）：
  1. 环境变量  AI_PROVIDER=qwen
  2. .env 文件 AI_PROVIDER=qwen
  3. 自动检测：按上方顺序使用第一个设置了 Key 的模型
"""

import os, re, json, time

from settings import _load_dotenv  # settings loads .env before provider configuration


# ══════════════════════════════════════════════════════════════════
# 模型注册表
# ══════════════════════════════════════════════════════════════════
PROVIDERS = {
    "deepseek": {
        "name":       "DeepSeek",
        "env_key":    "DEEPSEEK_API_KEY",
        "base_url":   "https://api.deepseek.com",
        "model":      os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "max_tokens": 4096,
        "sdk":        "openai",
    },
    "claude": {
        "name":       "Claude (Anthropic)",
        "env_key":    "ANTHROPIC_API_KEY",
        "base_url":   None,
        "model":      os.environ.get("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
        "max_tokens": 4096,
        "sdk":        "anthropic",
    },
    "qwen": {
        "name":       "通义千问",
        "env_key":    "DASHSCOPE_API_KEY",
        "base_url":   "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model":      os.environ.get("QWEN_MODEL", "qwen-plus"),
        "max_tokens": 4096,
        "sdk":        "openai",
    },
    "kimi": {
        "name":       "Kimi (Moonshot)",
        "env_key":    "MOONSHOT_API_KEY",
        "base_url":   "https://api.moonshot.cn/v1",
        "model":      os.environ.get("KIMI_MODEL", "moonshot-v1-32k"),
        "max_tokens": 4096,
        "sdk":        "openai",
    },
    "glm": {
        "name":       "GLM (智谱AI)",
        "env_key":    "ZHIPUAI_API_KEY",
        "base_url":   "https://open.bigmodel.cn/api/paas/v4",
        "model":      os.environ.get("GLM_MODEL", "glm-4"),
        "max_tokens": 4096,
        "sdk":        "openai",
    },
}

_AUTO_ORDER = ["deepseek", "claude", "qwen", "kimi", "glm"]


# ══════════════════════════════════════════════════════════════════
# Provider 解析
# ══════════════════════════════════════════════════════════════════
def _get_provider() -> dict:
    explicit = os.environ.get("AI_PROVIDER", "").strip().lower()

    if explicit:
        if explicit not in PROVIDERS:
            raise ValueError(
                "AI_PROVIDER 配置无效。\n"
                f"可选值: {', '.join(PROVIDERS.keys())}"
            )
        cfg = PROVIDERS[explicit]
        key = os.environ.get(cfg["env_key"], "").strip()
        if not key:
            raise ValueError(
                f"AI_PROVIDER 已设置为 '{explicit}'，但 {cfg['env_key']} 未填写。\n"
                f"请在 .env 中添加：{cfg['env_key']}=你的Key"
            )
        return {**cfg, "api_key": key, "provider_id": explicit}

    # 自动检测
    for pid in _AUTO_ORDER:
        cfg = PROVIDERS[pid]
        key = os.environ.get(cfg["env_key"], "").strip()
        if key:
            return {**cfg, "api_key": key, "provider_id": pid}

    raise ValueError(
        "未找到任何 AI API Key！\n"
        "请在 backend/.env 文件中填写以下任意一个：\n" +
        "\n".join(f"  {PROVIDERS[p]['env_key']}" for p in _AUTO_ORDER)
    )


# ══════════════════════════════════════════════════════════════════
# 核心调用函数（对业务代码完全透明）
# ══════════════════════════════════════════════════════════════════
def chat(
    prompt,
    system="你是专业的职业规划顾问，输出简洁准确。",
    max_tokens=1000,
    temperature=0.7,
    retries=2,
):
    cfg = _get_provider()
    if cfg["sdk"] == "anthropic":
        return _call_anthropic(cfg, prompt, system, max_tokens, temperature, retries)
    else:
        return _call_openai_compat(cfg, prompt, system, max_tokens, temperature, retries)


def _call_openai_compat(cfg, prompt, system, max_tokens, temperature, retries):
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(f"使用 {cfg['name']} 需安装: pip install openai")

    client   = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    last_err = None

    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=cfg["model"],
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=min(max_tokens, cfg["max_tokens"]),
                temperature=temperature,
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"[{cfg['name']}] 调用失败: {last_err}")


def _call_anthropic(cfg, prompt, system, max_tokens, temperature, retries):
    try:
        import anthropic
    except ImportError:
        raise ImportError("使用 Claude 需安装: pip install anthropic")

    client   = anthropic.Anthropic(api_key=cfg["api_key"])
    last_err = None

    for attempt in range(retries):
        try:
            msg = client.messages.create(
                model=cfg["model"],
                max_tokens=min(max_tokens, cfg["max_tokens"]),
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"[{cfg['name']}] 调用失败: {last_err}")


# ══════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════
def clean_json(text):
    """Prefer valid JSON; repair common model syntax only outside quoted strings."""
    import ast

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()
    decoder = json.JSONDecoder()
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    # A surrounding explanation must not trigger repairs to an already valid value.
    starts = [p for p in (text.find("{"), text.find("[")) if p >= 0]
    if starts:
        start = min(starts)
        try:
            _, end = decoder.raw_decode(text, start)
            return text[start:end]
        except json.JSONDecodeError:
            pass
        end = text.rfind("}" if text[start] == "{" else "]")
        if end > start:
            text = text[start:end + 1]
    result, quote, escaped, i = [], None, False, 0
    while i < len(text):
        char = text[i]
        if quote:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            i += 1
            continue
        if char in ('"', "'"):
            quote = char
            result.append(char)
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        else:
            result.append({"，": ",", "：": ":"}.get(char, char))
        i += 1
    # Remove trailing commas with a second string-aware pass.
    text = "".join(result)
    result, quote, escaped = [], None, False
    for i, char in enumerate(text):
        if quote:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
            result.append(char)
        elif char == "," and text[i + 1:].lstrip().startswith(("}", "]")):
            continue
        else:
            result.append(char)
    fixed = "".join(result)
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(fixed)
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed, ensure_ascii=False)
        except (ValueError, SyntaxError):
            pass
    return fixed


def get_provider_info():
    try:
        cfg = _get_provider()
        return {
            "provider":    cfg["provider_id"],
            "name":        cfg["name"],
            "model":       cfg["model"],
            "key_set":     True,
        }
    except Exception as e:
        return {"provider": "none", "name": "未配置", "model": "—",
                "key_set": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════
# 自测（python ai_client.py）
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    info = get_provider_info()
    print(f"\n{'='*50}")
    print(f"  当前模型 : {info['name']}")
    print(f"  版本     : {info.get('model', '—')}")
    print(f"  Key      : {'已配置' if info['key_set'] else '未设置'}")
    print(f"{'='*50}\n")
    if not info["key_set"]:
        print("❌ 未配置 API Key，请检查 .env 文件")
    else:
        print("发送测试请求...")
        try:
            result = chat("用一句话自我介绍", max_tokens=80)
            print(f"✅ 模型回复: {result}\n")
        except Exception as e:
            print(f"❌ 调用失败: {e}\n")
