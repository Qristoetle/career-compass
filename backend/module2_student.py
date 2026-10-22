"""
module2_student.py — 模块2：学生画像生成
接口：
  POST /api/student/analyze        手动填写 → 8维度画像
  POST /api/student/upload-resume  简历上传 → 结构化解析
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from validation import RequiredText
from typing import List, Optional, Dict
import json, os, io

from ai_client import chat, clean_json
from starlette.concurrency import run_in_threadpool

router = APIRouter()
from settings import DATA_DIR


def load_profiles():
    path = os.path.join(DATA_DIR, "job_profiles.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["profiles"]


def get_profile_for_job(target_job: str) -> Optional[dict]:
    if not target_job:
        return None
    for title, p in load_profiles().items():
        if target_job in title or title.replace("工程师", "") in target_job:
            return p
    return None


# ── 数据模型 ────────────────────────────────────────────────────────
class InternshipItem(BaseModel):
    company:     str
    position:    str
    duration:    str
    description: Optional[str] = ""
    tech_used:   Optional[List[str]] = []

class ProjectItem(BaseModel):
    name:        str
    role:        str
    description: str
    tech_stack:  Optional[str] = ""
    outcome:     Optional[str] = ""

class StudentInput(BaseModel):
    name:                RequiredText
    major:               RequiredText
    university:          str = ""
    education_level:     str  = "本科"
    graduation_year:     str  = "2025"
    gpa:                 Optional[float] = None
    skills:              List[str] = []
    certificates:        List[str] = []
    internships:         List[InternshipItem] = []
    projects:            List[ProjectItem] = []
    awards:              List[str] = []
    self_introduction:   Optional[str] = None
    target_jobs:         List[RequiredText] = []
    target_cities:       List[str] = []
    expected_salary:     Optional[str] = None
    willing_to_relocate: bool = False
    work_style:          Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# POST /api/student/analyze
# ═══════════════════════════════════════════════════════════════════
@router.post("/analyze")
async def analyze_student(student: StudentInput):
    target_job  = student.target_jobs[0] if student.target_jobs else ""
    job_profile = get_profile_for_job(target_job)
    profile_ctx = (
        json.dumps(job_profile["dimensions"], ensure_ascii=False)
        if job_profile
        else "（无对应岗位画像，请根据通用标准评分）"
    )

    system = "你是专业的HR顾问，擅长大学生职业能力评估。输出格式严格遵守JSON规范，只输出JSON不输出其他内容。"

    prompt = f"""请根据以下学生信息，结合目标岗位评分标准，生成就业能力画像。

【目标岗位满分标准】
{profile_ctx}

【学生信息】
{json.dumps(student.model_dump(), ensure_ascii=False, indent=2)}

只输出以下JSON格式，不添加任何说明：
{{
  "completeness_score": 0-100,
  "competitiveness_score": 0-100,
  "dimensions": {{
    "professional_skills": {{"score":0-100,"level":"初级/中级/高级","strengths":["优势"],"gaps":["欠缺"],"details":"50字"}},
    "certificates": {{"score":0-100,"owned":["已有"],"recommended":["建议获取"],"details":"30字"}},
    "innovation_ability": {{"score":0-100,"evidence":["支撑项"],"details":"30字"}},
    "learning_ability": {{"score":0-100,"evidence":["支撑项"],"details":"30字"}},
    "stress_resistance": {{"score":0-100,"evidence":["支撑项"],"details":"30字"}},
    "communication_ability": {{"score":0-100,"evidence":["支撑项"],"details":"30字"}},
    "internship_experience": {{"score":0-100,"highlights":["亮点"],"details":"30字"}},
    "career_intention": {{"score":0-100,"target_jobs":{json.dumps(student.target_jobs,ensure_ascii=False)},"clarity_level":"明确/较明确/模糊","feasibility":"高/中/低","details":"50字"}}
  }},
  "radar_data": [
    {{"axis":"专业技能","student":0-100,"benchmark":80}},
    {{"axis":"证书","student":0-100,"benchmark":60}},
    {{"axis":"创新能力","student":0-100,"benchmark":70}},
    {{"axis":"学习能力","student":0-100,"benchmark":75}},
    {{"axis":"抗压能力","student":0-100,"benchmark":70}},
    {{"axis":"沟通能力","student":0-100,"benchmark":70}},
    {{"axis":"实习经历","student":0-100,"benchmark":65}},
    {{"axis":"就业意愿","student":0-100,"benchmark":80}}
  ],
  "overall_analysis": "综合分析150字",
  "competitive_advantages": ["优势1","优势2","优势3"],
  "improvement_areas": ["提升方向1","方向2","方向3"],
  "suitable_jobs": ["适合岗位1","岗位2","岗位3"],
  "market_positioning": "市场定位60字"
}}"""

    try:
        text = await run_in_threadpool(chat, prompt, system=system, max_tokens=3000)
        return {
            "student_name": student.name,
            "major":        student.major,
            "target_job":   target_job,
            "profile":      json.loads(clean_json(text)),
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI输出解析失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"画像生成失败: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# POST /api/student/upload-resume
# ═══════════════════════════════════════════════════════════════════
@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".pdf", ".docx", ".txt"):
        raise HTTPException(status_code=400, detail="仅支持 PDF、DOCX、TXT 格式")

    content_bytes = await file.read()
    resume_text   = ""

    if ext == ".txt":
        resume_text = content_bytes.decode("utf-8", errors="ignore")
    elif ext == ".docx":
        try:
            from docx import Document as DocxDoc
            doc = DocxDoc(io.BytesIO(content_bytes))
            resume_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception:
            resume_text = content_bytes.decode("utf-8", errors="ignore")
    elif ext == ".pdf":
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
            resume_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(content_bytes)) as pdf:
                    resume_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            except Exception:
                resume_text = content_bytes.decode("utf-8", errors="ignore")

    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="无法提取简历文本，请检查文件内容或改用手动填写")

    system = "你是简历信息提取专家，严格按JSON格式输出，不添加额外说明。"
    prompt = f"""从以下简历文本中提取结构化信息，只输出JSON：
{{
  "name":"姓名","major":"专业","university":"学校",
  "education_level":"本科/硕士/博士","graduation_year":"毕业年份",
  "gpa":数值或null,"skills":["技能"],"certificates":["证书"],
  "internships":[{{"company":"","position":"","duration":"","description":"","tech_used":[]}}],
  "projects":[{{"name":"","role":"","description":"","tech_stack":"","outcome":""}}],
  "awards":["奖项"],"self_introduction":"自我介绍",
  "target_jobs":["目标岗位"],"target_cities":["目标城市"],"expected_salary":"期望薪资"
}}

简历原文（前4000字）：
{resume_text[:4000]}"""

    try:
        text   = await run_in_threadpool(chat, prompt, system=system, max_tokens=2000)
        parsed = json.loads(clean_json(text))
        return {"filename": filename, "char_count": len(resume_text), "parsed_data": parsed}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"简历解析格式错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"简历解析失败: {str(e)}")
