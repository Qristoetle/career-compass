"""
step2_profiles_ai_v2.py — 基于真实JD文本的AI岗位画像生成

核心特点：
  - 10个岗位全部来自数据集51种真实岗位名称，无任何手写画像
  - AI读取每个岗位的真实JD后提炼7维度权重、技能要求、市场分析
  - 薪资/城市/公司规模全部从真实数据统计，不估算不手写
  - 答辩说法：「画像100%数据驱动，由AI从真实JD中提炼，无主观手写」

10个岗位（均来自数据集真实岗位名称）：
  P001 Java开发工程师      ← Java（537条）
  P002 软件测试工程师      ← 软件测试+测试工程师（915条）
  P003 C/C++开发工程师     ← C/C++（370条）
  P004 前端开发工程师      ← 前端开发（243条）
  P005 硬件测试工程师      ← 硬件测试（234条）
  P006 实施工程师          ← 实施工程师（478条）
  P007 技术支持工程师      ← 技术支持工程师（482条）
  P008 质量管理工程师      ← 质量管理/测试（138条）
  P009 项目经理            ← 项目经理/主管（80条）
  P010 IT运营专员          ← 游戏运营+社区运营+运营助理/专员（405条）

运行方式：
  export DEEPSEEK_API_KEY="sk-你的密钥"        # Linux/Mac
  $env:DEEPSEEK_API_KEY="sk-你的密钥"          # Windows PowerShell
  python step2_profiles_ai_v2.py
"""

import os, json, time, math, re, datetime
from collections import Counter
from openai import OpenAI

# ─────────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────────
JOBS_CLEANED_PATH = "jobs_cleaned.json"
OUTPUT_PATH       = "job_profiles.json"

DEEPSEEK_API_KEY  = os.environ.get("DEEPSEEK_API_KEY", "")
JD_SAMPLE_COUNT   = 30    # 每个岗位喂给AI的JD条数
JD_CHAR_LIMIT     = 300   # 每条JD截取字符数（避免超token）
RETRY_TIMES       = 3
RETRY_DELAY       = 5
REQUEST_INTERVAL  = 2.0   # 请求间隔（防限速）

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


# ─────────────────────────────────────────────────────────────────
# 10个岗位配置
# dataset_titles: 数据集中真实岗位名称（精确匹配，来自51种之中）
# ─────────────────────────────────────────────────────────────────
JOB_CONFIGS = [
    {
        "profile_id":     "P001",
        "title":          "Java开发工程师",
        "dataset_titles": ["Java"],
    },
    {
        "profile_id":     "P002",
        "title":          "软件测试工程师",
        "dataset_titles": ["软件测试", "测试工程师"],
    },
    {
        "profile_id":     "P003",
        "title":          "C/C++开发工程师",
        "dataset_titles": ["C/C++"],
    },
    {
        "profile_id":     "P004",
        "title":          "前端开发工程师",
        "dataset_titles": ["前端开发"],
    },
    {
        "profile_id":     "P005",
        "title":          "硬件测试工程师",
        "dataset_titles": ["硬件测试"],
    },
    {
        "profile_id":     "P006",
        "title":          "实施工程师",
        "dataset_titles": ["实施工程师"],
    },
    {
        "profile_id":     "P007",
        "title":          "技术支持工程师",
        "dataset_titles": ["技术支持工程师"],
    },
    {
        "profile_id":     "P008",
        "title":          "质量管理工程师",
        "dataset_titles": ["质量管理/测试"],
    },
    {
        "profile_id":     "P009",
        "title":          "项目经理",
        "dataset_titles": ["项目经理/主管"],
    },
    {
        "profile_id":     "P010",
        "title":          "IT运营专员",
        "dataset_titles": ["游戏运营", "社区运营", "运营助理/专员"],
    },
]


# ─────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────

