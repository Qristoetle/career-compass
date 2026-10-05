"""
第一步：数据清洗脚本
输入：原始 xls 文件（转换后的 xlsx）
输出：jobs_cleaned.json

运行方式：
    python step1_clean.py
"""

import pandas as pd
import re
import json
from datetime import datetime

# ─────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────

def remove_html_tags(text: str) -> str:
    """剥离 HTML 标签，保留纯文本"""
    if not isinstance(text, str):
        return ""
    # 把 <br>、<br/> 换成换行
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # 去掉其余所有标签
    text = re.sub(r'<[^>]+>', '', text)
    # 压缩多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def clean_address(addr: str) -> dict:
    """
    把 '北京-海淀区' / '郑州-None' 等格式
    拆成 city + district 两个字段
    """
    if not isinstance(addr, str):
        return {"city": "未知", "district": ""}
    parts = addr.split('-', 1)
    city = parts[0].strip() if parts[0].strip() else "未知"
    district = parts[1].strip() if len(parts) > 1 else ""
    # 把字符串 'None' 视为空
    if district.lower() == 'none':
        district = ""
    return {"city": city, "district": district}


def parse_salary(raw: str) -> dict:
    """
    把各种薪资格式统一转成月薪（元）的 min/max/unit/negotiable
    支持格式举例：
        4000-6000元         → min=4000  max=6000  unit=月
        1-2万               → min=10000 max=20000 unit=月
        1.5-3万·14薪         → min=15000 max=30000 unit=月  bonus=14
        150-200元/天         → min=150   max=200   unit=天
        面议                → negotiable=True
    """
    if not isinstance(raw, str):
        return {"min": None, "max": None, "unit": "月", "negotiable": True, "raw": str(raw)}

    raw = raw.strip()

    # 面议
    if raw in ('面议', ''):
        return {"min": None, "max": None, "unit": "月", "negotiable": True, "raw": raw}

    result = {"negotiable": False, "raw": raw}

    # 提取 bonus（·13薪 / ·14薪）
    bonus_match = re.search(r'·(\d+)薪', raw)
    result["bonus_months"] = int(bonus_match.group(1)) if bonus_match else None

    # 日薪 → 统一换算为月薪（按22个工作日/月）
    if '元/天' in raw or '/天' in raw:
        nums = re.findall(r'[\d.]+', raw)
        WORK_DAYS = 22
        if len(nums) >= 2:
            result["min"] = round(float(nums[0]) * WORK_DAYS)
            result["max"] = round(float(nums[1]) * WORK_DAYS)
        elif len(nums) == 1:
            result["min"] = result["max"] = round(float(nums[0]) * WORK_DAYS)
        result["unit"] = "月"          # 换算后统一标记为月薪
        result["salary_note"] = "日薪换算"  # 保留换算标记供前端展示
        return result

    # 万单位
    if '万' in raw:
        nums = re.findall(r'[\d.]+', raw)
        if len(nums) >= 2:
            result["min"] = int(float(nums[0]) * 10000)
            result["max"] = int(float(nums[1]) * 10000)
        elif len(nums) == 1:
            result["min"] = result["max"] = int(float(nums[0]) * 10000)
        result["unit"] = "月"
        return result

    # 元单位
    nums = re.findall(r'\d+', raw)
    if len(nums) >= 2:
        result["min"] = int(nums[0])
        result["max"] = int(nums[1])
    elif len(nums) == 1:
        result["min"] = result["max"] = int(nums[0])
    result["unit"] = "月"
    return result


