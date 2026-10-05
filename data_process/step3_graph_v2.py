"""
step3_graph_v3.py — 岗位关联图谱构建（v3，AI驱动版）

改进点：
  - 垂直晋升路径由 AI 结合真实岗位数据集生成，有数据依据
  - 薪资区间、年限、里程碑全部基于数据集统计后交AI分析
  - 支持重新生成单个岗位路径
  - 横向转岗路径保持 v2 版本（已经过验证，质量稳定）

运行方式：
  python step3_graph_v3.py              # 生成全部10个岗位
  python step3_graph_v3.py --job Java   # 只重新生成指定岗位
"""

import json, os, re, sys, time, argparse
from datetime import datetime
from collections import Counter, defaultdict

# ── 加载 .env 文件（兼容脚本在 data/ 或 backend/ 下运行）────────
def _load_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 依次尝试：当前目录 / 上级目录（backend/） / 上上级目录
    candidates = [
        os.path.join(script_dir, ".env"),
        os.path.join(script_dir, "..", ".env"),
        os.path.join(script_dir, "..", "..", ".env"),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        print(f"  ✅ 已加载 .env: {path}")
        return
    print("  ⚠️  未找到 .env 文件，请确认 API Key 已设置为环境变量")

_load_env()

# ── AI调用（复用项目ai_client）──────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from ai_client import chat, clean_json
    print("✅ 使用项目 ai_client")
except ImportError:
    # 备用：直接调OpenAI兼容接口
    def chat(prompt, system="", max_tokens=2000, **kwargs):
        import os
        from openai import OpenAI
        key = (os.environ.get("DEEPSEEK_API_KEY") or
               os.environ.get("ZHIPUAI_API_KEY") or
               os.environ.get("DASHSCOPE_API_KEY"))
        if not key:
            raise ValueError("未找到API Key，请设置 DEEPSEEK_API_KEY 等环境变量")
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    def clean_json(text):
        text = re.sub(r"^```(?:json)?\s*\n?","",text.strip(),flags=re.MULTILINE)
        text = re.sub(r"\n?```\s*$","",text.strip(),flags=re.MULTILINE)
        si,ei = text.find('{'),text.rfind('}')
        return text[si:ei+1] if si!=-1 and ei>si else text

# 自动判断数据目录：
# - 脚本在 backend/ 下运行 → data/ 在 ./data/
# - 脚本在 backend/data/ 下运行 → data/ 就是当前目录 ./
_script_dir = os.path.dirname(os.path.abspath(__file__))
_default_data = _script_dir if os.path.exists(os.path.join(_script_dir, "jobs_cleaned.json")) else os.path.join(_script_dir, "data")
DATA_DIR = os.environ.get("DATA_DIR", _default_data)

# ─────────────────────────────────────────────────────────────────
# 第一步：从真实数据集提取各岗位统计信息
# ─────────────────────────────────────────────────────────────────

# 岗位名映射：图谱岗位名 → 数据集标题列表
JOB_TITLE_MAP = {
    "Java开发工程师":   ["Java"],
    "软件测试工程师":   ["软件测试", "测试工程师"],
    "C/C++开发工程师":  ["C/C++"],
    "前端开发工程师":   ["前端开发"],
    "硬件测试工程师":   ["硬件测试"],
    "实施工程师":       ["实施工程师"],
    "技术支持工程师":   ["技术支持工程师"],
    "质量管理工程师":   ["质量管理/测试"],
    "项目经理":         ["项目经理/主管", "项目专员/助理"],
    "IT运营专员":       ["运营助理/专员", "游戏运营", "社区运营"],
}

def load_jobs_data():
    path = os.path.join(DATA_DIR, "jobs_cleaned.json")
    with open(path, encoding="utf-8") as f:
        raw = re.sub(r'\bNaN\b', 'null', f.read())
    return json.loads(raw)["jobs"]

def extract_job_stats(jobs, job_name):
    """从数据集提取真实统计数据，作为AI生成路径的参考依据"""
    titles = JOB_TITLE_MAP.get(job_name, [job_name])
    matched = [j for j in jobs if j.get("title","") in titles]

    if not matched:
        return None

    # 薪资统计
    sals_min = [j["salary"]["min"] for j in matched
                if j.get("salary") and j["salary"].get("min") and j["salary"]["min"] > 1000]
    sals_max = [j["salary"]["max"] for j in matched
                if j.get("salary") and j["salary"].get("max") and j["salary"]["max"] > 1000]

    avg_min = sum(sals_min)/len(sals_min)/1000 if sals_min else 0
    avg_max = sum(sals_max)/len(sals_max)/1000 if sals_max else 0

    # 薪资分布（按区间）
    sal_buckets = {"5k以下":0,"5-10k":0,"10-15k":0,"15-20k":0,"20-30k":0,"30k以上":0}
    for s in sals_min:
        if s<5000: sal_buckets["5k以下"]+=1
        elif s<10000: sal_buckets["5-10k"]+=1
        elif s<15000: sal_buckets["10-15k"]+=1
        elif s<20000: sal_buckets["15-20k"]+=1
        elif s<30000: sal_buckets["20-30k"]+=1
        else: sal_buckets["30k以上"]+=1

    # 公司规模分布
    scales = Counter(j.get("company",{}).get("scale","未知") for j in matched)

    # 提取职位描述关键词（前20条，各取前300字）
    desc_sample = "\n---\n".join(
        j.get("description","")[:300]
        for j in matched[:20]
        if j.get("description")
    )

    return {
        "job_name":     job_name,
        "sample_count": len(matched),
        "avg_min_salary": round(avg_min, 1),
        "avg_max_salary": round(avg_max, 1),
        "salary_distribution": sal_buckets,
        "company_scales": dict(scales.most_common(5)),
        "desc_sample":  desc_sample[:3000],
    }


# ─────────────────────────────────────────────────────────────────
# 第二步：AI生成垂直晋升路径
# ─────────────────────────────────────────────────────────────────

def generate_vertical_path_with_ai(stats):
    """
    结合真实数据统计，让AI生成有依据的垂直晋升路径
    """
    job_name = stats["job_name"]
    print(f"  🤖 AI生成 [{job_name}] 垂直路径（样本{stats['sample_count']}条）...")

    system = "你是资深HR和职业规划专家，熟悉中国IT行业职业发展路径。严格按JSON格式输出，只输出JSON。"

    prompt = f"""请根据以下【真实招聘数据统计】，为"{job_name}"岗位生成5级垂直晋升路径。

【数据集统计信息（来自{stats['sample_count']}条真实招聘JD）】
- 数据集平均薪资区间：{stats['avg_min_salary']}k - {stats['avg_max_salary']}k（月薪）
- 薪资分布：{json.dumps(stats['salary_distribution'], ensure_ascii=False)}
- 企业规模分布：{json.dumps(stats['company_scales'], ensure_ascii=False)}

【真实JD描述样本（部分，用于理解岗位要求）】
{stats['desc_sample'][:2000]}

请基于以上真实数据，生成5个层级的晋升路径。要求：
1. 薪资区间必须参考数据集统计（入门级对应数据集低端，高级对应高端，向上合理延伸）
2. 典型年限基于行业惯例（应届/0-2年/2-4年/4-7年/7年+）
3. 关键里程碑必须具体、可量化、可验证（避免空泛）
4. 第5级可适度超出数据集范围（代表行业顶尖水平）

只输出以下JSON格式：
{{
  "vertical_path": [
    {{
      "level": 1,
      "level_name": "岗位名称（如：Java实习生/应届）",
      "typical_years": "在校期间",
      "salary_range": "Xk-Yk（参考数据集低端）",
      "key_milestone": "具体可量化的里程碑（30字内）",
      "data_basis": "此级薪资数据依据（如：数据集{stats['avg_min_salary']}k均值推算）"
    }},
    {{"level": 2, "level_name": "...", "typical_years": "0-2年", "salary_range": "...", "key_milestone": "...", "data_basis": "..."}},
    {{"level": 3, "level_name": "...", "typical_years": "2-4年", "salary_range": "...", "key_milestone": "...", "data_basis": "..."}},
    {{"level": 4, "level_name": "...", "typical_years": "4-7年", "salary_range": "...", "key_milestone": "...", "data_basis": "..."}},
    {{"level": 5, "level_name": "...", "typical_years": "7年+",  "salary_range": "...", "key_milestone": "...", "data_basis": "..."}}
  ]
}}"""

    for attempt in range(3):
        try:
            text   = chat(prompt, system=system, max_tokens=1500)
            result = json.loads(clean_json(text))
            path   = result.get("vertical_path", result)

            # 验证数据完整性
            if not isinstance(path, list) or len(path) < 5:
                raise ValueError(f"路径数量不足: {len(path) if isinstance(path,list) else '非列表'}")

            for lv in path:
                if not all(k in lv for k in ["level","level_name","typical_years","salary_range","key_milestone"]):
                    raise ValueError(f"第{lv.get('level','?')}级字段不完整")

            print(f"    ✅ 生成成功，{len(path)}个层级")
            # 打印数据依据，方便验证
            for lv in path:
                basis = lv.get("data_basis", "")
                print(f"    L{lv['level']} {lv['level_name']}: {lv['salary_range']} | {basis}")
            return path

        except Exception as e:
            print(f"    ⚠️  第{attempt+1}次尝试失败: {e}")
            if attempt < 2:
                time.sleep(2)

    # 最终失败，返回基于数据统计的兜底路径
    print(f"    ❌ AI生成失败，使用数据推算兜底路径")
    return _fallback_path(job_name, stats)


def _fallback_path(job_name, stats):
    """AI失败时，根据真实数据统计生成兜底路径"""
    lo = stats["avg_min_salary"]
    hi = stats["avg_max_salary"]
    # 按层级推算薪资（入门60%，初级80%，中级120%，高级180%，专家250%）
    return [
        {"level":1,"level_name":f"{job_name[:2]}实习生/应届",
         "typical_years":"在校期间","salary_range":f"{lo*0.5:.0f}k-{lo*0.7:.0f}k",
         "key_milestone":"完成基础任务；通过试用期考核","data_basis":f"数据集均值{lo}k的50-70%"},
        {"level":2,"level_name":f"初级{job_name}",
         "typical_years":"0-2年","salary_range":f"{lo*0.8:.0f}k-{hi*0.9:.0f}k",
         "key_milestone":"独立完成常规工作任务","data_basis":f"数据集均值{lo}k-{hi}k区间"},
        {"level":3,"level_name":f"{job_name}",
         "typical_years":"2-4年","salary_range":f"{hi*0.9:.0f}k-{hi*1.3:.0f}k",
         "key_milestone":"负责核心模块；能指导初级","data_basis":f"数据集均值{hi}k的90-130%"},
        {"level":4,"level_name":f"高级{job_name}",
         "typical_years":"4-7年","salary_range":f"{hi*1.3:.0f}k-{hi*2.0:.0f}k",
         "key_milestone":"主导技术方案；团队管理","data_basis":f"数据集均值{hi}k的130-200%"},
        {"level":5,"level_name":f"{job_name[:2]}总监/专家",
         "typical_years":"7年+","salary_range":f"{hi*2.0:.0f}k-{hi*3.5:.0f}k",
         "key_milestone":"部门战略；技术方向引领","data_basis":f"数据集均值{hi}k的200-350%"},
    ]


# ─────────────────────────────────────────────────────────────────
# 横向转岗路径（保留v2高质量版本，已经过人工审核）
# ─────────────────────────────────────────────────────────────────

LATERAL_PATHS = {
    "Java开发工程师": [
        {"target":"软件测试工程师","difficulty":"较易",
         "reason":"Java开发对系统逻辑理解深，能快速掌握测试方法；开发转测试是常见路径",
         "required_skills":["测试用例设计","接口测试（Postman）","自动化测试基础（pytest/JUnit）"],
         "transition_period":"3-6个月","tips":"建议先做白盒测试/开发自测，再逐步向独立测试岗过渡"},
        {"target":"项目经理","difficulty":"中等",
         "reason":"Java开发积累了项目执行经验和技术判断力，是技术型PM的天然路径",
         "required_skills":["PMP项目管理认证","项目计划制定","需求管理","风险识别与控制"],
         "transition_period":"6-12个月","tips":"考取PMP证书后薪资通常提升20-30%，建议3-5年开发经验后转型"},
        {"target":"实施工程师","difficulty":"较易",
         "reason":"Java开发具备代码理解和系统调试能力，是实施岗位的核心竞争力",
         "required_skills":["系统部署与配置","数据库操作（SQL）","客户沟通与培训","文档编写"],
         "transition_period":"2-4个月","tips":"实施岗位出差多但压力小于开发，适合追求工作生活平衡的开发者"},
        {"target":"技术支持工程师","difficulty":"较易",
         "reason":"开发背景使技术支持能快速定位和解决技术问题，是技术支持的核心优势",
         "required_skills":["产品知识积累","客户服务意识","问题排查方法论","工单管理系统"],
         "transition_period":"1-3个月","tips":"此路径技术压力降低，但需要提升沟通耐心；适合转型过渡期"},
    ],
    "软件测试工程师": [
        {"target":"Java开发工程师","difficulty":"中等",
         "reason":"测试人员对系统逻辑有全面理解，具备成为后端开发的思维基础",
         "required_skills":["Java编程（Spring Boot）","数据库开发（MySQL）","RESTful API设计","Git工作流"],
         "transition_period":"10-15个月","tips":"建议先做测试开发（SDET），以测试开发身份逐步向纯开发靠拢"},
        {"target":"质量管理工程师","difficulty":"较易",
         "reason":"软件测试与质量管理核心理念相通，技能高度互补",
         "required_skills":["质量管理体系（ISO9001）","质量数据分析","流程改进方法（PDCA）","质量报告编写"],
         "transition_period":"4-8个月","tips":"考取CQE（质量工程师认证）有助于快速进入质量管理领域"},
        {"target":"项目经理","difficulty":"中等",
         "reason":"测试工程师参与完整项目生命周期，对项目风险和质量管控有深刻理解",
         "required_skills":["PMP认证","项目计划与执行","跨团队沟通协调","测试质量指标体系"],
         "transition_period":"6-12个月","tips":"测试背景的PM在质量管控上有天然优势，适合技术型项目管理岗"},
        {"target":"IT运营专员","difficulty":"较易",
         "reason":"测试人员具备严谨的逻辑分析能力和用户视角，是运营工作的核心素质",
         "required_skills":["数据分析（Excel/SQL）","用户行为分析","运营活动策划","内容审核经验"],
         "transition_period":"3-6个月","tips":"游戏测试转游戏运营是业内最常见路径，行业知识可直接复用"},
    ],
    "C/C++开发工程师": [
        {"target":"硬件测试工程师","difficulty":"较易",
         "reason":"C/C++开发积累的底层系统知识和调试经验，是硬件测试的核心技术基础",
         "required_skills":["硬件测试仪器使用","测试方案设计","信号分析基础","测试报告编写"],
         "transition_period":"3-6个月","tips":"嵌入式方向C++开发转硬件测试最自然，两者技术栈高度重叠"},
        {"target":"Java开发工程师","difficulty":"中等",
         "reason":"C/C++的编程基础扎实，学习Java语法成本低；但需补充Java生态知识",
         "required_skills":["Java语法与特性","Spring Boot框架","JVM调优基础","Maven/Gradle构建工具"],
         "transition_period":"4-8个月","tips":"C++开发者学Java上手很快，重点在补充Web开发和中间件知识"},
        {"target":"质量管理工程师","difficulty":"中等",
         "reason":"C/C++开发对系统性能和可靠性要求高，与质量管理思维高度契合",
         "required_skills":["质量检测流程","FMEA失效分析","6Sigma基础","质量管理体系"],
         "transition_period":"6-10个月","tips":"嵌入式/汽车电子方向的C++开发转质量管理在制造业非常受欢迎"},
        {"target":"技术支持工程师","difficulty":"较易",
         "reason":"C/C++的底层调试能力使技术支持能快速定位复杂技术问题",
         "required_skills":["产品知识体系","客户问题诊断流程","技术文档编写","远程支持工具"],
         "transition_period":"2-4个月","tips":"工业设备、嵌入式产品的技术支持岗特别看重C/C++背景"},
    ],
    "前端开发工程师": [
        {"target":"Java开发工程师","difficulty":"中等",
         "reason":"前端已有完整的Web知识，补充后端语言和数据库即可打通全栈",
         "required_skills":["Java/Python后端语言","Spring Boot框架","MySQL数据库设计","RESTful API设计"],
         "transition_period":"6-12个月","tips":"建议从Node.js切入，语言语法与JS接近，学习曲线最平缓"},
        {"target":"IT运营专员","difficulty":"较易",
         "reason":"前端对用户体验有深刻理解，是互联网运营的核心竞争力",
         "required_skills":["数据分析（SQL/Excel）","用户行为分析","内容运营策略","A/B测试方法"],
         "transition_period":"3-6个月","tips":"前端转增长运营/用户运营薪资相近，但工作强度和压力通常更低"},
        {"target":"项目经理","difficulty":"中等",
         "reason":"前端有技术背景，理解产品实现可行性，是技术型PM的优势",
         "required_skills":["需求分析与文档撰写","原型工具（Axure/Figma）","跨部门沟通协调","项目进度管理"],
         "transition_period":"6-12个月","tips":"互联网公司实习做项目助理是最佳过渡路径"},
        {"target":"软件测试工程师","difficulty":"较易",
         "reason":"前端开发熟悉UI交互逻辑，转型为测试工程师能快速建立用户视角测试思维",
         "required_skills":["功能测试方法","UI自动化测试（Selenium）","测试用例设计","Bug管理工具"],
         "transition_period":"3-5个月","tips":"前端背景做UI自动化测试有天然优势，是薪资提升较快的测试方向"},
    ],
    "硬件测试工程师": [
        {"target":"质量管理工程师","difficulty":"较易",
         "reason":"硬件测试与质量管理工作高度重叠，是最自然的横向发展方向",
         "required_skills":["质量体系认证（ISO9001）","FMEA/8D分析方法","供应商审核","质量数据统计分析"],
         "transition_period":"3-6个月","tips":"制造业/电子行业中硬件测试转质量管理是最常见的职业路径"},
        {"target":"技术支持工程师","difficulty":"较易",
         "reason":"硬件测试积累的产品知识和故障排查经验是技术支持的核心能力",
         "required_skills":["售后服务流程","客户沟通技巧","远程诊断技术","维修知识（初级）"],
         "transition_period":"2-4个月","tips":"消费电子/通信设备领域的技术支持特别需要硬件测试背景"},
        {"target":"实施工程师","difficulty":"中等",
         "reason":"硬件测试工程师熟悉设备部署和调试，与实施工程师的工作内容高度相关",
         "required_skills":["系统集成与部署","客户培训能力","项目文档管理","跨地区出差适应性"],
         "transition_period":"4-8个月","tips":"物联网/工业自动化方向的实施岗位特别欢迎硬件测试背景"},
        {"target":"C/C++开发工程师","difficulty":"较难",
         "reason":"硬件测试积累了底层硬件知识，补充C/C++开发能力可转嵌入式开发",
         "required_skills":["C/C++编程","嵌入式系统开发","RTOS基础","硬件驱动开发"],
         "transition_period":"12-18个月","tips":"需要系统学习编程，建议报考嵌入式培训班或读相关方向研究生"},
    ],
    "实施工程师": [
        {"target":"项目经理","difficulty":"较易",
         "reason":"实施经验是项目管理的核心基础，客户积累也是售前的重要资产",
         "required_skills":["PMP项目管理认证","项目计划制定（甘特图）","风险管理","方案报价与商务谈判"],
         "transition_period":"3-6个月","tips":"PMP证书是此方向最直接的敲门砖，考取后薪资通常提升20-30%"},
        {"target":"技术支持工程师","difficulty":"较易",
         "reason":"实施工程师在客户现场积累的问题处理经验与技术支持高度重叠",
         "required_skills":["远程支持技术","工单管理系统","知识库建设","服务SLA管理"],
         "transition_period":"1-3个月","tips":"技术支持比实施出差少，适合希望减少差旅的实施工程师"},
        {"target":"质量管理工程师","difficulty":"中等",
         "reason":"实施过程中积累的项目质量管控经验，与质量管理岗位要求高度匹配",
         "required_skills":["质量管理体系（ISO）","流程审核与改进","质量问题分析（8D/PDCA）","客户满意度管理"],
         "transition_period":"6-10个月","tips":"ToB软件实施背景在质量管理领域有独特优势"},
        {"target":"IT运营专员","difficulty":"中等",
         "reason":"实施工程师熟悉产品功能和用户需求，是互联网产品运营的重要基础",
         "required_skills":["用户运营策略","数据分析工具（SQL/Excel）","内容运营","社区管理"],
         "transition_period":"6-10个月","tips":"企业软件SaaS方向的客户成功/运营岗位特别适合实施工程师转型"},
    ],
    "技术支持工程师": [
        {"target":"实施工程师","difficulty":"较易",
         "reason":"技术支持和实施工作性质相近，都需要产品知识和客户沟通能力",
         "required_skills":["系统部署与配置","项目文档管理","现场实施流程","客户培训技能"],
         "transition_period":"2-4个月","tips":"实施工程师薪资通常高于技术支持10-20%，是技术支持最顺畅的晋升方向"},
        {"target":"质量管理工程师","difficulty":"中等",
         "reason":"技术支持积累的问题案例库和分析方法，是质量改进的重要数据来源",
         "required_skills":["质量问题统计分析","PDCA改进方法","质量报告编写","ISO质量体系基础"],
         "transition_period":"5-9个月","tips":"建议先在现岗位建立问题分析数据库，作为转型质量管理的作品集"},
        {"target":"IT运营专员","difficulty":"较易",
         "reason":"技术支持的用户问题处理经验与运营的用户服务思维高度契合",
         "required_skills":["用户行为分析","内容运营（FAQ/帮助中心）","社区运营","数据分析基础"],
         "transition_period":"3-6个月","tips":"游戏/互联网产品的技术支持转运营是高频路径，行业知识可直接复用"},
        {"target":"项目经理","difficulty":"中等",
         "reason":"技术支持具备跨部门协调和客户沟通经验，是项目管理的重要基础",
         "required_skills":["PMP项目管理认证","项目计划工具（MS Project）","风险识别与应对","干系人管理"],
         "transition_period":"8-14个月","tips":"考取PMP后可申请公司内部项目协调岗位，逐步过渡到项目经理"},
    ],
    "质量管理工程师": [
        {"target":"软件测试工程师","difficulty":"中等",
         "reason":"质量管理的测试思维与软件测试高度相通，IT化是质量工程师的热门转型方向",
         "required_skills":["软件测试基础（功能/接口测试）","测试工具（Jira/TestRail）","自动化测试入门","编程基础（Python）"],
         "transition_period":"6-12个月","tips":"互联网/软件行业的软件测试岗位薪资通常高于传统制造业质量管理"},
        {"target":"项目经理","difficulty":"中等",
         "reason":"质量管理工程师熟悉流程控制和风险管理，是项目管理的核心能力",
         "required_skills":["PMP项目管理认证","项目计划制定","多方协调沟通","项目风险管理"],
         "transition_period":"6-10个月","tips":"质量背景的PM在制造业/工程项目中有明显优势"},
        {"target":"实施工程师","difficulty":"较易",
         "reason":"质量管理的流程规范能力与实施工程师的现场交付工作高度互补",
         "required_skills":["软件系统操作能力","客户培训技巧","现场问题处理","项目文档规范"],
         "transition_period":"4-8个月","tips":"企业管理软件（ERP/MES）的实施岗位特别看重质量管理背景"},
        {"target":"硬件测试工程师","difficulty":"较易",
         "reason":"质量管理的检测方法与硬件测试工作重叠度高，技能可直接迁移",
         "required_skills":["硬件测试仪器操作","测试方案设计","电子/通信基础知识","测试数据分析"],
         "transition_period":"4-8个月","tips":"制造业质量工程师转电子产品硬件测试，薪资和发展空间通常有所提升"},
    ],
    "项目经理": [
        {"target":"IT运营专员","difficulty":"较易",
         "reason":"项目经理的统筹协调能力与运营管理高度契合，是互联网方向的常见转型",
         "required_skills":["产品运营思维","数据分析（SQL/Excel）","用户增长策略","内容/社区管理"],
         "transition_period":"3-6个月","tips":"互联网公司的产品运营岗位欢迎有项目管理背景的候选人"},
        {"target":"实施工程师","difficulty":"较易",
         "reason":"项目经理对项目交付流程熟悉，转型实施工程师可快速胜任现场交付",
         "required_skills":["系统部署与配置","客户沟通与培训","现场问题应急处理","技术文档整理"],
         "transition_period":"2-4个月","tips":"ToB软件公司的实施项目经理岗位是两者的结合，薪资有竞争力"},
        {"target":"技术支持工程师","difficulty":"较易",
         "reason":"项目经理的多方协调经验在技术支持场景中极有价值",
         "required_skills":["产品知识积累","服务级别管理（SLA）","客户关系维护","问题升级处理机制"],
         "transition_period":"2-3个月","tips":"大型软件厂商的高级技术支持/客户成功经理岗位，薪资与项目经理相当"},
        {"target":"质量管理工程师","difficulty":"中等",
         "reason":"项目经理熟悉质量管控和流程规范，具备转型质量管理的知识基础",
         "required_skills":["质量体系认证（ISO）","质量审核方法","流程设计与优化","质量数据分析"],
         "transition_period":"6-10个月","tips":"软件项目经理转型质量管理，可以专注于软件质量方向（CMM/CMMI）"},
    ],
    "IT运营专员": [
        {"target":"项目经理","difficulty":"中等",
         "reason":"运营专员积累的多方协调和数据分析能力，是项目管理的重要基础",
         "required_skills":["PMP项目管理认证","项目计划与执行","需求分析","干系人沟通管理"],
         "transition_period":"8-14个月","tips":"运营背景的PM在互联网产品项目中有独特优势，适合用户侧项目"},
        {"target":"软件测试工程师","difficulty":"中等",
         "reason":"运营专员对产品功能和用户体验有深刻理解，是测试工作的重要视角",
         "required_skills":["功能测试基础","测试用例设计","Bug管理工具（Jira）","用户场景还原能力"],
         "transition_period":"6-10个月","tips":"游戏运营转游戏测试是高频路径，产品知识可直接复用"},
        {"target":"技术支持工程师","difficulty":"较易",
         "reason":"运营专员积累了大量用户问题处理经验，与技术支持工作性质高度相近",
         "required_skills":["技术问题处理流程","工单系统操作","产品深度知识","客户服务规范"],
         "transition_period":"2-4个月","tips":"互联网产品的技术客服/用户成功岗位是两者的交叉点，入门门槛低"},
        {"target":"实施工程师","difficulty":"中等",
         "reason":"运营专员对产品使用有深入了解，是软件实施培训的核心素质",
         "required_skills":["系统配置与部署基础","客户培训技能","业务流程梳理","项目跟进能力"],
         "transition_period":"5-9个月","tips":"SaaS产品的客户成功/实施专员岗位特别欢迎运营背景的候选人"},
    ],
}


# ─────────────────────────────────────────────────────────────────
# 第三步：构建图结构（与v2完全兼容）
# ─────────────────────────────────────────────────────────────────

def build_graph(vertical_paths, lateral_paths):
    nodes, edges, node_id_map, nid = [], [], {}, 0

    for job_title, levels in vertical_paths.items():
        for lv in levels:
            key = f"{job_title}__{lv['level']}"
            node_id_map[key] = nid
            nodes.append({
                "id": nid, "label": lv["level_name"],
                "job_family": job_title, "level": lv["level"],
                "salary_range": lv["salary_range"],
                "years": lv["typical_years"],
                "milestone": lv["key_milestone"],
                "node_type": "vertical",
            })
            nid += 1

    for job_title, levels in vertical_paths.items():
        for i in range(len(levels) - 1):
            src = node_id_map[f"{job_title}__{levels[i]['level']}"]
            tgt = node_id_map[f"{job_title}__{levels[i+1]['level']}"]
            edges.append({"source":src,"target":tgt,"type":"vertical","label":"晋升"})

    node_jobs = set(n["job_family"] for n in nodes)
    for src_job, laterals in lateral_paths.items():
        src_key = f"{src_job}__2"
        if src_key not in node_id_map:
            continue
        for lat in laterals:
            tgt_key = f"{lat['target']}__2"
            if tgt_key not in node_id_map:
                continue
            edges.append({
                "source": node_id_map[src_key],
                "target": node_id_map[tgt_key],
                "type": "lateral",
                "difficulty": lat["difficulty"],
                "transition_period": lat["transition_period"],
                "label": f"转岗→{lat['target']}",
            })

    return {"nodes": nodes, "edges": edges}


# ─────────────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=str, default=None, help="只重新生成指定岗位（如：Java开发工程师）")
    parser.add_argument("--no-ai", action="store_true", help="跳过AI，使用数据推算兜底路径（测试用）")
    args = parser.parse_args()

    print("=" * 60)
    print("构建岗位关联图谱 v3（AI驱动版）")
    print("=" * 60)

    # 加载数据
    print("\n📂 加载数据集...")
    jobs_data = load_jobs_data()
    print(f"  共 {len(jobs_data)} 条岗位数据")

    job_names = list(LATERAL_PATHS.keys())
    if args.job:
        # 只重新生成指定岗位
        if args.job not in job_names:
            print(f"❌ 未找到岗位：{args.job}")
            print(f"可选岗位：{', '.join(job_names)}")
            sys.exit(1)
        target_jobs = [args.job]
    else:
        target_jobs = job_names

    # 尝试加载已有图谱（用于部分更新）
    out_path = os.path.join(DATA_DIR, "job_graph.json")
    existing_vertical = {}
    if os.path.exists(out_path) and args.job:
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
        existing_vertical = existing.get("vertical_paths", {})
        print(f"  已加载现有图谱（{len(existing_vertical)}个岗位路径），仅更新：{args.job}")

    # 生成垂直路径
    print(f"\n🤖 AI生成垂直晋升路径（共{len(target_jobs)}个岗位）...")
    vertical_paths = dict(existing_vertical)  # 从现有数据开始

    for job_name in target_jobs:
        stats = extract_job_stats(jobs_data, job_name)
        if not stats:
            print(f"  ⚠️  {job_name}：数据集中无匹配样本，跳过AI生成")
            continue

        if args.no_ai:
            vertical_paths[job_name] = _fallback_path(job_name, stats)
            print(f"  📊 [{job_name}] 使用数据推算路径（样本{stats['sample_count']}条）")
        else:
            vertical_paths[job_name] = generate_vertical_path_with_ai(stats)
            time.sleep(0.5)  # 避免触发限速

    # 确保所有岗位都有路径
    for job_name in job_names:
        if job_name not in vertical_paths:
            print(f"  ⚠️  {job_name} 无路径数据，生成兜底路径")
            stats = extract_job_stats(jobs_data, job_name)
            vertical_paths[job_name] = _fallback_path(job_name, stats) if stats else []

    # 构建图结构
    print("\n🔗 构建图结构...")
    graph = build_graph(vertical_paths, LATERAL_PATHS)
    v_edges = [e for e in graph["edges"] if e["type"] == "vertical"]
    l_edges = [e for e in graph["edges"] if e["type"] == "lateral"]

    # 输出
    output = {
        "meta": {
            "generated_at":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version":             "v3 — AI驱动，基于真实数据集",
            "ai_generated":        not args.no_ai,
            "total_jobs":          len(vertical_paths),
            "total_nodes":         len(graph["nodes"]),
            "total_edges":         len(graph["edges"]),
            "vertical_edge_count": len(v_edges),
            "lateral_edge_count":  len(l_edges),
            "data_source":         f"基于 {len(jobs_data)} 条真实招聘JD统计分析",
        },
        "vertical_paths": vertical_paths,
        "lateral_paths":  LATERAL_PATHS,
        "graph":          graph,
    }

    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 图谱生成完成 → {out_path}")
    print(f"  岗位数量：{output['meta']['total_jobs']}")
    print(f"  图节点数：{output['meta']['total_nodes']}")
    print(f"  晋升边数：{output['meta']['vertical_edge_count']}")
    print(f"  转岗边数：{output['meta']['lateral_edge_count']}")
    print(f"  数据来源：{output['meta']['data_source']}")
    print(f"  AI驱动：{'是' if output['meta']['ai_generated'] else '否（数据推算）'}")
    print("=" * 60)