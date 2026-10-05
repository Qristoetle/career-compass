"""
module1_jobs.py — 模块1：岗位数据接口
接口列表：
  GET /api/jobs/list              岗位列表（分页+筛选）
  GET /api/jobs/detail/{job_id}  岗位详情
  GET /api/jobs/graph            完整图谱（节点+边）
  GET /api/jobs/graph/{job_name} 单岗位晋升+转岗路径
  GET /api/jobs/stats            市场统计（薪资/城市/行业）
  GET /api/jobs/profiles/list    10个画像概要
  GET /api/jobs/profiles/{id}    单画像详情
  POST /api/jobs/recommend         AI个性化岗位推荐
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict
import json, os
from functools import lru_cache
from ai_client import chat, clean_json

router = APIRouter()

DATA_DIR = os.environ.get("DATA_DIR", "./data")


@lru_cache(maxsize=1)
def load_jobs():
    path = os.path.join(DATA_DIR, "jobs_cleaned.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["jobs"]


@lru_cache(maxsize=1)
def load_graph():
    path = os.path.join(DATA_DIR, "job_graph.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_profiles():
    path = os.path.join(DATA_DIR, "job_profiles.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["profiles"]


def to_monthly(sal: dict):
    """统一换算为月薪（元）"""
    if sal.get("negotiable"):
        return None
    mn = sal.get("min")
    if mn is None:
        return None
    unit = sal.get("unit", "月")
    if unit == "天":
        return mn * 22
    if unit == "年":
        return mn / 12
    return mn


def fuzzy_match_profile(title: str):
    """根据岗位名称模糊匹配画像"""
    profiles = load_profiles()
    for pkey, pval in profiles.items():
        if title in pkey or pkey.replace("工程师", "") in title:
            return pval
    return None


def fuzzy_match_path(job_name: str, data: dict):
    for key, val in data.items():
        if job_name in key or key in job_name:
            return val
    return None


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs/list
# ═══════════════════════════════════════════════════════════════════
@router.get("/list")
async def get_job_list(
    keyword:    Optional[str] = Query(None),
    industry:   Optional[str] = Query(None),
    city:       Optional[str] = Query(None),
    salary_min: Optional[int] = Query(None),
    salary_max: Optional[int] = Query(None),
    page:       int           = Query(1, ge=1),
    page_size:  int           = Query(20, ge=1, le=100),
):
    jobs = load_jobs()
    filtered = jobs

    if keyword:
        kw = keyword.lower().strip()

        # 第一优先：标题完整包含关键词
        title_match = [j for j in filtered if kw in j.get("title", "").lower()]

        if title_match:
            filtered = title_match
        else:
            # 第二优先：去掉前缀词和后缀词后再搜标题
            # 前缀示例："IT技术支持"→"技术支持"，"高级Java"→"Java"
            # 后缀示例："软件测试工程师"→"软件测试"
            prefix_words = ["it", "高级", "资深", "初级", "中级", "junior", "senior"]
            suffix_words = ["工程师", "开发", "专员", "主管", "经理", "总监",
                            "负责人", "架构师", "顾问", "助理", "实习生"]
            kw_short = kw
            for pw in prefix_words:
                if kw_short.startswith(pw):
                    kw_short = kw_short[len(pw):]
            for sw in suffix_words:
                kw_short = kw_short.replace(sw, "")
            kw_short = kw_short.strip()

            # 去前缀后结果至少3字才用，避免"IT运营"→"运营"太宽泛
            if kw_short and len(kw_short) >= 3:
                short_match = [j for j in filtered if kw_short in j.get("title", "").lower()]
                filtered = short_match if short_match else []
            elif kw_short and len(kw_short) >= 2:
                # 2字时要求完整匹配标题（不做子串），避免噪声
                short_match = [j for j in filtered if kw_short == j.get("title", "").lower()
                               or j.get("title", "").lower().startswith(kw_short)]
                filtered = short_match if short_match else []
            else:
                filtered = title_match  # 空列表
    if industry:
        filtered = [j for j in filtered
                    if any(industry in ind for ind in j.get("industry", []))]
    if city:
        filtered = [j for j in filtered
                    if city in j.get("location", {}).get("city", "")]
    if salary_min is not None:
        filtered = [j for j in filtered
                    if (m := to_monthly(j.get("salary", {}))) is not None and m >= salary_min]
    if salary_max is not None:
        filtered = [j for j in filtered
                    if (m := to_monthly(j.get("salary", {}))) is not None and m <= salary_max]

    total     = len(filtered)
    page_jobs = filtered[(page - 1) * page_size: page * page_size]

    slim = []
    for j in page_jobs:
        sal = j.get("salary", {})
        slim.append({
            "job_id":        j["job_id"],
            "title":         j["title"],
            "city":          j.get("location", {}).get("city", ""),
            "salary_min":    sal.get("min"),
            "salary_max":    sal.get("max"),
            "salary_unit":   sal.get("unit"),
            "negotiable":    sal.get("negotiable", False),
            "company_name":  j.get("company", {}).get("name", ""),
            "company_scale": j.get("company", {}).get("scale", ""),
            "company_type":  j.get("company", {}).get("type", ""),
            "industry":      j.get("industry", []),
            "updated_at":    j.get("updated_at", ""),
        })

    return {"total": total, "page": page, "page_size": page_size, "jobs": slim}


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs/detail/{job_id}
# ═══════════════════════════════════════════════════════════════════
@router.get("/detail/{job_id}")
async def get_job_detail(job_id: str):
    job = next((j for j in load_jobs() if j["job_id"] == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail=f"岗位不存在: {job_id}")
    return {"job": job, "profile": fuzzy_match_profile(job.get("title", ""))}


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs/graph  &  GET /api/jobs/graph/{job_name}
# ═══════════════════════════════════════════════════════════════════
@router.get("/graph")
async def get_full_graph():
    g = load_graph()
    nodes = g["graph"]["nodes"]
    edges = g["graph"]["edges"]
    return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}


@router.get("/graph/{job_name}")
async def get_job_path(job_name: str):
    g      = load_graph()
    vpath  = fuzzy_match_path(job_name, g.get("vertical_paths", {}))
    lpath  = fuzzy_match_path(job_name, g.get("lateral_paths", {}))
    if vpath is None and lpath is None:
        available = list(g.get("vertical_paths", {}).keys())
        raise HTTPException(status_code=404, detail={"message": f"未找到: {job_name}", "available": available})
    return {"job_name": job_name, "vertical_path": vpath or [], "lateral_paths": lpath or []}


class JobNameRequest(BaseModel):
    job_name: str

@router.post("/graph/query")
async def get_job_path_post(req: JobNameRequest):
    """POST版路径查询，专门处理含/等特殊字符的岗位名（如C/C++）"""
    g     = load_graph()
    vpath = fuzzy_match_path(req.job_name, g.get("vertical_paths", {}))
    lpath = fuzzy_match_path(req.job_name, g.get("lateral_paths", {}))
    if vpath is None and lpath is None:
        available = list(g.get("vertical_paths", {}).keys())
        raise HTTPException(status_code=404, detail={"message": f"未找到: {req.job_name}", "available": available})
    return {"job_name": req.job_name, "vertical_path": vpath or [], "lateral_paths": lpath or []}


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs/stats
# ═══════════════════════════════════════════════════════════════════
@router.get("/stats")
async def get_stats(job_title: Optional[str] = Query(None)):
    from collections import Counter
    import statistics

    jobs = load_jobs()
    if job_title:
        jobs = [j for j in jobs if job_title in j.get("title", "")]

    monthly = [to_monthly(j.get("salary", {})) for j in jobs]
    monthly = [s for s in monthly if s is not None]

    buckets = {"3k以下": 0, "3-6k": 0, "6-10k": 0, "10-15k": 0, "15-20k": 0, "20k以上": 0}
    for s in monthly:
        if s < 3000:    buckets["3k以下"]  += 1
        elif s < 6000:  buckets["3-6k"]    += 1
        elif s < 10000: buckets["6-10k"]   += 1
        elif s < 15000: buckets["10-15k"]  += 1
        elif s < 20000: buckets["15-20k"]  += 1
        else:           buckets["20k以上"] += 1

    cities     = Counter(j.get("location", {}).get("city", "未知") for j in jobs)
    industries = Counter(ind for j in jobs for ind in j.get("industry", []))
    scales     = Counter(j.get("company", {}).get("scale", "未知") for j in jobs)

    return {
        "total_records":         len(jobs),
        "salary_distribution":   buckets,
        "salary_median_monthly": round(statistics.median(monthly), 0) if monthly else None,
        "salary_avg_monthly":    round(sum(monthly) / len(monthly), 0) if monthly else None,
        "top_cities":            dict(cities.most_common(10)),
        "top_industries":        dict(industries.most_common(10)),
        "company_scale_dist":    dict(scales.most_common()),
    }


# ═══════════════════════════════════════════════════════════════════
# GET /api/jobs/profiles/list  &  GET /api/jobs/profiles/{profile_id}
# ═══════════════════════════════════════════════════════════════════
@router.get("/profiles/list")
async def list_profiles():
    profiles = load_profiles()
    result = []
    for title, p in profiles.items():
        dims = p.get("dimensions", {})
        result.append({
            "profile_id":        p.get("profile_id"),
            "title":             title,
            "salary_range":      p.get("salary_stats", {}).get("range", ""),
            "top_cities":        p.get("top_cities", [])[:3],
            "education":         p.get("education_requirement", ""),
            "experience":        p.get("experience_requirement", ""),
            "core_skills":       dims.get("professional_skills", {}).get("core_skills", [])[:4],
            "dimension_weights": {k: v.get("score_weight", 0) for k, v in dims.items()},
        })
    return {"profiles": result, "total": len(result)}


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    profiles = load_profiles()
    for title, p in profiles.items():
        if p.get("profile_id") == profile_id or title == profile_id:
            return {"title": title, "profile": p}
    raise HTTPException(status_code=404, detail=f"未找到画像: {profile_id}")


# ═══════════════════════════════════════════════════════════════════
# POST /api/jobs/recommend  — AI 个性化岗位推荐
# ═══════════════════════════════════════════════════════════════════
class RecommendRequest(BaseModel):
    student_info:    Dict
    student_profile: Dict
    top_k:           int = 6

@router.post("/recommend")
async def recommend_jobs(req: RecommendRequest):
    """
    根据学生能力画像，AI 智能推荐最适合的岗位方向。
    返回 top_k 个推荐岗位，每个包含匹配分、推荐理由、优势标签、建议行动。
    """
    # 构建岗位画像摘要（用于AI参考）
    profiles = load_profiles()
    profile_summary = []
    for title, p in profiles.items():
        dims = p.get("dimensions", {})
        core_skills = dims.get("professional_skills", {}).get("core_skills", [])[:5]
        profile_summary.append({
            "岗位名称": title,
            "薪资区间": p.get("salary_stats", {}).get("range", ""),
            "核心技能要求": core_skills,
            "学历要求": p.get("education_requirement", ""),
        })

    system = "你是专业的职业规划顾问。严格按JSON格式输出，只输出JSON不输出其他内容。"
    prompt = f"""根据以下学生信息，从可选岗位列表中推荐最适合的 {req.top_k} 个岗位方向。