def normalize_industry(raw: str) -> list:
    """
    行业字段标准化：
    1. 按逗号拆分
    2. 去除重复项（忽略大小写）
    3. 去除空字符串
    返回去重后的列表
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    parts = [p.strip() for p in re.split(r'[,，、]', raw)]
    seen = set()
    result = []
    for p in parts:
        key = p.lower()
        if p and key not in seen:
            seen.add(key)
            result.append(p)
    return result


def parse_update_date(raw: str) -> str:
    """
    把 '7月25日' 补全为 '2025-07-25'
    数据来源为应届生招聘，推断年份为 2025
    """
    if not isinstance(raw, str):
        return ""
    m = re.search(r'(\d+)月(\d+)日', raw)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return f"2025-{month:02d}-{day:02d}"
    return raw


# ─────────────────────────────────────────
# IT 行业过滤
# ─────────────────────────────────────────

# ── 行业白名单 ────────────────────────────────────────────
# 只要岗位的 industry 字段命中其中任意一个，就视为 IT 岗位保留
IT_INDUSTRY_WHITELIST = {
    # 核心 IT 行业
    '计算机软件', '互联网', 'IT服务', '计算机硬件',
    # 硬件/通信/电子
    '电子/半导体/集成电路', '通信/网络设备', '物联网',
    '运营商/增值服务', '电子设备制造', '智能硬件', '机器人',
    # 新兴技术
    '人工智能', '云计算/大数据', '网络/信息安全',
    # 互联网垂直领域
    '电子商务', '游戏', '新媒体', '互联网金融/小额贷款',
    '在线招聘/求职', '工业自动化',
    # 技术服务（含大量外包/外派 IT 岗位）
    '专业技术服务',
}

# ── 岗位名称关键词白名单（兜底用）────────────────────────
# 仅当行业属于"中介/外包/咨询"类时才启用此兜底
IT_TITLE_KEYWORDS = [
    # 通用技术岗（精确词，避免误匹配"销售工程师"）
    '开发工程师', '测试工程师', '运维工程师', '硬件工程师',
    '嵌入式工程师', '网络工程师', '安全工程师', '数据工程师',
    '算法工程师', '实施工程师', '技术支持工程师',
    '开发', '程序员', '架构师', '运维', '测试', '算法',
    # 前后端/全栈
    '前端', '后端', '全栈', 'Web开发', 'web开发',
    # 数据方向
    '数仓', '数据库', 'DBA', '爬虫', '数据分析', '数据开发',
    # 产品/设计
    '产品经理', 'UI设计师', 'UX设计', '交互设计',
    # 安全/网络
    '信息安全', '网络安全',
    # 硬件/嵌入式
    '嵌入式', '芯片', 'FPGA', 'PCB设计',
    # 编程语言直接作为岗位名
    'Java', 'Python', 'C++', 'C#', 'Golang',
    'iOS开发', 'Android开发', 'Flutter', 'React', 'Vue',
    # 运维/云
    'DevOps', '云原生', 'SRE',
    # AI/ML
    '机器学习', '深度学习', 'NLP', '计算机视觉',
    # 其他IT
    'IT运维', 'IT支持', '信息技术',
    '自动化测试', '自动化开发',
]

# ── 岗位名称黑名单 ────────────────────────────────────────
# 无论行业如何，这些岗位名称本身就不属于计算机专业岗位，直接过滤
NON_IT_TITLE_BLACKLIST = {
    # 销售类
    '销售工程师', '广告销售', '电话销售', '网络销售',
    '销售助理', '销售运营', '销售专员', '销售顾问',
    # 客服类（非技术）
    '电话客服', '售后客服',
    # 语言类
    '英语翻译', '日语翻译', '韩语翻译', '德语翻译',
    # 法务/行政
    '法务专员/助理', '法务专员', '行政专员',
}

# ── 允许"岗位名称兜底"的行业 ──────────────────────────────
# 仅限中介/外包/咨询性质的行业，这类公司常以乙方身份招IT人员
# 汽车/石油/医疗/农业等行业公司的"工程师"不在此列
IT_TITLE_FALLBACK_ALLOWED_INDUSTRIES = {
    '人力资源服务', '咨询服务', '企业服务', '专业技术服务',
    '科学技术推广', '学术/科研', '在线教育', '教育',
}

# ── 岗位描述中必须包含的 IT 关键词（用于二次验证"科研人员"等边界岗位）──
IT_DESC_KEYWORDS = [
    '计算机', '软件', '编程', '代码', '算法', '数据库', '开发',
    '人工智能', '机器学习', '深度学习', '芯片', '嵌入式', '网络',
    '信息系统', 'IT', '互联网', '云计算', '大数据', '程序',
    'Java', 'Python', 'C++', 'Linux', 'SQL', 'API',
]

# ── 需要描述二次验证的岗位名称 ────────────────────────────
# 这些岗位名称本身含义宽泛，必须通过岗位描述确认是否真的是IT岗
AMBIGUOUS_TITLES = {'科研人员', '研究员', '技术员', '工程师'}


def is_it_job(industry_list: list, title: str, description: str = '') -> tuple:
    """
    判断是否为计算机/IT 相关岗位。
    返回 (bool, reason_str)

    判断顺序：
      0. 岗位名称黑名单：命中直接拒绝，不再走后续逻辑
      1. 行业白名单：精确命中即保留
      2. 含糊岗位名称（科研人员/研究员等）：需描述中包含 IT 关键词才保留
      3. 岗位名称兜底：仅对人力/咨询/企业服务行业启用，且使用精确关键词
    """
    # 0. 岗位名称黑名单 —— 直接过滤，不走任何白名单
    if title in NON_IT_TITLE_BLACKLIST:
        return False, ''

    # 1. 行业白名单 —— 命中即保留
    for ind in industry_list:
        if ind in IT_INDUSTRY_WHITELIST:
            # 对含糊岗位名称额外做描述验证
            if title in AMBIGUOUS_TITLES:
                desc_lower = description.lower()
                has_it_desc = any(kw.lower() in desc_lower for kw in IT_DESC_KEYWORDS)
                if not has_it_desc:
                    return False, ''
            return True, f'行业:{ind}'

    # 2. 行业字段为空时，只靠描述+岗位名关键词判断
    if len(industry_list) == 0:
        for kw in IT_TITLE_KEYWORDS:
            if kw in title:
                return True, f'无行业+岗位名:{kw}'
        return False, ''

    # 3. 岗位名称兜底 —— 仅对中介/外包/咨询行业启用
    industry_set = set(industry_list)
    is_fallback_industry = bool(industry_set & IT_TITLE_FALLBACK_ALLOWED_INDUSTRIES)
    if is_fallback_industry:
        for kw in IT_TITLE_KEYWORDS:
            if kw in title:
                return True, f'行业+岗位名:{kw}'

    return False, ''


# ─────────────────────────────────────────
# 主清洗流程
# ─────────────────────────────────────────

def clean_pipeline(input_path: str, output_path: str):
    print("=" * 60)
    print("开始数据清洗")
    print("=" * 60)

    # ── 读取 ──────────────────────────────
    df = pd.read_excel(input_path, engine='openpyxl')
    raw_count = len(df)
    print(f"[1/7] 读取原始数据：{raw_count} 条")

    # ── Step 1：按岗位编码去重（保留第一条，日期相同时无法区分新旧，保留第一次出现） ──
    # 说明：数据中重复行更新日期完全相同（见质检报告），直接 drop_duplicates
    df = df.drop_duplicates(subset=['岗位编码'], keep='first')
    after_dedup = len(df)
    print(f"[2/7] 按岗位编码去重：剩余 {after_dedup} 条（去除 {raw_count - after_dedup} 条）")

    # ── Step 2：清洗地址 ──────────────────
    addr_parsed = df['地址'].apply(clean_address)
    df['城市']  = addr_parsed.apply(lambda x: x['city'])
    df['区县']  = addr_parsed.apply(lambda x: x['district'])
    none_fixed = (df['区县'] == '').sum()
    print(f"[3/7] 地址清洗完成：{none_fixed} 条补全了区县空值")

    # ── Step 3：剥离岗位详情 HTML ────────
    df['岗位详情_clean'] = df['岗位详情'].apply(remove_html_tags)
    html_rows = df['岗位详情_clean'].apply(lambda x: bool(re.search(r'<', x))).sum()
    print(f"[4/7] HTML 标签剥离完成（残留含'<'行数: {html_rows}）")

    # ── Step 4：薪资结构化 ────────────────
    salary_parsed = df['薪资范围'].apply(parse_salary)
    df['薪资_最低'] = salary_parsed.apply(lambda x: x.get('min'))
    df['薪资_最高'] = salary_parsed.apply(lambda x: x.get('max'))
    df['薪资_单位'] = salary_parsed.apply(lambda x: x.get('unit', '月'))
    df['薪资_面议'] = salary_parsed.apply(lambda x: x.get('negotiable', False))
    negotiable_count = df['薪资_面议'].sum()
    print(f"[5/7] 薪资结构化完成：面议 {negotiable_count} 条，其余已转为数值")

    # ── Step 5：行业标准化 ────────────────
    df['行业_标准'] = df['所属行业'].apply(normalize_industry)
    print(f"[6/7] 行业标准化完成")

    # ── Step 6：公司类型空值填充 ──────────
    df['公司类型'] = df['公司类型'].fillna('未知')
    print(f"[6/8] 公司类型空值填充完成")

    # ── Step 7：过滤非计算机行业岗位 ─────
    # 策略：黑名单 → 行业白名单 → 描述二次验证 → 中介兜底
    it_mask = []
    for _, row in df.iterrows():
        inds  = row['行业_标准'] if isinstance(row['行业_标准'], list) else []
        title = str(row['岗位名称'])    if pd.notna(row['岗位名称'])    else ''
        desc  = str(row['岗位详情_clean']) if pd.notna(row['岗位详情_clean']) else ''
        ok, _ = is_it_job(inds, title, desc)
        it_mask.append(ok)

    df['_is_it'] = it_mask
    before_it = len(df)
    df_removed = df[~df['_is_it']].copy()
    df = df[df['_is_it']].copy()
    print(f"[7/8] IT行业过滤：保留 {len(df)} 条，过滤掉 {before_it - len(df)} 条非IT岗位")

    # ── Step 7b：清洗行业混合标签 ────────
    # 保留 industry 字段中属于 IT 白名单的标签，去掉石油/农业/制造等杂项标签
    # 避免前端岗位卡片上展示"农/林/牧/渔"等无关行业标签
    ALL_IT_TAGS = IT_INDUSTRY_WHITELIST | IT_TITLE_FALLBACK_ALLOWED_INDUSTRIES
    def clean_industry_tags(ind_list):
        kept = [i for i in ind_list if i in ALL_IT_TAGS]
        # 如果过滤后为空（全是非IT标签），保留原始列表（通常不会走到这里）
        return kept if kept else ind_list
    df['行业_标准'] = df['行业_标准'].apply(clean_industry_tags)
    print(f"[7b/8] 行业混合标签清洗完成")

    # ── Step 8：更新日期补全年份 ──────────
    df['更新日期_完整'] = df['更新日期'].apply(parse_update_date)
    print(f"[8/8] 日期补全完成")

    # ── 构建薪资 note 映射（日薪换算标记） ──
    salary_note_map = {}
    for idx, raw_val in df['薪资范围'].items():
        parsed = parse_salary(str(raw_val) if pd.notna(raw_val) else '')
        salary_note_map[idx] = parsed.get('salary_note', '')
    # ── 构建输出记录 ──────────────────────
    records = []
    for _, row in df.iterrows():
        record = {
            "job_id":       str(row['岗位编码']),
            "title":        str(row['岗位名称']) if pd.notna(row['岗位名称']) else "",
            "location": {
                "city":     row['城市'],
                "district": row['区县'],
                "raw":      str(row['地址']) if pd.notna(row['地址']) else ""
            },
            "salary": {
                "min":        row['薪资_最低'],
                "max":        row['薪资_最高'],
                "unit":       row['薪资_单位'],
                "negotiable": bool(row['薪资_面议']),
                "raw":        str(row['薪资范围']),
                "note":       salary_note_map.get(row.name, '')
            },
            "company": {
                "name":        str(row['公司名称']) if pd.notna(row['公司名称']) else "",
                "type":        str(row['公司类型']),
                "scale":       str(row['公司规模'])  if pd.notna(row['公司规模'])  else "未知",
                "description": str(row['公司详情'])  if pd.notna(row['公司详情'])  else ""
            },
            "industry":        row['行业_标准'],
            "description":     row['岗位详情_clean'],
            "updated_at":      row['更新日期_完整'],
            "source_url":      str(row['岗位来源地址']) if pd.notna(row['岗位来源地址']) else ""
        }
        records.append(record)

    # ── 写出 JSON ─────────────────────────
    output = {
        "meta": {
            "total":        len(records),
            "raw_total":    raw_count,
            "cleaned_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_file":  input_path
        },
        "jobs": records
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"清洗完成！")
    print(f"  原始条数：        {raw_count}")
    print(f"  去重后：          {after_dedup}")
    print(f"  过滤非IT后：      {before_it - (before_it - len(df_removed) - len(records) + len(records))} → 保留 {len(records)} 条")
    print(f"  输出文件：        {output_path}")
    print("=" * 60)

    return records


if __name__ == "__main__":
    records = clean_pipeline(
        input_path  = "20260226105856_457.xlsx",
        output_path = "jobs_cleaned.json"
    )