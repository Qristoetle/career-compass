"""
module3_match.py — 模块3：人岗匹配
接口：
  POST /api/match/score   四维度加权评分
  POST /api/match/batch   批量匹配排名（最多5个岗位）
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import json, os

from ai_client import chat, clean_json

router = APIRouter()
DATA_DIR = os.environ.get("DATA_DIR", "./data")

MATCH_LEVELS = [(85,"高度匹配"),(70,"较好匹配"),(55,"基本匹配"),(40,"有差距"),(0,"暂不建议")]

def score_to_level(s):
    for thr, lv in MATCH_LEVELS:
        if s >= thr: return lv
    return "暂不建议"

def load_profiles():
    path = os.path.join(DATA_DIR, "job_profiles.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["profiles"]

def get_profile(job_name):
    for title, p in load_profiles().items():
        if job_name in title or title.replace("工程师","") in job_name:
            return p
    return None


class MatchRequest(BaseModel):
    student_profile:      Dict
    student_info:         Dict
    target_job:           str
    job_profile_override: Optional[Dict] = None

class BatchMatchRequest(BaseModel):
    student_profile: Dict
    student_info:    Dict
    target_jobs:     List[str]


# ═══════════════════════════════════════════════════════════════════
# POST /api/match/score
# ═══════════════════════════════════════════════════════════════════
@router.post("/score")
async def match_score(req: MatchRequest):
    job_profile = req.job_profile_override or get_profile(req.target_job)
    job_ctx = json.dumps(job_profile, ensure_ascii=False) if job_profile else "（无预设画像，请根据岗位名称推断）"

    system = "你是HR专家，严格按JSON格式输出，数字计算准确。"
    prompt = f"""对以下学生与目标岗位进行人岗匹配分析。

【目标岗位】{req.target_job}
【岗位要求画像】
{job_ctx}

【学生基本信息】
{json.dumps(req.student_info, ensure_ascii=False, indent=2)}

【学生能力画像】
{json.dumps(req.student_profile, ensure_ascii=False, indent=2)}

四维度权重固定：基础要求25% + 职业技能40% + 职业素养20% + 发展潜力15%
只输出以下JSON：
{{
  "overall_score": 综合分(四维度加权分之和保留1位小数),
  "match_level": "高度匹配/较好匹配/基本匹配/有差距/暂不建议",
  "dimensions": {{
    "basic_requirements": {{"weight":25,"raw_score":0-100,"weighted_score":raw*0.25,"matched_items":["匹配项"],"gap_items":["差距项"],"analysis":"50字"}},
    "professional_skills": {{"weight":40,"raw_score":0-100,"weighted_score":raw*0.40,"skill_coverage_rate":整数%,"matched_skills":["已掌握"],"missing_skills":["缺失"],"analysis":"80字"}},
    "professional_quality": {{"weight":20,"raw_score":0-100,"weighted_score":raw*0.20,"strengths":["优势"],"weaknesses":["短板"],"analysis":"50字"}},
    "development_potential": {{"weight":15,"raw_score":0-100,"weighted_score":raw*0.15,"potential_indicators":["潜力点"],"analysis":"50字"}}
  }},
  "match_summary": "综合匹配总结150字",
  "top_recommendations": [
    {{"priority":1,"action":"最优先行动","expected_impact":"预期效果","timeline":"1-2个月"}},
    {{"priority":2,"action":"第二行动","expected_impact":"效果","timeline":"2-3个月"}},
    {{"priority":3,"action":"第三行动","expected_impact":"效果","timeline":"3-6个月"}}
  ],
  "improvement_potential": "完成推荐行动后预估分数",
  "alternative_jobs": ["备选岗位1","备选岗位2"]
}}"""

    try:
        text       = chat(prompt, system=system, max_tokens=2500)
        match_data = json.loads(clean_json(text))

        # 服务端校验加权分
        dims = match_data.get("dimensions", {})
        computed = sum(
            dims.get(k, {}).get("weighted_score", 0)
            for k in ["basic_requirements","professional_skills","professional_quality","development_potential"]
        )
        match_data["overall_score_computed"] = round(computed, 1)

        return {"target_job": req.target_job, "has_profile": job_profile is not None, "match_result": match_data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"匹配结果解析失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"匹配评分失败: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# POST /api/match/batch
# ═══════════════════════════════════════════════════════════════════
@router.post("/batch")
async def batch_match(req: BatchMatchRequest):
    if len(req.target_jobs) > 5:
        raise HTTPException(status_code=400, detail="单次最多批量匹配5个岗位")

    results = []
    for job in req.target_jobs:
        try:
            res = await match_score(MatchRequest(
                student_profile=req.student_profile,
                student_info=req.student_info,
                target_job=job,
            ))
            results.append({
                "job":           job,
                "overall_score": res["match_result"].get("overall_score_computed", 0),
                "match_level":   res["match_result"].get("match_level", ""),
                "top_gap":       res["match_result"].get("dimensions", {})
                                     .get("professional_skills", {})
                                     .get("missing_skills", [])[:2],
            })
        except Exception as e:
            results.append({"job": job, "error": str(e)})

    results.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
    return {"rankings": results}