【学生基本信息】
姓名：{req.student_info.get("name", "同学")}
专业：{req.student_info.get("major", "")}
学历：{req.student_info.get("education_level", "本科")}

【学生能力画像摘要】
{json.dumps({
    "专业技能得分": req.student_profile.get("dimensions", {}).get("professional_skills", {}).get("score", 0),
    "专业技能优势": req.student_profile.get("dimensions", {}).get("professional_skills", {}).get("strengths", []),
    "证书": req.student_profile.get("dimensions", {}).get("certificates", {}).get("owned", []),
    "竞争力评分": req.student_profile.get("competitiveness_score", 0),
    "适合岗位参考": req.student_profile.get("suitable_jobs", []),
    "核心优势": req.student_profile.get("competitive_advantages", []),
}, ensure_ascii=False)}

【可选岗位列表】
{json.dumps(profile_summary, ensure_ascii=False)}

请推荐最适合该学生的 {req.top_k} 个岗位，按匹配度从高到低排列。
只输出以下JSON，所有字段必须填写真实内容：
{{
  "recommendations": [
    {{
      "job_title": "岗位名称（必须来自可选岗位列表）",
      "match_score": 0-100的整数匹配分,
      "match_level": "高度匹配/较好匹配/基本匹配",
      "reason": "推荐理由（60字，说明为什么适合该学生，结合学生具体特点）",
      "strengths": ["该学生匹配该岗位的3个核心优势标签，每个6字以内"],
      "skill_gaps": ["最需要补充的1-2个技能"],
      "action": "最优先行动建议（30字）",
      "salary_range": "该岗位薪资区间"
    }}
  ]
}}"""

    try:
        text = chat(prompt, system=system, max_tokens=2000)
        result = json.loads(clean_json(text))
        recommendations = result.get("recommendations", [])
        # 验证数据完整性
        for r in recommendations:
            r.setdefault("match_score", 60)
            r.setdefault("strengths", [])
            r.setdefault("skill_gaps", [])
            r.setdefault("action", "")
            r.setdefault("salary_range", "")
        return {
            "student_name": req.student_info.get("name", ""),
            "recommendations": recommendations[:req.top_k],
            "total": len(recommendations),
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"推荐结果解析失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐生成失败: {str(e)}")