def load_jobs(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["jobs"]


def filter_jobs(jobs: list, dataset_titles: list) -> list:
    """按数据集岗位名称精确匹配"""
    return [j for j in jobs if j.get("title", "") in dataset_titles]


def extract_salary_stats(job_list: list) -> dict:
    mins = [
        j["salary"]["min"] for j in job_list
        if j["salary"].get("min") is not None
        and not (isinstance(j["salary"]["min"], float) and math.isnan(j["salary"]["min"]))
        and j["salary"].get("unit") == "月"
        and not j["salary"].get("negotiable", False)
    ]
    maxs = [
        j["salary"]["max"] for j in job_list
        if j["salary"].get("max") is not None
        and not (isinstance(j["salary"]["max"], float) and math.isnan(j["salary"]["max"]))
        and j["salary"].get("unit") == "月"
        and not j["salary"].get("negotiable", False)
    ]
    if not mins:
        return {"avg_min": None, "avg_max": None, "sample_count": 0, "range": "数据不足"}
    avg_min = int(sum(mins) / len(mins))
    avg_max = int(sum(maxs) / len(maxs)) if maxs else avg_min
    return {
        "avg_min":      avg_min,
        "avg_max":      avg_max,
        "sample_count": len(mins),
        "range":        f"{avg_min // 1000:.0f}k-{avg_max // 1000:.0f}k",
    }


def extract_top_cities(job_list: list, top_n: int = 5) -> list:
    cities = [j["location"]["city"] for j in job_list
              if j["location"]["city"] not in ("未知", "")]
    return [c for c, _ in Counter(cities).most_common(top_n)]


def extract_company_scales(job_list: list) -> dict:
    scales = [j["company"]["scale"] for j in job_list
              if j["company"]["scale"] not in ("未知", "")]
    return dict(Counter(scales).most_common(5))


def build_jd_corpus(job_list: list, sample_n: int, char_limit: int) -> str:
    """
    从真实JD均匀抽样，过滤低质量JD（<50字），拼接成AI可读语料。
    """
    valid = [
        j for j in job_list
        if isinstance(j.get("description"), str)
        and len(j["description"].strip()) >= 50
    ]
    step   = max(1, len(valid) // sample_n)
    sample = valid[::step][:sample_n]
    lines  = []
    for idx, j in enumerate(sample, 1):
        desc = j["description"].strip()[:char_limit]
        lines.append(f"【JD{idx}】{desc}")
    return "\n\n".join(lines)


def clean_json_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*",     "", text)
    text = re.sub(r"\s*```$",     "", text)
    return text.strip()


def call_deepseek(prompt: str, system: str = "", max_tokens: int = 3000) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            resp = client.chat.completions.create(
                model       = "deepseek-chat",
                messages    = messages,
                max_tokens  = max_tokens,
                temperature = 0.3,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"    ⚠ 第{attempt}次调用失败：{e}")
            if attempt < RETRY_TIMES:
                print(f"    {RETRY_DELAY}秒后重试...")
                time.sleep(RETRY_DELAY)
            else:
                raise RuntimeError(f"DeepSeek调用失败（已重试{RETRY_TIMES}次）：{e}")


# ─────────────────────────────────────────────────────────────────
# 核心：AI从真实JD提炼画像
# ─────────────────────────────────────────────────────────────────

def ai_extract_from_jd(
    job_title:      str,
    jd_corpus:      str,
    salary_stats:   dict,
    top_cities:     list,
    company_scales: dict,
    sample_count:   int,
) -> dict:
    """
    把真实JD语料 + 统计数据喂给DeepSeek，
    让AI提炼结构化岗位画像（7维度权重、技能、市场分析）。
    """
    system = (
        "你是一名资深IT行业HR专家。你的任务是从真实招聘JD中提炼岗位能力画像。"
        "请仔细阅读JD，归纳真实的技能要求和能力权重，不要凭空创造JD中没有的内容。"
        "严格按JSON格式输出，不添加任何说明文字，7个维度score_weight之和必须等于100。"
    )

    prompt = f"""以下是来自真实招聘数据集的【{job_title}】岗位JD样本
（数据集共{sample_count}条，以下为均匀抽样）：

{jd_corpus}

---
【已统计的真实市场数据（请直接使用，勿修改数字）】
- 月薪均值：{salary_stats.get('range', '数据不足')}
  最低均值 {salary_stats.get('avg_min')} 元 / 最高均值 {salary_stats.get('avg_max')} 元
  有效薪资样本数：{salary_stats.get('sample_count', 0)} 条
- 岗位需求Top城市：{', '.join(top_cities) if top_cities else '数据不足'}
- 公司规模分布：{json.dumps(company_scales, ensure_ascii=False)}

---
请基于以上JD内容和真实数据，只输出以下JSON结构，不添加任何说明：

{{
  "education_requirement": "从JD高频词中提炼的学历要求",
  "experience_requirement": "从JD中提炼的经验要求",
  "salary_stats": {{
    "avg_min": {salary_stats.get('avg_min', 0)},
    "avg_max": {salary_stats.get('avg_max', 0)},
    "range": "{salary_stats.get('range', '数据不足')}",
    "sample_count": {salary_stats.get('sample_count', 0)},
    "market_note": "30字以内：基于真实数据的薪资市场说明"
  }},
  "top_cities": {json.dumps(top_cities, ensure_ascii=False)},
  "market_analysis": "100字以内：基于JD高频词分析该岗位市场需求、技术趋势、竞争程度",
  "high_freq_keywords": ["从JD中提炼的高频技能关键词，10-15个"],
  "dimensions": {{
    "professional_skills": {{
      "score_weight": 整数（35-45，根据JD中技术要求篇幅占比决定）,
      "description": "从JD提炼的核心技能要求概述，40字以内",
      "core_skills": ["JD中高频出现的必备技能，6-8项，写具体工具/框架/技术名称"],
      "bonus_skills": ["JD中出现的加分技能，3-5项"],
      "scoring_criteria": "评分标准，50字以内"
    }},
    "certificates": {{
      "score_weight": 整数（5-10，根据JD中是否明确要求证书决定）,
      "description": "JD中提及的证书要求，30字以内",
      "recommended_certs": ["JD提及或岗位常见证书，3-4项"],
      "scoring_criteria": "证书评分标准，30字以内"
    }},
    "innovation_ability": {{
      "score_weight": 整数（8-15）,
      "description": "该岗位创新能力要求，从JD提炼，30字以内",
      "indicators": ["可量化的创新能力指标，3项"]
    }},
    "learning_ability": {{
      "score_weight": 整数（10-15）,
      "description": "该岗位学习能力要求，从JD提炼，30字以内",
      "indicators": ["学习能力指标，3项"]
    }},
    "stress_resistance": {{
      "score_weight": 整数（8-12）,
      "description": "JD中体现的压力场景，30字以内",
      "indicators": ["抗压能力指标，3项"]
    }},
    "communication_ability": {{
      "score_weight": 整数（8-12）,
      "description": "该岗位沟通协作要求，从JD提炼，30字以内",
      "indicators": ["沟通能力指标，3项"]
    }},
    "internship_experience": {{
      "score_weight": 整数（5-10）,
      "description": "JD中对实习/经历的要求，30字以内",
      "indicators": ["实习经历评判标准，3项"]
    }}
  }}
}}

约束：
1. core_skills必须是JD中高频出现的具体技术/工具名称，不要写泛泛描述
2. 7个维度score_weight之和必须恰好等于100
3. 薪资数字直接使用已提供的真实统计值，不要改动
"""

    raw     = call_deepseek(prompt, system=system, max_tokens=3000)
    cleaned = clean_json_text(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败：{e}\n原始输出：\n{raw[:500]}")

    # 自动修正权重之和
    dims       = result.get("dimensions", {})
    weight_sum = sum(v.get("score_weight", 0) for v in dims.values())
    if weight_sum != 100:
        diff = 100 - weight_sum
        dims["professional_skills"]["score_weight"] += diff
        print(f"    ⚠ 权重和={weight_sum}，已自动修正 professional_skills += {diff}")

    return result


# ─────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────

def build_profiles(jobs_path: str, output_path: str):
    print("=" * 60)
    print("职途罗盘 — AI岗位画像生成 v2（数据集驱动版）")
    print("=" * 60)

    if not DEEPSEEK_API_KEY:
        raise EnvironmentError(
            "未设置 DEEPSEEK_API_KEY！\n"
            "Linux/Mac:  export DEEPSEEK_API_KEY='sk-xxx'\n"
            "PowerShell: $env:DEEPSEEK_API_KEY='sk-xxx'"
        )

    print(f"\n[准备] 载入：{jobs_path}")
    all_jobs = load_jobs(jobs_path)
    print(f"[准备] 共 {len(all_jobs)} 条岗位")

    profiles = {}
    total    = len(JOB_CONFIGS)

    for i, cfg in enumerate(JOB_CONFIGS, 1):
        pid     = cfg["profile_id"]
        title   = cfg["title"]
        dtitles = cfg["dataset_titles"]

        print(f"\n{'─'*55}")
        print(f"[{i}/{total}] {title}（{pid}）")
        print(f"  数据集岗位：{dtitles}")

        # Step1: 精确匹配真实样本
        matched = filter_jobs(all_jobs, dtitles)
        print(f"  样本数：{len(matched)} 条")
        if not matched:
            print(f"  ✗ 无匹配样本，跳过")
            continue

        # Step2: 统计客观数据
        salary = extract_salary_stats(matched)
        cities = extract_top_cities(matched)
        scales = extract_company_scales(matched)
        print(f"  薪资：{salary['range']}（{salary['sample_count']}条有效数据）")
        print(f"  城市：{cities[:3]}")

        # Step3: 构建JD语料
        corpus    = build_jd_corpus(matched, JD_SAMPLE_COUNT, JD_CHAR_LIMIT)
        jd_count  = corpus.count("【JD")
        print(f"  JD语料：抽样{jd_count}条，{len(corpus)}字符")

        # Step4: AI提炼画像
        print(f"  → 调用 DeepSeek...")
        try:
            ai_data = ai_extract_from_jd(
                job_title      = title,
                jd_corpus      = corpus,
                salary_stats   = salary,
                top_cities     = cities,
                company_scales = scales,
                sample_count   = len(matched),
            )
        except Exception as e:
            print(f"  ✗ 失败：{e}")
            continue

        # Step5: 组装画像（真实统计数据强制覆盖AI输出）
        ai_data["salary_stats"].update({
            "avg_min":      salary["avg_min"],
            "avg_max":      salary["avg_max"],
            "range":        salary["range"],
            "sample_count": salary["sample_count"],
        })
        if cities:
            ai_data["top_cities"] = cities

        profiles[title] = {
            "profile_id":             pid,
            "title":                  title,
            "dataset_titles":         dtitles,
            "data_source":            f"数据集真实JD提炼（{len(matched)}条样本，AI分析）",
            "sample_count":           len(matched),
            "education_requirement":  ai_data.get("education_requirement", ""),
            "experience_requirement": ai_data.get("experience_requirement", ""),
            "salary_stats":           ai_data.get("salary_stats", salary),
            "top_cities":             ai_data.get("top_cities", cities),
            "company_scale_dist":     scales,
            "market_analysis":        ai_data.get("market_analysis", ""),
            "high_freq_keywords":     ai_data.get("high_freq_keywords", []),
            "dimensions":             ai_data.get("dimensions", {}),
        }

        dims       = profiles[title]["dimensions"]
        weight_sum = sum(v.get("score_weight", 0) for v in dims.values())
        skills     = dims.get("professional_skills", {}).get("core_skills", [])
        ok         = "✓" if weight_sum == 100 else f"⚠权重={weight_sum}"
        print(f"  ✓ 完成 | {ok} | 核心技能：{', '.join(skills[:3])}...")

        if i < total:
            time.sleep(REQUEST_INTERVAL)

    # 写出JSON
    output = {
        "meta": {
            "total":           len(profiles),
            "generated_by":    "DeepSeek AI（基于数据集真实JD提炼，无手写内容）",
            "generated_at":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "jd_sample_count": JD_SAMPLE_COUNT,
            "source_jobs":     jobs_path,
        },
        "profiles": profiles,
    }
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 汇总报告
    print(f"\n{'='*60}")
    print("生成完成！")
    print(f"{'='*60}")
    for t, p in profiles.items():
        dims = p.get("dimensions", {})
        ws   = sum(v.get("score_weight", 0) for v in dims.values())
        kws  = p.get("high_freq_keywords", [])[:5]
        print(f"  [{p['profile_id']}] {t}")
        print(f"         样本:{p['sample_count']} | 薪资:{p['salary_stats'].get('range','?')} | 权重和:{ws}")
        print(f"         高频词：{', '.join(kws)}")
    print(f"\n  输出：{output_path}")
    print("=" * 60)
    return profiles


if __name__ == "__main__":
    build_profiles(
        jobs_path   = JOBS_CLEANED_PATH,
        output_path = OUTPUT_PATH,
    )
