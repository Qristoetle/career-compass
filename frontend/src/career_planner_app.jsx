import React, { useState, useEffect, useRef, useCallback } from "react";
import "./responsive.css";

/* ═══════════════════════════════════════════════════════════════
   职途罗盘 — 完整前端 v3
   设计语言：精密仪器 · 深海蓝 · 金色强调 · 数据终端美学
   接入后端 API，不再直连 AI
═══════════════════════════════════════════════════════════════ */

const API = "/api";

function errorMessage(detail, fallback = "请求失败，请重试") {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => {
    const field = (item.loc || []).filter(value => value !== "body").join(".");
    return `${field ? field + "：" : ""}${item.msg || "输入格式不正确"}`;
  }).join("；");
  return fallback;
}

// ── 设计 Token ──────────────────────────────────────────────────
const T = {
  bg0: "#020b18",   // 最深背景
  bg1: "#041020",   // 卡片背景
  bg2: "#071428",   // 悬浮背景
  bg3: "#0b1d35",   // 输入框背景
  line: "#0e2340",   // 边框
  line2: "#142d4a",   // 较亮边框
  text0: "#e8f4ff",   // 主文字
  text1: "#8bb8d8",   // 次文字
  text2: "#4a7a9b",   // 辅助文字
  gold: "#c8952a",   // 金色主题色
  goldL: "#e8b84b",   // 金色高亮
  goldD: "#8a6018",   // 金色暗调
  cyan: "#1aadce",   // 青色
  green: "#0fa86e",   // 绿色
  red: "#d9534f",   // 红色
  orange: "#e07a30",   // 橙色
};

// ── API 工具 ────────────────────────────────────────────────────
async function api(path, opts = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API}${path}`, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...opts,
    });
    clearTimeout(timer);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(errorMessage(err.detail, `请求失败（${res.status}），请稍后重试`));
    }
    return res.json();
  } catch (e) {
    clearTimeout(timer);
    if (e.name === "AbortError") throw new Error("请求超时，请重试");
    throw e;
  }
}

// ── 全局样式注入 ────────────────────────────────────────────────
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body { background: ${T.bg0}; color: ${T.text0}; font-family: 'Noto Sans SC', 'Sora', sans-serif; }

  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: ${T.bg1}; }
  ::-webkit-scrollbar-thumb { background: ${T.gold}44; border-radius: 2px; }

  input, textarea, select {
    outline: none; font-family: inherit;
    background: ${T.bg3};
    border: 1px solid ${T.line2};
    color: ${T.text0};
    border-radius: 6px;
    transition: border-color .2s, box-shadow .2s;
  }
  input:focus, textarea:focus, select:focus {
    border-color: ${T.gold};
    box-shadow: 0 0 0 3px ${T.gold}18;
  }
  button { font-family: inherit; cursor: pointer; border: none; }
  button:disabled { opacity: .45; cursor: not-allowed; }

  @keyframes fadeUp {
    from { opacity:0; transform:translateY(16px); }
    to   { opacity:1; transform:translateY(0); }
  }
  @keyframes pulse {
    0%,100% { opacity:1; }
    50%      { opacity:.4; }
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  @keyframes shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position:  200% 0; }
  }
  @keyframes scanline {
    0%   { transform: translateY(-100%); }
    100% { transform: translateY(100vh); }
  }
  .fade-up { animation: fadeUp .4s ease both; }
  .fade-up-2 { animation: fadeUp .4s .08s ease both; }
  .fade-up-3 { animation: fadeUp .4s .16s ease both; }
`;

// ══════════════════════════════════════════════════════════════════
// 基础原子组件
// ══════════════════════════════════════════════════════════════════

// 通用卡片
function Card({ children, style, glow, onClick, className = "" }) {
  return (
    <div
      onClick={onClick}
      className={className}
      style={{
        background: T.bg1,
        border: `1px solid ${glow ? T.gold + "55" : T.line2}`,
        borderRadius: 10,
        padding: 20,
        boxShadow: glow ? `0 0 20px ${T.gold}18` : "none",
        transition: "all .2s",
        ...(onClick && { cursor: "pointer" }),
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// 按钮
function Btn({ children, onClick, variant = "gold", disabled, size = "md", style }) {
  const sizes = { sm: "7px 14px", md: "10px 22px", lg: "13px 30px" };
  const fontSize = { sm: 12, md: 13, lg: 15 };
  const variants = {
    gold: { background: `linear-gradient(135deg, ${T.gold}, ${T.goldL})`, color: "#020b18", fontWeight: 700 },
    outline: { background: "transparent", border: `1px solid ${T.gold}`, color: T.gold },
    ghost: { background: "transparent", border: `1px solid ${T.line2}`, color: T.text1 },
    danger: { background: `linear-gradient(135deg, ${T.red}, #b02020)`, color: "#fff" },
    cyan: { background: `linear-gradient(135deg, ${T.cyan}, #0d8fa8)`, color: "#020b18", fontWeight: 700 },
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: sizes[size],
        borderRadius: 6,
        fontSize: fontSize[size],
        letterSpacing: ".3px",
        transition: "all .18s",
        ...variants[variant],
        ...style,
      }}
      onMouseEnter={e => { if (!disabled) e.currentTarget.style.filter = "brightness(1.15) translateY(-1px)"; }}
      onMouseLeave={e => { e.currentTarget.style.filter = ""; }}
    >
      {children}
    </button>
  );
}

// 标签
function Tag({ children, color = T.gold, removable, onRemove }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      background: color + "18", color, border: `1px solid ${color}44`,
      borderRadius: 4, padding: "3px 8px", fontSize: 11, lineHeight: 1.4,
    }}>
      {children}
      {removable && (
        <button onClick={onRemove} style={{ background: "none", color: T.red, fontSize: 13, lineHeight: 1, padding: 0, opacity: .7 }}>×</button>
      )}
    </span>
  );
}

// 进度条
function Bar({ value, max = 100, color = T.gold, h = 5, label, sublabel, animated = true }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div style={{ marginBottom: 8 }}>
      {(label || sublabel) && (
        <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          {label && <span style={{ fontSize: 12, color: T.text1 }}>{label}</span>}
          {sublabel && <span style={{ fontSize: 12, color: color, fontFamily: "JetBrains Mono, monospace" }}>{sublabel}</span>}
        </div>
      )}
      <div style={{ height: h, background: T.bg3, borderRadius: h, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`, borderRadius: h,
          background: `linear-gradient(90deg, ${color}cc, ${color})`,
          transition: animated ? "width 1s cubic-bezier(.4,0,.2,1)" : "none",
          boxShadow: `0 0 8px ${color}60`,
        }} />
      </div>
    </div>
  );
}

// 得分环
function Ring({ score, size = 80, color = T.gold, label, thickness = 7 }) {
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const dash = (score / 100) * c;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={T.bg3} strokeWidth={thickness} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={thickness}
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 1.2s cubic-bezier(.4,0,.2,1)", filter: `drop-shadow(0 0 4px ${color}80)` }}
        />
        <text
          x={size / 2} y={size / 2}
          textAnchor="middle" dominantBaseline="central"
          fill={T.text0}
          style={{ transform: "rotate(90deg)", transformOrigin: `${size / 2}px ${size / 2}px`, fontSize: size * .22, fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}
        >
          {score}
        </text>
      </svg>
      {label && <span style={{ fontSize: 11, color: T.text2 }}>{label}</span>}
    </div>
  );
}

// SVG 雷达图
function Radar({ data, size = 260 }) {
  if (!data || data.length === 0) return null;
  const cx = size / 2, cy = size / 2;
  const r = size * 0.35;
  const n = data.length;
  const angle = i => (i * 2 * Math.PI) / n - Math.PI / 2;
  const pt = (i, v) => {
    const a = angle(i), d = (v / 100) * r;
    return [cx + d * Math.cos(a), cy + d * Math.sin(a)];
  };

  const studentPts = data.map((d, i) => pt(i, d.student ?? d.value ?? 0));
  const benchPts = data.map((d, i) => pt(i, d.benchmark ?? 80));
  const toPath = pts => pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ") + "Z";

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* 背景网格 */}
      {[20, 40, 60, 80, 100].map(v => (
        <polygon
          key={v}
          points={data.map((_, i) => pt(i, v).join(",")).join(" ")}
          fill="none" stroke={T.line2} strokeWidth={v === 100 ? .8 : .5}
        />
      ))}
      {/* 辐射线 */}
      {data.map((_, i) => {
        const [x, y] = pt(i, 100);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke={T.line2} strokeWidth=".5" />;
      })}
      {/* 基准线 */}
      <path d={toPath(benchPts)} fill={T.cyan + "10"} stroke={T.cyan} strokeWidth="1" strokeDasharray="3,2" />
      {/* 学生数据 */}
      <path d={toPath(studentPts)} fill={T.gold + "28"} stroke={T.gold} strokeWidth="2" style={{ filter: `drop-shadow(0 0 6px ${T.gold}80)` }} />
      {studentPts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="3.5" fill={T.gold} style={{ filter: `drop-shadow(0 0 3px ${T.gold})` }} />
      ))}
      {/* 标签 */}
      {data.map((d, i) => {
        const a = angle(i), lx = cx + (r + 22) * Math.cos(a), ly = cy + (r + 22) * Math.sin(a);
        return (
          <text key={i} x={lx} y={ly} textAnchor="middle" dominantBaseline="middle"
            fill={T.text1} fontSize="10" fontFamily="Noto Sans SC, sans-serif"
          >
            {d.axis || d.label}
          </text>
        );
      })}
    </svg>
  );
}

// 输入框封装
function Field({ label, children, tip }) {
  return (
    <div>
      <label style={{ display: "block", fontSize: 11, color: T.text2, letterSpacing: ".8px", textTransform: "uppercase", marginBottom: 6, fontFamily: "Sora, sans-serif" }}>
        {label}
      </label>
      {children}
      {tip && <p style={{ fontSize: 11, color: T.text2, marginTop: 4 }}>{tip}</p>}
    </div>
  );
}
function Input({ value, onChange, placeholder, type = "text", style, ...props }) {
  return (
    <input
      type={type} value={value} onChange={onChange} placeholder={placeholder}
      {...props}
      style={{ width: "100%", padding: "9px 12px", fontSize: 13, ...style }}
    />
  );
}
function Textarea({ value, onChange, placeholder, rows = 3 }) {
  return (
    <textarea
      value={value} onChange={onChange} placeholder={placeholder} rows={rows}
      style={{ width: "100%", padding: "9px 12px", fontSize: 13, resize: "vertical" }}
    />
  );
}

// 标签输入组件（动态添加删除）
function TagInput({ label, items = [], onAdd, onRemove, placeholder, color = T.gold }) {
  const [val, setVal] = useState("");
  const add = () => { if (val.trim()) { onAdd(val.trim()); setVal(""); } };
  return (
    <Field label={label}>
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        <Input value={val} onChange={e => setVal(e.target.value)} placeholder={placeholder}
          onKeyDown={e => e.key === "Enter" && (e.preventDefault(), add())} style={{ flex: 1 }} />
        <Btn onClick={add} variant="outline" size="sm">＋添加</Btn>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, minHeight: 28 }}>
        {items.length === 0
          ? <span style={{ fontSize: 12, color: T.text2, padding: "2px 0" }}>暂未添加</span>
          : items.map((item, i) => (
            <Tag key={i} color={color} removable onRemove={() => onRemove(i)}>
              {typeof item === "string" ? item : (item.company || item.name || JSON.stringify(item))}
            </Tag>
          ))
        }
      </div>
    </Field>
  );
}

// 分割线标题
function SectionTitle({ children, icon }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, marginTop: 8 }}>
      {icon && <span style={{ fontSize: 16 }}>{icon}</span>}
      <span style={{ fontSize: 13, fontWeight: 600, color: T.gold, letterSpacing: ".6px", fontFamily: "Sora, sans-serif" }}>{children}</span>
      <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${T.gold}44, transparent)` }} />
    </div>
  );
}

// Loading 遮罩
function Loading({ text = "AI 分析中…" }) {
  return (
    <div style={{ textAlign: "center", padding: "60px 0" }}>
      <div style={{
        width: 48, height: 48, border: `3px solid ${T.line2}`,
        borderTopColor: T.gold, borderRadius: "50%",
        animation: "spin 1s linear infinite", margin: "0 auto 20px",
      }} />
      <p style={{ color: T.text1, fontSize: 14 }}>{text}</p>
      <p style={{ color: T.text2, fontSize: 12, marginTop: 6 }}>通常需要 3-8 秒，请稍候</p>
    </div>
  );
}

// ── [迁移自代码 1] 就业能力画像专用模拟进度加载 ──
function ProfileLoading() {
  const dims = [
    { label: "专业技能", icon: "💻" }, { label: "证书资质", icon: "📜" },
    { label: "创新能力", icon: "💡" }, { label: "学习能力", icon: "📚" },
    { label: "抗压能力", icon: "🧠" }, { label: "沟通能力", icon: "🗣️" },
    { label: "实习经历", icon: "🏢" }, { label: "就业意愿", icon: "🎯" },
  ];
  const [progresses, setProgresses] = useState(() => dims.map(() => 0));
  const [currentIdx, setCurrentIdx] = useState(0);
  const [tip, setTip] = useState("正在初始化分析模型…");
  const tips = ["正在初始化分析模型…", "读取个人信息与技能数据…", "对照岗位标准进行评分…", "生成雷达图数据…", "整合分析结果…"];

  useEffect(() => {
    let idx = 0;
    const tipTimer = setInterval(() => { idx = (idx + 1) % tips.length; setTip(tips[idx]); }, 2200);
    return () => clearInterval(tipTimer);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setProgresses(prev => {
        const next = [...prev];
        for (let i = 0; i < dims.length; i++) {
          if (i < currentIdx) next[i] = 100;
          else if (i === currentIdx) next[i] = Math.min(next[i] + Math.random() * 2.5 + 1.2, 100);
          else next[i] = Math.min(next[i] + Math.random() * 0.4, 20);
        }
        return next;
      });
    }, 300);
    return () => clearInterval(timer);
  }, [currentIdx]);

  useEffect(() => {
    if (progresses[currentIdx] >= 100 && currentIdx < dims.length - 1) {
      setTimeout(() => setCurrentIdx(i => i + 1), 200);
    }
  }, [progresses, currentIdx]);

  const overall = Math.round(progresses.reduce((a, b) => a + b, 0) / dims.length);

  return (
    <div style={{ padding: "32px 24px", background: T.bg1, borderRadius: 14, border: `1px solid ${T.line2}`, marginBottom: 20 }}>
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div style={{ width: 52, height: 52, borderRadius: "50%", background: `conic-gradient(${T.gold} ${overall * 3.6}deg, ${T.line2} 0deg)`, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 14px" }}>
          <div style={{ width: 40, height: 40, borderRadius: "50%", background: T.bg0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, color: T.gold }}>{overall}%</div>
        </div>
        <p style={{ fontSize: 15, fontWeight: 600, color: T.text1, marginBottom: 4 }}>AI 正在分析就业能力画像</p>
        <p style={{ fontSize: 12, color: T.text2 }}>{tip}</p>
      </div>
      <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 20px" }}>
        {dims.map((d, i) => (
          <div key={d.label}>
            <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: progresses[i] >= 100 ? T.green : i === currentIdx ? T.gold : T.text2 }}>{d.icon} {d.label}</span>
              <span style={{ fontSize: 11, color: T.text2 }}>{Math.round(progresses[i])}%</span>
            </div>
            <div style={{ height: 5, background: T.line2, borderRadius: 3, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${progresses[i]}%`, background: progresses[i] >= 100 ? T.green : i === currentIdx ? T.gold : T.line2, transition: "width 0.12s ease" }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── [迁移自代码 1] 人岗匹配专用四维度模拟加载 ──
function MatchLoading() {
  const dims = [
    { label: "基础要求", icon: "📋", weight: "25%" },
    { label: "职业技能", icon: "⚙️", weight: "40%" },
    { label: "职业素养", icon: "🌟", weight: "20%" },
    { label: "发展潜力", icon: "🚀", weight: "15%" },
  ];
  const [progresses, setProgresses] = useState(() => dims.map(() => 0));
  const [currentIdx, setCurrentIdx] = useState(0);
  const [tip, setTip] = useState("正在加载岗位要求…");
  const tips = ["正在加载岗位要求…", "对比基础条件…", "分析技能匹配度…", "评估职业素养…", "计算综合加权得分…"];

  useEffect(() => {
    let idx = 0;
    const timer = setInterval(() => { idx = (idx + 1) % tips.length; setTip(tips[idx]); }, 2800);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setProgresses(prev => {
        const next = [...prev];
        for (let i = 0; i < dims.length; i++) {
          if (i < currentIdx) next[i] = 100;
          else if (i === currentIdx) next[i] = Math.min(next[i] + Math.random() * 2.2 + 1.0, 100);
          else next[i] = Math.min(next[i] + Math.random() * 0.5, 20);
        }
        return next;
      });
    }, 300);
    return () => clearInterval(timer);
  }, [currentIdx]);

  useEffect(() => {
    if (progresses[currentIdx] >= 100 && currentIdx < dims.length - 1) {
      setTimeout(() => setCurrentIdx(i => i + 1), 250);
    }
  }, [progresses, currentIdx]);

  return (
    <div style={{ padding: "32px 24px", background: T.bg1, borderRadius: 14, border: `1px solid ${T.line2}`, marginBottom: 20 }}>
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <p style={{ fontSize: 15, fontWeight: 600, color: T.text1, marginBottom: 4 }}>AI 正在进行四维度匹配分析</p>
        <p style={{ fontSize: 12, color: T.text2 }}>{tip}</p>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {dims.map((d, i) => (
          <div key={d.label}>
            <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontSize: 13, color: progresses[i] >= 100 ? T.green : i === currentIdx ? T.cyan : T.text2 }}>{d.icon} {d.label} ({d.weight})</span>
              <span style={{ fontSize: 11, color: T.text2 }}>{Math.round(progresses[i])}%</span>
            </div>
            <div style={{ height: 6, background: T.line2, borderRadius: 3, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${progresses[i]}%`, background: progresses[i] >= 100 ? T.green : i === currentIdx ? T.cyan : T.line2, transition: "width 0.15s ease" }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── [新增] 职业规划报告专用“文档构建”模拟加载 ──
function ReportLoading() {
  const sections = [
    { label: "执行摘要", icon: "◎", desc: "提炼核心竞争优势与职业定位" },
    { label: "职业探索", icon: "◉", desc: "分析行业趋势与岗位匹配深度" },
    { label: "职业目标", icon: "◆", desc: "规划短期、中期及长期发展路径" },
    { label: "行动计划", icon: "◈", desc: "制定具体的技能提升与实践时间表" },
    { label: "竞争策略", icon: "◇", desc: "构建差异化核心竞争力与面试策略" },
    { label: "资源推荐", icon: "✦", desc: "匹配最相关的课程、证书与项目资源" },
  ];

  const [progresses, setProgresses] = useState(() => sections.map(() => 0));
  const [currentIdx, setCurrentIdx] = useState(0);
  const [tip, setTip] = useState("正在检索全网行业基准数据…");

  const tips = [
    "正在检索全网行业基准数据…",
    "整合人岗匹配分析模型…",
    "调用深度学习模型生成个性化建议…",
    "正在优化报告排版与视觉呈现…",
    "最后核对行动计划的可行性…",
  ];

  // 文字提示轮播
  useEffect(() => {
    let idx = 0;
    const timer = setInterval(() => {
      idx = (idx + 1) % tips.length;
      setTip(tips[idx]);
    }, 3500);
    return () => clearInterval(timer);
  }, []);

  // 进度条逻辑
  useEffect(() => {
    const timer = setInterval(() => {
      setProgresses(prev => {
        const next = [...prev];
        for (let i = 0; i < sections.length; i++) {
          if (i < currentIdx) {
            next[i] = 100;
          } else if (i === currentIdx) {
            // 报告生成较慢，步进设置得小一点，模拟“撰写中”
            next[i] = Math.min(next[i] + Math.random() * 1.8 + 0.8, 100);
          } else {
            next[i] = Math.min(next[i] + Math.random() * 0.3, 10);
          }
        }
        return next;
      });
    }, 400);
    return () => clearInterval(timer);
  }, [currentIdx]);

  useEffect(() => {
    if (progresses[currentIdx] >= 100 && currentIdx < sections.length - 1) {
      setTimeout(() => setCurrentIdx(i => i + 1), 400);
    }
  }, [progresses, currentIdx]);

  const totalProgress = Math.round(progresses.reduce((a, b) => a + b, 0) / sections.length);

  return (
    <div style={{ padding: "40px 30px", background: T.bg1, borderRadius: 16, border: `1px solid ${T.gold}33`, marginBottom: 24, position: "relative", overflow: "hidden" }}>
      {/* 装饰用扫描线 */}
      <div style={{ position: "absolute", inset: 0, background: `linear-gradient(transparent, ${T.gold}05, transparent)`, height: "20%", width: "100%", animation: "scanline 3s linear infinite", pointerEvents: "none" }} />

      <div style={{ textAlign: "center", marginBottom: 32, position: "relative" }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: T.gold, marginBottom: 8, letterSpacing: "1px" }}>AI 智能报告构建中</h3>
        <p style={{ fontSize: 13, color: T.text1, height: 20 }}>{tip}</p>
        <div style={{ fontSize: 32, fontWeight: 800, color: T.gold, marginTop: 16, fontFamily: "JetBrains Mono, monospace", opacity: 0.9 }}>
          {totalProgress}%
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {sections.map((s, i) => {
          const p = Math.round(progresses[i]);
          const active = i === currentIdx;
          const done = p >= 100;
          return (
            <div key={s.label} style={{ opacity: done || active ? 1 : 0.4, transition: "opacity 0.5s" }}>
              <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 18, color: done ? T.green : active ? T.gold : T.text2 }}>{s.icon}</span>
                  <div>
                    <span style={{ fontSize: 14, fontWeight: 600, color: done ? T.green : active ? T.text0 : T.text2 }}>{s.label}</span>
                    {active && <span style={{ fontSize: 11, color: T.gold, marginLeft: 8, animation: "pulse 1.5s infinite" }}>撰写中...</span>}
                  </div>
                </div>
                <span style={{ fontSize: 12, color: T.text2, fontFamily: "JetBrains Mono, monospace" }}>{p}%</span>
              </div>
              <div style={{ height: 4, background: T.bg3, borderRadius: 2, overflow: "hidden" }}>
                <div style={{
                  height: "100%", width: `${p}%`,
                  background: done ? T.green : active ? `linear-gradient(90deg, ${T.gold}, ${T.goldL})` : T.bg3,
                  boxShadow: active ? `0 0 10px ${T.gold}66` : "none",
                  transition: "width 0.4s ease"
                }} />
              </div>
              {active && <p style={{ fontSize: 11, color: T.text2, marginTop: 6, paddingLeft: 28 }}>正在生成：{s.desc}</p>}
            </div>
          );
        })}
      </div>
      <p style={{ textAlign: "center", fontSize: 11, color: T.text2, marginTop: 32 }}>
        基于 DeepSeek 深度思考模型，报告字数预计 2500+ 字
      </p>
    </div>
  );
}


// 错误提示
function ErrBanner({ msg, onRetry }) {
  if (!msg) return null;
  return (
    <div className="responsive-row" style={{ padding: "10px 14px", background: T.red + "15", border: `1px solid ${T.red}44`, borderRadius: 6, marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: 13, color: T.red }}>⚠ {msg}</span>
      {onRetry && <Btn onClick={onRetry} variant="ghost" size="sm">重试</Btn>}
    </div>
  );
}

// 空态
function Empty({ icon, text, sub, children }) {
  return (
    <div style={{ textAlign: "center", padding: "50px 0", color: T.text2 }}>
      <div style={{ fontSize: 40, marginBottom: 12, filter: "grayscale(40%)" }}>{icon}</div>
      <p style={{ color: T.text1, fontSize: 14, marginBottom: 6 }}>{text}</p>
      {sub && <p style={{ fontSize: 12, marginBottom: 0 }}>{sub}</p>}
      {children}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════
// 模型选择器
// ══════════════════════════════════════════════════════════════════
const MODELS = [
  { id: "deepseek", label: "DeepSeek V3", icon: "⚡", desc: "性价比最高" },
  { id: "qwen", label: "通义千问", icon: "🔮", desc: "国内合规" },
  { id: "kimi", label: "Kimi", icon: "🌙", desc: "长文本佳" },
  { id: "glm", label: "GLM-4-Flash", icon: "⭐", desc: "有免费额度" },
  { id: "claude", label: "Claude 3.5", icon: "🤖", desc: "理解力强" },
];

function ModelSelector() {
  const [current, setCurrent] = useState(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [tip, setTip] = useState("");

  useEffect(() => {
    fetch("/api/ai/provider").then(r => r.json()).then(d => { if (d.provider) setCurrent(d.provider); }).catch(() => { });
  }, []);

  const switchModel = async (id) => {
    if (id === current || loading) return;
    setLoading(true); setOpen(false); setTip("");
    try {
      const res = await fetch("/api/ai/provider", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: id }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "切换失败");
      setCurrent(data.provider);
      setTip("✅ 已切换到 " + (MODELS.find(m => m.id === id)?.label || id));
    } catch (e) { setTip("❌ " + e.message); }
    setLoading(false);
    setTimeout(() => setTip(""), 3000);
  };

  const cur = MODELS.find(m => m.id === current);
  return (
    <div style={{ position: "relative" }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: "flex", alignItems: "center", gap: 6, padding: "5px 12px",
        borderRadius: 8, cursor: "pointer", background: T.bg1,
        border: `1px solid ${T.gold}44`, color: T.text0, fontSize: 12,
        fontFamily: "Sora, sans-serif",
      }}>
        <span style={{ fontSize: 14 }}>{loading ? "⟳" : (cur?.icon || "🤖")}</span>
        <span style={{ color: T.goldL, fontWeight: 600 }}>{loading ? "切换中…" : (cur?.label || "选择模型")}</span>
        <span style={{ color: T.text2, fontSize: 10 }}>▾</span>
      </button>
      {tip && (
        <div style={{
          position: "absolute", top: 38, right: 0, whiteSpace: "nowrap",
          padding: "6px 12px", borderRadius: 8, fontSize: 12, zIndex: 300,
          background: tip.startsWith("✅") ? T.green + "22" : "#c0002022",
          border: `1px solid ${tip.startsWith("✅") ? T.green : "#c00020"}44`,
          color: T.text0,
        }}>{tip}</div>
      )}
      {open && !loading && (
        <div style={{
          position: "absolute", top: 38, right: 0, zIndex: 300,
          background: T.bg1, border: `1px solid ${T.gold}44`,
          borderRadius: 12, overflow: "hidden", minWidth: 200,
          boxShadow: "0 8px 32px rgba(0,0,0,.4)",
        }}>
          <div style={{ padding: "10px 14px 6px", fontSize: 11, color: T.text2, borderBottom: `1px solid ${T.line2}` }}>选择 AI 模型</div>
          {MODELS.map(m => (
            <button key={m.id} onClick={() => switchModel(m.id)} style={{
              width: "100%", display: "flex", alignItems: "center", gap: 10,
              padding: "10px 14px", background: m.id === current ? T.gold + "18" : "none",
              border: "none", borderBottom: `1px solid ${T.line}`, cursor: "pointer",
              color: T.text0, textAlign: "left",
            }}>
              <span style={{ fontSize: 18 }}>{m.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: m.id === current ? T.goldL : T.text0 }}>
                  {m.label}{m.id === current && <span style={{ fontSize: 10, color: T.gold, marginLeft: 6 }}>● 使用中</span>}
                </div>
                <div style={{ fontSize: 11, color: T.text2 }}>{m.desc}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// 顶部 Header + 步骤导航
// ══════════════════════════════════════════════════════════════════
const STEPS = [
  { id: 1, label: "信息录入", icon: "◎" },
  { id: 2, label: "能力画像", icon: "◈" },
  { id: 3, label: "岗位探索", icon: "◉" },
  { id: 4, label: "人岗匹配", icon: "◆" },
  { id: 5, label: "职业报告", icon: "◇" },
];

function Header({ step, setStep, maxStep }) {
  return (
    <header style={{
      position: "sticky", top: 0, zIndex: 200,
      background: T.bg0 + "ee", backdropFilter: "blur(12px)",
      borderBottom: `1px solid ${T.line2}`,
    }}>
      {/* Logo行 */}
      <div className="responsive-row brand-header" style={{ padding: "10px 28px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: `1px solid ${T.line}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Logo 图形 */}
          <svg width="32" height="32" viewBox="0 0 32 32">
            <circle cx="16" cy="16" r="14" fill="none" stroke={T.gold} strokeWidth="1.5" />
            <circle cx="16" cy="16" r="6" fill="none" stroke={T.goldL} strokeWidth="1" />
            <line x1="16" y1="2" x2="16" y2="10" stroke={T.gold} strokeWidth="1.5" />
            <line x1="16" y1="22" x2="16" y2="30" stroke={T.gold} strokeWidth="1.5" />
            <line x1="2" y1="16" x2="10" y2="16" stroke={T.gold} strokeWidth="1.5" />
            <line x1="22" y1="16" x2="30" y2="16" stroke={T.gold} strokeWidth="1.5" />
            <circle cx="16" cy="16" r="2.5" fill={T.gold} />
          </svg>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: T.text0, fontFamily: "Sora, sans-serif", letterSpacing: ".5px" }}>职途罗盘</div>
            <div style={{ fontSize: 10, color: T.text2, letterSpacing: "1.2px", textTransform: "uppercase" }}>Career Intelligence System</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="version-caption" style={{ fontSize: 11, color: T.text2, fontFamily: "JetBrains Mono, monospace" }}>v3.0 · AI-Powered</div>
          <ModelSelector />
        </div>
      </div>

      {/* 步骤导航 */}
      <div className="step-navigation" style={{ padding: "0 28px", display: "flex", alignItems: "center" }}>
        {STEPS.map((s, idx) => (
          <div className="step-item" key={s.id} style={{ display: "flex", alignItems: "center", flex: idx < 4 ? 1 : 0 }}>
            <button
              onClick={() => s.id <= maxStep && setStep(s.id)}
              disabled={s.id > maxStep}
              aria-current={s.id === step ? "step" : undefined}
              style={{
                display: "flex", alignItems: "center", gap: 7, padding: "12px 0",
                background: "none", color: step === s.id ? T.gold : s.id < step ? T.green : T.text2,
                fontSize: 12, fontWeight: step === s.id ? 700 : 400,
                opacity: s.id > maxStep ? .5 : 1,
                cursor: s.id <= maxStep ? "pointer" : "default",
                borderBottom: step === s.id ? `2px solid ${T.gold}` : "2px solid transparent",
                fontFamily: "Sora, sans-serif",
                whiteSpace: "nowrap",
              }}
            >
              <span style={{
                width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 700, flexShrink: 0,
                background: step === s.id ? T.gold : s.id < step ? T.green : T.bg3,
                color: step === s.id || s.id < step ? T.bg0 : T.text2,
                boxShadow: step === s.id ? `0 0 8px ${T.gold}80` : "none",
              }}>
                {s.id < step ? "✓" : s.id}
              </span>
              {s.icon} {s.label}
            </button>
            {idx < 4 && (
              <div style={{ flex: 1, height: 1, background: s.id < step ? T.green + "60" : T.line, margin: "0 8px" }} />
            )}
          </div>
        ))}
      </div>
    </header>
  );
}

// ══════════════════════════════════════════════════════════════════
// 步骤1：信息录入
// ══════════════════════════════════════════════════════════════════
function Step1({ data, setData, onNext }) {
  const [tab, setTab] = useState("basic");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState(() => loadHistory());
  const fileRef = useRef();

  const set = (k, v) => setData(p => ({ ...p, [k]: v }));
  const addTag = (k, v) => setData(p => ({ ...p, [k]: [...(p[k] || []), v] }));
  const rmTag = (k, i) => setData(p => ({ ...p, [k]: p[k].filter((_, j) => j !== i) }));

  const handleUpload = async e => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/student/upload-resume`, { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || "解析失败");
      const d = json.parsed_data || {};
      if (json.char_count < 100) {
        setUploadMsg("⚠ 简历文本提取较少，建议手动补充关键信息");
      } else {
        setUploadMsg(`✓ 已解析 ${json.char_count} 字，请检查并确认信息`);
      }
      setData(prev => ({
        ...prev,
        ...Object.fromEntries(
          Object.entries(d).filter(([k, v]) => v !== null && v !== undefined && v !== "")
        ),
        skills: d.skills?.length ? d.skills : prev.skills,
        certificates: d.certificates?.length ? d.certificates : prev.certificates,
        internships: d.internships?.length ? d.internships.map(i => `${i.company} · ${i.position} · ${i.duration}`) : prev.internships,
        projects: d.projects?.length ? d.projects.map(p => `${p.name}（${p.tech_stack || ""}）`) : prev.projects,
        awards: d.awards?.length ? d.awards : prev.awards,
        target_jobs: d.target_jobs?.length ? d.target_jobs : prev.target_jobs,
      }));
    } catch (err) {
      setUploadMsg("✗ 解析失败：" + err.message);
    }
    setUploading(false);
    fileRef.current.value = "";
  };

  const TABS = [
    { id: "basic", label: "基本信息" },
    { id: "skills", label: "技能证书" },
    { id: "exp", label: "经历项目" },
    { id: "intent", label: "求职意向" },
  ];

  const IS = { width: "100%", padding: "9px 12px", fontSize: 13 };

  return (
    <div className="fade-up">
      {/* 页头区 */}
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: T.text0, fontFamily: "Sora, sans-serif", marginBottom: 4 }}>
          个人信息录入
        </h2>
        <p style={{ fontSize: 13, color: T.text2 }}>信息越完整，AI 分析越精准。支持直接上传简历自动填写。</p>
      </div>

      {/* ── 历史记录面板 ── */}
      {history.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <button
            onClick={() => setShowHistory(h => !h)}
            style={{
              display: "flex", alignItems: "center", gap: 8, padding: "7px 14px",
              background: T.bg1, border: `1px solid ${T.gold}44`, borderRadius: 8,
              cursor: "pointer", color: T.goldL, fontSize: 13, fontFamily: "Sora, sans-serif",
            }}
          >
            <span>📋</span>
            <span style={{ fontWeight: 600 }}>历史记录</span>
            <span style={{ color: T.text2, fontSize: 11 }}>({history.length} 条)</span>
            <span style={{ color: T.text2, fontSize: 11, marginLeft: 4 }}>{showHistory ? "▲ 收起" : "▼ 展开"}</span>
          </button>

          {showHistory && (
            <div style={{
              marginTop: 8, padding: "16px 20px",
              background: T.bg1, border: `1px solid ${T.gold}33`,
              borderRadius: 10, animation: "fadeUp .2s ease both",
            }}>
              <div style={{ fontSize: 12, color: T.text2, marginBottom: 12 }}>
                点击记录可一键恢复信息，最多保留 {MAX_HISTORY} 条（本次会话有效）
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {history.map((h, i) => (
                  <div key={i}
                    onClick={() => {
                      const { _savedAt, ...rest } = h;
                      setData({ ...DEFAULT_STUDENT, ...rest });
                      setShowHistory(false);
                    }}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      padding: "10px 14px", borderRadius: 8, cursor: "pointer",
                      background: T.bg2, border: `1px solid ${T.line2}`, transition: "all .15s",
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = T.gold; e.currentTarget.style.background = T.bg0; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = T.line2; e.currentTarget.style.background = T.bg2; }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: "50%",
                        background: T.gold + "22", display: "flex", alignItems: "center",
                        justifyContent: "center", fontSize: 16, flexShrink: 0,
                      }}>👤</div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: T.text0 }}>
                          {h.name}
                          <span style={{ fontSize: 11, color: T.text2, marginLeft: 8, fontWeight: 400 }}>
                            {h.education_level} · {h.graduation_year}届
                          </span>
                        </div>
                        <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>
                          {h.university || "—"} · {h.major || "—"}
                          {h.target_jobs?.length > 0 && (
                            <span style={{ marginLeft: 8, color: T.goldL }}>
                              目标：{h.target_jobs.slice(0, 2).join("、")}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ fontSize: 11, color: T.text2, textAlign: "right" }}>
                        <div>{h._savedAt}</div>
                        <div style={{ color: T.cyan, marginTop: 2 }}>
                          {[h.skills?.length > 0 && `${h.skills.length}项技能`,
                          h.internships?.length > 0 && `${h.internships.length}段实习`,
                          h.projects?.length > 0 && `${h.projects.length}个项目`,
                          ].filter(Boolean).join(" · ") || "基本信息"}
                        </div>
                      </div>
                      <div style={{
                        padding: "4px 10px", borderRadius: 6, fontSize: 11,
                        background: T.gold + "22", color: T.goldL, border: `1px solid ${T.gold}44`,
                      }}>恢复</div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 10, textAlign: "right" }}>
                <button onClick={() => {
                  sessionStorage.removeItem(HISTORY_KEY);
                  setHistory([]);
                  setShowHistory(false);
                }} style={{
                  fontSize: 11, color: T.text2, background: "none",
                  border: "none", cursor: "pointer", textDecoration: "underline",
                }}>清除所有历史记录</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 简历上传 */}
      <Card style={{ marginBottom: 20, borderStyle: "dashed", borderColor: T.line2, background: T.bg0 }} glow={false}>
        <div className="responsive-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <div>
            <div style={{ fontSize: 13, color: T.text1, marginBottom: 3 }}>📎 快速填写 — 上传简历自动解析</div>
            <div style={{ fontSize: 11, color: T.text2 }}>支持 PDF / DOCX / TXT，AI 提取后可手动修改</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {uploadMsg && <span style={{ fontSize: 12, color: uploadMsg.startsWith("✓") ? T.green : uploadMsg.startsWith("⚠") ? T.orange : T.red }}>{uploadMsg}</span>}
            <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" style={{ display: "none" }} onChange={handleUpload} />
            <Btn onClick={() => fileRef.current.click()} disabled={uploading} variant="outline" size="sm">
              {uploading ? "解析中…" : "上传简历"}
            </Btn>
          </div>
        </div>
      </Card>

      {/* Tab 导航 */}
      <div className="form-tabs" style={{ display: "flex", gap: 2, marginBottom: 20, borderBottom: `1px solid ${T.line2}` }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: "9px 18px", background: "none", fontSize: 13,
            color: tab === t.id ? T.gold : T.text2,
            borderBottom: tab === t.id ? `2px solid ${T.gold}` : "2px solid transparent",
            fontWeight: tab === t.id ? 600 : 400,
            fontFamily: "Sora, sans-serif",
            marginBottom: -1,
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* 基本信息 */}
      {tab === "basic" && (
        <div className="fade-up responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {[
            ["name", "姓名", "张三"],
            ["major", "专业", "计算机科学与技术"],
            ["university", "学校", "XX 大学"],
            ["education_level", "学历", "本科 / 硕士 / 博士"],
            ["graduation_year", "毕业年份", "2025"],
            ["gpa", "GPA", "3.8"],
          ].map(([k, label, ph]) => (
            <Field key={k} label={label}>
              <Input value={data[k] || ""} onChange={e => set(k, e.target.value)} placeholder={ph} />
            </Field>
          ))}
          <div style={{ gridColumn: "1/-1" }}>
            <Field label="自我介绍">
              <Textarea value={data.self_introduction || ""} onChange={e => set("self_introduction", e.target.value)} placeholder="简要介绍自己的优势、经历和职业方向（100字内）…" rows={3} />
            </Field>
          </div>
        </div>
      )}

      {/* 技能证书 */}
      {tab === "skills" && (
        <div className="fade-up responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          <TagInput label="专业技能" items={data.skills || []} onAdd={v => addTag("skills", v)} onRemove={i => rmTag("skills", i)} placeholder="如：Python、Vue.js（回车添加）" color={T.gold} />
          <TagInput label="证书 / 资质" items={data.certificates || []} onAdd={v => addTag("certificates", v)} onRemove={i => rmTag("certificates", i)} placeholder="如：CET-6、PMP" color={T.cyan} />
          <div style={{ gridColumn: "1/-1" }}>
            <TagInput label="获奖荣誉" items={data.awards || []} onAdd={v => addTag("awards", v)} onRemove={i => rmTag("awards", i)} placeholder="如：国家奖学金、ACM 铜牌" color={T.green} />
          </div>
        </div>
      )}

      {/* 经历项目 */}
      {tab === "exp" && (
        <div className="fade-up responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          <TagInput
            label="实习 / 工作经历"
            items={data.internships || []}
            onAdd={v => addTag("internships", v)}
            onRemove={i => rmTag("internships", i)}
            placeholder="如：阿里巴巴 · 前端实习 · 6个月"
            color={T.gold}
          />
          <TagInput
            label="项目经历"
            items={data.projects || []}
            onAdd={v => addTag("projects", v)}
            onRemove={i => rmTag("projects", i)}
            placeholder="如：校园外卖系统（React + SpringBoot）"
            color={T.cyan}
          />
        </div>
      )}

      {/* 求职意向 */}
      {tab === "intent" && (
        <div className="fade-up responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div style={{ gridColumn: "1/-1" }}>
            <TagInput label="目标岗位" items={data.target_jobs || []} onAdd={v => addTag("target_jobs", v)} onRemove={i => rmTag("target_jobs", i)} placeholder="如：前端开发工程师（回车添加）" color={T.gold} />
          </div>
          <Field label="期望薪资">
            <Input value={data.expected_salary || ""} onChange={e => set("expected_salary", e.target.value)} placeholder="如：15-25k" />
          </Field>
          <Field label="期望城市">
            <Input value={(data.target_cities || []).join("、")} onChange={e => set("target_cities", e.target.value.split(/[、,，\s]+/).filter(Boolean))} placeholder="如：北京、上海" />
          </Field>
          <div style={{ gridColumn: "1/-1" }}>
            <Field label="工作偏好" tip="如：倾向大厂 / 初创公司 / 远程工作 / 稳定国企…">
              <Input value={data.work_style || ""} onChange={e => set("work_style", e.target.value)} placeholder="描述您的工作风格偏好" />
            </Field>
          </div>
          <div style={{ gridColumn: "1/-1" }}>
            <Field label="是否接受异地">
              <select value={data.willing_to_relocate ? "yes" : "no"} onChange={e => set("willing_to_relocate", e.target.value === "yes")}
                style={{ width: "100%", padding: "9px 12px", fontSize: 13 }}>
                <option value="yes">是，可以接受异地</option>
                <option value="no">否，仅考虑本地机会</option>
              </select>
            </Field>
          </div>
        </div>
      )}

      {/* 底部操作 */}
      <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 28, paddingTop: 16, borderTop: `1px solid ${T.line}` }}>
        <span style={{ fontSize: 12, color: T.text2 }}>
          {data.name.trim() && data.major.trim() ? `✓ ${data.name.trim()} · ${data.major.trim()}` : "请至少填写姓名和专业"}
        </span>
        <Btn onClick={() => { saveHistory(data); onNext(); }} disabled={!data.name.trim() || !data.major.trim()} variant="gold">
          下一步：生成能力画像 →
        </Btn>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// 步骤2：能力画像
// ══════════════════════════════════════════════════════════════════
function Step2({ studentData, profile, setProfile, onNext }) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const generate = async () => {
    setLoading(true); setErr("");
    try {
      const res = await api("/student/analyze", {
        method: "POST",
        body: JSON.stringify({
          name: studentData.name,
          major: studentData.major,
          university: studentData.university || "",
          education_level: studentData.education_level || "本科",
          graduation_year: studentData.graduation_year || "2025",
          gpa: studentData.gpa ? parseFloat(studentData.gpa) : null,
          skills: studentData.skills || [],
          certificates: studentData.certificates || [],
          internships: (studentData.internships || []).map(s => ({ company: s, position: "", duration: "" })),
          projects: (studentData.projects || []).map(s => ({ name: s, role: "", description: s })),
          awards: studentData.awards || [],
          self_introduction: studentData.self_introduction || "",
          target_jobs: studentData.target_jobs || [],
          target_cities: studentData.target_cities || [],
          expected_salary: studentData.expected_salary || "",
          willing_to_relocate: studentData.willing_to_relocate || false,
          work_style: studentData.work_style || "",
        }),
      }, 90000);
      setProfile(res.profile);
    } catch (e) {
      setErr(e.message);
    }
    setLoading(false);
  };

  const DIM_LABELS = {
    professional_skills: "专业技能",
    certificates: "证书资质",
    innovation_ability: "创新能力",
    learning_ability: "学习能力",
    stress_resistance: "抗压能力",
    communication_ability: "沟通能力",
    internship_experience: "实习经历",
    career_intention: "就业意愿",
  };

  const dims = profile?.dimensions
    ? Object.entries(profile.dimensions).map(([k, v]) => ({
      key: k, label: DIM_LABELS[k] || k, score: v.score || 0, data: v,
    }))
    : [];

  const radarData = profile?.radar_data || dims.map(d => ({ axis: d.label, student: d.score, benchmark: 80 }));

  const getColor = s => s >= 80 ? T.green : s >= 60 ? T.gold : s >= 40 ? T.orange : T.red;

  return (
    <div className="fade-up">
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, fontFamily: "Sora, sans-serif", marginBottom: 4 }}>就业能力画像</h2>
        <p style={{ fontSize: 13, color: T.text2 }}>AI 从 8 个维度分析您的就业竞争力，与目标岗位标准对照评分</p>
      </div>

      {loading && <ProfileLoading />}
      <ErrBanner msg={err} onRetry={generate} />

      {!profile && !loading && (
        <Empty icon="🎯" text={`准备为 ${studentData.name || "您"} 生成专属能力画像`} sub="点击下方按钮，AI 将综合分析您填写的所有信息">
          <Btn onClick={generate} variant="gold" size="lg" style={{ marginTop: 24 }}>生成我的能力画像</Btn>
        </Empty>
      )}

      {!loading && (
        <div style={{ display: "none" }}>
          <Btn onClick={generate} variant="gold">生成能力画像</Btn>
        </div>
      )}

      {profile && !loading && (
        <div>
          {/* 顶部总分 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }} className="fade-up responsive-grid">
            {[
              { label: "信息完整度", score: profile.completeness_score, color: T.cyan },
              { label: "综合竞争力", score: profile.competitiveness_score, color: T.gold },
              { label: "能力等级", score: Math.round((profile.completeness_score + profile.competitiveness_score) / 2), color: T.green },
            ].map(({ label, score, color }) => (
              <Card key={label} style={{ textAlign: "center", padding: "20px 16px" }}>
                <Ring score={score} size={80} color={color} />
                <div style={{ fontSize: 12, color: T.text2, marginTop: 10, fontFamily: "Sora, sans-serif" }}>{label}</div>
              </Card>
            ))}
          </div>

          {/* 雷达图 + 维度条 */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.1fr", gap: 16, marginBottom: 16 }} className="fade-up-2 responsive-grid">
            <Card>
              <SectionTitle icon="◉">能力雷达图</SectionTitle>
              <div style={{ display: "flex", justifyContent: "center" }}>
                <Radar data={radarData} size={240} />
              </div>
              <div style={{ display: "flex", justifyContent: "center", gap: 20, marginTop: 8 }}>
                <span style={{ fontSize: 10, color: T.cyan }}>— — 岗位基准</span>
                <span style={{ fontSize: 10, color: T.gold }}>—— 当前水平</span>
              </div>
            </Card>
            <Card>
              <SectionTitle icon="◈">各维度评分</SectionTitle>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {dims.map(d => (
                  <Bar key={d.key} label={d.label} sublabel={`${d.score}`} value={d.score} color={getColor(d.score)} h={6} />
                ))}
              </div>
            </Card>
          </div>

          {/* 优势 + 提升 */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }} className="fade-up-3 responsive-grid">
            <Card>
              <SectionTitle icon="✦">核心竞争优势</SectionTitle>
              {(profile.competitive_advantages || []).map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 8, marginBottom: 10, fontSize: 13, color: T.text1, alignItems: "flex-start" }}>
                  <span style={{ color: T.green, flexShrink: 0, marginTop: 1 }}>✓</span>
                  <span style={{ lineHeight: 1.6 }}>{a}</span>
                </div>
              ))}
            </Card>
            <Card>
              <SectionTitle icon="→">重点提升方向</SectionTitle>
              {(profile.improvement_areas || []).map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 8, marginBottom: 10, fontSize: 13, color: T.text1, alignItems: "flex-start" }}>
                  <span style={{ color: T.gold, flexShrink: 0, marginTop: 1 }}>→</span>
                  <span style={{ lineHeight: 1.6 }}>{a}</span>
                </div>
              ))}
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 11, color: T.text2, marginBottom: 6, textTransform: "uppercase", letterSpacing: ".6px" }}>适合岗位方向</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                  {(profile.suitable_jobs || []).map((j, i) => <Tag key={i} color={T.gold}>{j}</Tag>)}
                </div>
              </div>
            </Card>
          </div>

          {/* 综合分析 */}
          {profile.overall_analysis && (
            <Card style={{ marginBottom: 16, background: T.gold + "06", borderColor: T.gold + "33" }}>
              <SectionTitle icon="◎">综合分析</SectionTitle>
              <p style={{ fontSize: 14, color: T.text1, lineHeight: 1.8, margin: 0 }}>{profile.overall_analysis}</p>
            </Card>
          )}

          {/* 维度详情展开 */}
          <Card style={{ marginBottom: 16 }}>
            <SectionTitle icon="◈">维度详细分析</SectionTitle>
            <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {dims.map(d => (
                <div key={d.key} style={{ padding: "10px 12px", background: T.bg0, borderRadius: 6, borderLeft: `3px solid ${getColor(d.score)}` }}>
                  <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: T.text0 }}>{d.label}</span>
                    <span style={{ fontSize: 12, color: getColor(d.score), fontFamily: "JetBrains Mono, monospace" }}>{d.score}</span>
                  </div>
                  {d.data?.level && <Tag color={getColor(d.score)}>{d.data.level}</Tag>}
                  {d.data?.details && <p style={{ fontSize: 11, color: T.text2, marginTop: 6, lineHeight: 1.6 }}>{d.data.details}</p>}
                  {d.data?.gaps?.length > 0 && (
                    <div style={{ marginTop: 5, display: "flex", flexWrap: "wrap", gap: 3 }}>
                      {d.data.gaps.slice(0, 2).map((g, i) => <Tag key={i} color={T.orange}>{g}</Tag>)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", paddingTop: 12, borderTop: `1px solid ${T.line}` }}>
            <Btn onClick={generate} variant="ghost">↺ 重新生成</Btn>
            <Btn onClick={onNext} variant="gold">下一步：探索岗位 →</Btn>
          </div>
        </div>
      )}

      {!profile && !loading && (
        <div style={{ textAlign: "center", marginTop: 20 }}>
          <Btn onClick={generate} variant="gold" size="lg">⚡ 生成我的能力画像</Btn>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// 步骤3：岗位探索
// ══════════════════════════════════════════════════════════════════
function Step3({ selectedJob, setSelectedJob, onNext, profile, studentData }) {
  const [view, setView] = useState("list");
  const [keyword, setKeyword] = useState("");
  const [city, setCity] = useState("");
  const [industry, setIndustry] = useState("");
  const [salMin, setSalMin] = useState("");
  const [page, setPage] = useState(1);
  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [graphJob, setGraphJob] = useState("前端开发工程师");
  const [pathData, setPathData] = useState(null);
  const [pathLoading, setPathLoading] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [recJobs, setRecJobs] = useState([]);
  const [recLoading, setRecLoading] = useState(false);
  const [recErr, setRecErr] = useState("");
  const [recDone, setRecDone] = useState(false);
  const [showRec, setShowRec] = useState(false);
  const [recAnalysis, setRecAnalysis] = useState("");

  const PAGE_SIZE = 12;

  const fetchJobs = useCallback(async (pg = 1, kwOverride = null) => {
    setLoading(true); setErr("");
    try {
      const params = new URLSearchParams({ page: pg, page_size: PAGE_SIZE });
      const kw = kwOverride !== null ? kwOverride : keyword;
      if (kw) params.set("keyword", kw);
      if (city) params.set("city", city);
      if (industry) params.set("industry", industry);
      if (salMin) params.set("salary_min", salMin);
      const res = await api(`/jobs/list?${params}`);
      setJobs(res.jobs || []);
      setTotal(res.total || 0);
      setPage(pg);
    } catch (e) {
      setJobs(prev => { if (prev.length === 0) setErr(e.message); return prev; });
    } finally {
      setLoading(false);
    }
  }, [keyword, city, industry, salMin]);

  const fetchPath = async jname => {
    setPathLoading(true);
    try {
      // 使用POST接口，避免C/C++等含特殊字符的岗位名在URL中被错误解析
      const res = await api("/jobs/graph/query", {
        method: "POST",
        body: JSON.stringify({ job_name: jname }),
      });
      setPathData(res);
    } catch { setPathData(null); }
    finally { setPathLoading(false); }
  };

  const fetchProfiles = async () => {
    try {
      const res = await api("/jobs/profiles/list");
      setProfiles(res.profiles || []);
    } catch (e) {
      // profiles 加载失败不影响主流程，静默处理
      console.warn("profiles加载失败:", e.message);
    }
  };

  // ── AI推荐岗位 ──
  const fetchRecommend = async () => {
    if (!profile || !studentData) {
      setRecErr("请先完成能力画像分析再获取推荐");
      return;
    }
    setRecLoading(true); setRecErr(""); setShowRec(true);
    try {
      const res = await api("/jobs/recommend", {
        method: "POST",
        body: JSON.stringify({
          student_info: {
            name: studentData.name, major: studentData.major,
            education_level: studentData.education_level || "本科"
          },
          student_profile: profile,
          top_k: 6,
        }),
      }, 90000);
      setRecJobs(res.recommendations || []);
      setRecDone(true);
    } catch (e) { setRecErr(e.message); }
    setRecLoading(false);
  };

  useEffect(() => {
    fetchJobs(1).then(() => fetchProfiles());
    // 已有能力画像则自动触发推荐，让用户进入页面就看到推荐结果
    if (profile) {
      setShowRec(true);
      fetchRecommend();
    }
  }, []);
  useEffect(() => { if (view === "graph") fetchPath(graphJob); }, [view, graphJob]);

  const DIFF_COLOR = { 较易: T.green, 中等: T.gold, 较难: T.red };

  const salDisplay = j => {
    if (j.negotiable) return "面议";
    if (!j.salary_min) return "—";
    return `${(j.salary_min / 1000).toFixed(0)}-${(j.salary_max / 1000).toFixed(0)}k`;
  };

  // 可用图谱岗位从画像列表里取
  const graphJobs = profiles.map(p => p.title).filter(Boolean);
  if (!graphJobs.length) graphJobs.push(...["Java开发工程师", "软件测试工程师", "C/C++开发工程师", "前端开发工程师", "硬件测试工程师", "实施工程师", "技术支持工程师", "质量管理工程师", "项目经理", "IT运营专员"]);

  return (
    <div className="fade-up">
      <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, fontFamily: "Sora, sans-serif", marginBottom: 4 }}>岗位探索</h2>
          <p style={{ fontSize: 13, color: T.text2 }}>共 {total.toLocaleString()} 条真实岗位数据，选择目标岗位后进行匹配分析</p>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {[["list", "◉ 岗位列表"], ["recommend", "✦ AI推荐"], ["graph", "◈ 路径图谱"]].map(([v, l]) => (
            <Btn key={v} onClick={() => {
              setView(v);
              if (v === "recommend" && recJobs.length === 0 && !recLoading) fetchRecommend();
            }} variant={view === v ? "gold" : "ghost"} size="sm">{l}</Btn>
          ))}
          <Btn onClick={fetchRecommend} disabled={recLoading || !profile}
            variant={showRec ? "gold" : "outline"}
            size="sm"
            style={{ borderColor: T.cyan, color: showRec ? undefined : T.cyan }}
          >
            {recLoading ? "⟳ 分析中…" : "✦ AI推荐岗位"}
          </Btn>
        </div>
      </div>

      {/* ── AI推荐岗位面板（顶部常驻）── */}
      {showRec && (
        <div style={{
          marginBottom: 20, padding: "20px 24px",
          background: `linear-gradient(135deg, ${T.cyan}0a, ${T.gold}06)`,
          border: `1px solid ${T.cyan}44`, borderRadius: 12,
          animation: "fadeUp .3s ease both",
        }}>
          {/* 面板标题 */}
          <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: T.cyan, fontFamily: "Sora, sans-serif" }}>
                ✦ AI 为 {studentData?.name || "你"} 推荐的岗位方向
              </div>
              <div style={{ fontSize: 12, color: T.text2, marginTop: 3 }}>
                基于你的能力画像、专业背景和技能特长，从 10 个标准岗位方向中智能匹配
              </div>
            </div>
            <div className="action-group" style={{ display: "flex", gap: 8 }}>
              <Btn onClick={fetchRecommend} disabled={recLoading} variant="outline" size="sm"
                style={{ borderColor: T.cyan, color: T.cyan }}>
                {recLoading ? "⟳ 分析中…" : "↺ 重新推荐"}
              </Btn>
              <Btn onClick={() => setShowRec(false)} variant="ghost" size="sm">✕ 收起</Btn>
            </div>
          </div>

          {recLoading && <Loading text="AI 正在分析你的能力画像，智能匹配最适合的岗位…" />}
          {recErr && <ErrBanner msg={recErr} onRetry={fetchRecommend} />}

          {!recLoading && recJobs.length > 0 && (
            <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              {recJobs.map((rec, i) => {
                const scoreColor = rec.match_score >= 75 ? T.green : rec.match_score >= 55 ? T.goldL : T.red;
                const scoreBg = rec.match_score >= 75 ? T.green : rec.match_score >= 55 ? T.gold : T.red;
                return (
                  <div key={i}
                    onClick={() => {
                      setKeyword(rec.job_title);
                      setView("list");
                      fetchJobs(1, rec.job_title);  // 直接传关键词，避免state异步问题
                    }}
                    style={{
                      padding: "16px", borderRadius: 10, cursor: "pointer",
                      background: T.bg1, border: `1px solid ${T.cyan}33`,
                      transition: "all .2s", position: "relative",
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = T.cyan; e.currentTarget.style.background = T.bg2; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = T.cyan + "33"; e.currentTarget.style.background = T.bg1; }}
                  >
                    {/* 排名角标 */}
                    <div style={{
                      position: "absolute", top: 10, left: 10,
                      width: 20, height: 20, borderRadius: "50%",
                      background: i < 3 ? T.gold + "33" : T.bg0,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 10, fontWeight: 700, color: i < 3 ? T.goldL : T.text2,
                    }}>{i + 1}</div>

                    {/* 岗位名 + 匹配分 */}
                    <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, paddingLeft: 26 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: T.text0 }}>{rec.job_title}</div>
                      <div style={{
                        fontSize: 12, fontWeight: 700, padding: "3px 9px", borderRadius: 20,
                        background: scoreBg + "22", color: scoreColor, border: `1px solid ${scoreBg}44`,
                      }}>{rec.match_score}分</div>
                    </div>

                    {/* 匹配等级 */}
                    <div style={{ marginBottom: 8, paddingLeft: 26 }}>
                      <span style={{ fontSize: 11, color: T.text2 }}>{rec.match_level} · 薪资参考：</span>
                      <span style={{ fontSize: 11, color: T.goldL, fontWeight: 600 }}>{rec.salary_range || "—"}</span>
                    </div>

                    {/* 推荐理由 */}
                    <div style={{ fontSize: 12, color: T.text1, lineHeight: 1.7, marginBottom: 10 }}>
                      {rec.reason}
                    </div>

                    {/* 优势标签 */}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
                      {(rec.strengths || []).map((s, si) => (
                        <span key={si} style={{
                          fontSize: 10, padding: "2px 8px", borderRadius: 10,
                          background: T.cyan + "15", color: T.cyan, border: `1px solid ${T.cyan}33`,
                        }}>✓ {s}</span>
                      ))}
                    </div>

                    {/* 缺口技能 */}
                    {rec.skill_gaps?.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
                        {rec.skill_gaps.map((g, gi) => (
                          <span key={gi} style={{
                            fontSize: 10, padding: "2px 8px", borderRadius: 10,
                            background: T.gold + "12", color: T.goldL, border: `1px solid ${T.gold}33`,
                          }}>⚠ {g}</span>
                        ))}
                      </div>
                    )}

                    {/* 行动建议 */}
                    {rec.action && (
                      <div style={{
                        fontSize: 11, color: T.text2, lineHeight: 1.6,
                        padding: "6px 8px", background: T.bg0, borderRadius: 6, marginBottom: 8
                      }}>
                        💡 {rec.action}
                      </div>
                    )}

                    <div style={{ fontSize: 11, color: T.cyan, marginTop: 4 }}>→ 点击搜索该岗位真实职位</div>
                  </div>
                );
              })}
            </div>
          )}

          {!recLoading && recDone && recJobs.length === 0 && (
            <p style={{ color: T.text2, fontSize: 13, textAlign: "center", padding: "20px 0" }}>
              暂无推荐结果，建议完善能力画像后重试
            </p>
          )}
        </div>
      )}

      {/* ── 岗位列表 ── */}
      {view === "list" && (
        <div>
          {/* 搜索筛选区 */}
          <Card style={{ marginBottom: 16, padding: "14px 16px" }}>
            <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1.8fr 1fr 1fr 1fr auto", gap: 10, alignItems: "end" }}>
              <Field label="关键词搜索">
                <Input value={keyword} onChange={e => setKeyword(e.target.value)}
                  placeholder="岗位名称、描述…"
                  onKeyDown={e => e.key === "Enter" && fetchJobs(1)} />
              </Field>
              <Field label="城市">
                <Input value={city} onChange={e => setCity(e.target.value)} placeholder="如：北京" />
              </Field>
              <Field label="行业">
                <Input value={industry} onChange={e => setIndustry(e.target.value)} placeholder="如：互联网" />
              </Field>
              <Field label="月薪下限（元）">
                <Input value={salMin} onChange={e => setSalMin(e.target.value)} placeholder="如：10000" type="number" />
              </Field>
              <div style={{ paddingBottom: 0 }}>
                <Btn onClick={() => fetchJobs(1)} variant="gold" style={{ height: 37, marginTop: 17 }}>搜索</Btn>
              </div>
            </div>
          </Card>

          <ErrBanner msg={err} onRetry={() => fetchJobs(1)} />
          {loading && <Loading text="加载岗位数据中…" />}

          {!loading && (
            <>
              <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
                {jobs.map(job => {
                  const selected = selectedJob?.job_id === job.job_id;
                  return (
                    <div
                      key={job.job_id}
                      onClick={() => setSelectedJob(selected ? null : job)}
                      style={{
                        background: selected ? T.gold + "10" : T.bg1,
                        border: `1px solid ${selected ? T.gold : T.line2}`,
                        borderRadius: 10, padding: "14px 16px", cursor: "pointer",
                        transition: "all .2s",
                        boxShadow: selected ? `0 0 16px ${T.gold}20` : "none",
                      }}
                    >
                      <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: T.text0, marginBottom: 3 }}>{job.title}</div>
                          <div style={{ fontSize: 11, color: T.text2 }}>{job.company_name} · {job.city || "—"}</div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: T.green, fontFamily: "JetBrains Mono, monospace" }}>
                            {salDisplay(job)}
                          </div>
                          <div style={{ fontSize: 10, color: T.text2 }}>月薪</div>
                        </div>
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
                        {(job.industry || []).slice(0, 2).map((ind, i) => (
                          <Tag key={i} color={T.cyan}>{ind}</Tag>
                        ))}
                        {job.company_scale && <Tag color={T.text2}>{job.company_scale}</Tag>}
                      </div>
                      <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 10, color: T.text2 }}>{job.updated_at || ""}</span>
                        {selected && <span style={{ fontSize: 11, color: T.gold, fontWeight: 600 }}>✓ 已选</span>}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* 分页 */}
              {total > PAGE_SIZE && (
                <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 8 }}>
                  <Btn onClick={() => fetchJobs(page - 1)} disabled={page <= 1} variant="ghost" size="sm">← 上一页</Btn>
                  <span style={{ fontSize: 12, color: T.text2, padding: "8px 12px", fontFamily: "JetBrains Mono, monospace" }}>
                    {page} / {Math.ceil(total / PAGE_SIZE)}
                  </span>
                  <Btn onClick={() => fetchJobs(page + 1)} disabled={page >= Math.ceil(total / PAGE_SIZE)} variant="ghost" size="sm">下一页 →</Btn>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── AI推荐岗位 ── */}
      {view === "recommend" && (
        <div className="fade-up">
          {/* 顶部说明卡 */}
          <Card style={{
            marginBottom: 16, padding: "16px 20px",
            background: `linear-gradient(135deg, ${T.gold}0a, ${T.cyan}06)`,
            borderColor: T.gold + "33"
          }}>
            <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.gold, marginBottom: 4 }}>
                  ✦ AI 智能岗位推荐
                </div>
                <div style={{ fontSize: 12, color: T.text2 }}>
                  基于你的能力画像，AI 综合分析后为你推荐最匹配的岗位方向
                </div>
              </div>
              <Btn onClick={fetchRecommend} disabled={recLoading} variant="gold" size="sm">
                {recLoading ? "⟳ 分析中…" : "↺ 重新推荐"}
              </Btn>
            </div>
          </Card>

          <ErrBanner msg={recErr} onRetry={fetchRecommend} />
          {recLoading && <Loading text="AI 正在分析你的能力画像，匹配最佳岗位…" />}

          {/* AI 分析说明 */}
          {recAnalysis && !recLoading && (
            <Card style={{
              marginBottom: 16, padding: "14px 18px",
              borderLeft: `3px solid ${T.cyan}`, background: T.bg1
            }}>
              <div style={{ fontSize: 12, color: T.cyan, fontWeight: 600, marginBottom: 6 }}>◎ AI 分析报告</div>
              <p style={{ fontSize: 13, color: T.text1, lineHeight: 1.85, margin: 0 }}>{recAnalysis}</p>
            </Card>
          )}

          {/* 推荐岗位卡片列表 */}
          {!recLoading && recJobs.length > 0 && (
            <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              {recJobs.map((rec, idx) => {
                const isSelected = selectedJob?.title === rec.job_title;
                return (
                  <div key={idx} onClick={() => setSelectedJob(isSelected ? null : {
                    job_id: `rec_${idx}`, title: rec.job_title,
                    company_name: "推荐岗位", city: "", salary_min: null, salary_max: null,
                  })}
                    style={{
                      padding: "16px 18px", borderRadius: 10, cursor: "pointer",
                      background: isSelected ? T.gold + "18" : T.bg1,
                      border: `1px solid ${isSelected ? T.gold : T.line2}`,
                      transition: "all .2s"
                    }}>
                    {/* 排名 + 标题 */}
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: "50%",
                        background: idx < 3 ? T.gold : T.bg2,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 13, fontWeight: 700,
                        color: idx < 3 ? "#000" : T.text2, flexShrink: 0
                      }}>
                        {idx + 1}
                      </div>
                      <div style={{
                        fontSize: 15, fontWeight: 700, color: T.text0,
                        fontFamily: "Sora, sans-serif"
                      }}>{rec.job_title}</div>
                      {isSelected && <Tag color={T.gold}>✓ 已选</Tag>}
                    </div>
                    {/* 匹配度进度条 */}
                    <div style={{ marginBottom: 10 }}>
                      <div style={{
                        display: "flex", justifyContent: "space-between",
                        fontSize: 11, color: T.text2, marginBottom: 4
                      }}>
                        <span>预估匹配度</span>
                        <span style={{ color: T.gold, fontWeight: 600 }}>{rec.match_score}%</span>
                      </div>
                      <div style={{ height: 6, background: T.bg2, borderRadius: 3, overflow: "hidden" }}>
                        <div style={{
                          height: "100%", borderRadius: 3,
                          width: `${rec.match_score}%`,
                          background: rec.match_score >= 75 ? T.green :
                            rec.match_score >= 55 ? T.gold : T.red,
                          transition: "width 1s ease"
                        }} />
                      </div>
                    </div>
                    {/* 推荐理由 */}
                    <p style={{ fontSize: 12, color: T.text1, lineHeight: 1.75, margin: "0 0 10px" }}>
                      {rec.reason}
                    </p>
                    {/* 优势标签 */}
                    {rec.matched_strengths?.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 8 }}>
                        {rec.matched_strengths.slice(0, 3).map((s, i) => (
                          <Tag key={i} color={T.green}>{s}</Tag>
                        ))}
                      </div>
                    )}
                    {/* 需补充技能 */}
                    {rec.skill_gaps?.length > 0 && (
                      <div>
                        <span style={{ fontSize: 11, color: T.text2 }}>需补充：</span>
                        {rec.skill_gaps.slice(0, 3).map((s, i) => (
                          <Tag key={i} color={T.orange} style={{ marginLeft: 4 }}>{s}</Tag>
                        ))}
                      </div>
                    )}
                    {/* 点击选择提示 */}
                    <div style={{ marginTop: 10, fontSize: 11, color: T.text2, textAlign: "right" }}>
                      {isSelected ? "✓ 已选为目标岗位" : "点击选择此岗位 →"}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {!recLoading && recJobs.length === 0 && !recErr && (
            <div style={{ textAlign: "center", padding: "50px 0", color: T.text2 }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>✦</div>
              <p style={{ color: T.text1, marginBottom: 16 }}>点击"重新推荐"获取 AI 个性化岗位推荐</p>
              <Btn onClick={fetchRecommend} variant="gold">✦ 开始 AI 分析</Btn>
            </div>
          )}
        </div>
      )}

      {/* ── 路径图谱 ── */}
      {view === "graph" && (
        <div>
          <Card style={{ marginBottom: 16, padding: "12px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 12, color: T.text2, whiteSpace: "nowrap" }}>选择岗位：</span>
              <select value={graphJob} onChange={e => setGraphJob(e.target.value)}
                style={{ flex: 1, padding: "8px 12px", fontSize: 13, maxWidth: 280 }}>
                {graphJobs.map(j => <option key={j} value={j}>{j}</option>)}
              </select>
            </div>
          </Card>

          {pathLoading && <Loading text="加载路径图谱…" />}

          {!pathLoading && pathData && (
            <div>
              {/* 垂直晋升路径 */}
              <Card style={{ marginBottom: 16 }}>
                <SectionTitle icon="↑">垂直晋升路径</SectionTitle>
                <div style={{ display: "flex", alignItems: "stretch", gap: 0, overflowX: "auto", padding: "4px 0 12px" }}>
                  {(pathData.vertical_path || []).map((v, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
                      <div style={{
                        background: i === 0 ? T.gold + "15" : T.bg0,
                        border: `1px solid ${i === 0 ? T.gold : T.line2}`,
                        borderRadius: 8, padding: "14px 18px", textAlign: "center", minWidth: 120,
                        boxShadow: i === 0 ? `0 0 12px ${T.gold}20` : "none",
                      }}>
                        <div style={{ fontSize: 10, color: T.text2, marginBottom: 5, letterSpacing: ".6px", textTransform: "uppercase" }}>{v.level || v.stage}</div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: T.text0, marginBottom: 6 }}>{v.level_name || v.title}</div>
                        <div style={{ fontSize: 12, color: T.green, fontFamily: "JetBrains Mono, monospace", marginBottom: 3 }}>
                          {v.salary_range || v.salary}
                        </div>
                        <div style={{ fontSize: 10, color: T.text2 }}>{v.typical_years || v.years_required || v.years}</div>
                        {(v.key_milestone || v.key_skills?.length > 0) && (
                          <div style={{ marginTop: 8, fontSize: 10, color: T.text2, lineHeight: 1.5 }}>
                            {v.key_milestone
                              ? v.key_milestone
                              : v.key_skills.slice(0, 2).map((s, j) => <Tag key={j} color={T.cyan}>{s}</Tag>)
                            }
                          </div>
                        )}
                      </div>
                      {i < (pathData.vertical_path.length - 1) && (
                        <div style={{ padding: "0 6px", color: T.gold, fontSize: 18, flexShrink: 0 }}>→</div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>

              {/* 转岗路径卡片 */}
              <Card>
                <SectionTitle icon="↔">横向转岗路径</SectionTitle>
                <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
                  {(pathData.lateral_paths || []).map((l, i) => (
                    <div key={i} style={{ padding: "14px 16px", background: T.bg0, borderRadius: 8, border: `1px solid ${T.line2}`, borderLeft: `3px solid ${DIFF_COLOR[l.difficulty] || T.gold}` }}>
                      <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: T.text0 }}>→ {l.target_job || l.target}</span>
                        <Tag color={DIFF_COLOR[l.difficulty] || T.gold}>{l.difficulty}</Tag>
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: 10, color: T.text2, marginBottom: 4 }}>需补充技能</div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {(l.required_skills || l.skills_to_add || []).map((s, j) => <Tag key={j} color={T.gold}>{s}</Tag>)}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 16, fontSize: 11, color: T.text2 }}>
                        <span>⏱ {l.transition_period || l.period}</span>
                        {l.tips && <span>💡 {l.tips}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {!pathLoading && !pathData && (
            <Empty icon="🗺" text="未找到该岗位的路径数据" sub="请选择其他岗位" />
          )}
        </div>
      )}

      {/* 底部 */}
      <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20, paddingTop: 16, borderTop: `1px solid ${T.line}` }}>
        <span style={{ fontSize: 12, color: T.text2 }}>
          {selectedJob
            ? <span style={{ color: T.gold }}>✓ 已选：{selectedJob.title}</span>
            : "请在列表中点击选择目标岗位"}
        </span>
        <Btn onClick={onNext} disabled={!selectedJob} variant="gold">下一步：人岗匹配 →</Btn>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// 步骤4：人岗匹配
// ══════════════════════════════════════════════════════════════════
function Step4({ studentData, profile, selectedJob, matchResult, setMatchResult, onNext }) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const doMatch = async () => {
    if (!selectedJob || !profile) return;
    setLoading(true); setErr("");
    try {
      const res = await api("/match/score", {
        method: "POST",
        body: JSON.stringify({
          student_profile: profile,
          student_info: {
            name: studentData.name,
            major: studentData.major,
            university: studentData.university || "",
            education_level: studentData.education_level || "本科",
            graduation_year: studentData.graduation_year || "2025",
          },
          target_job: selectedJob.title,
        }),
      }, 60000);
      setMatchResult(res.match_result);
    } catch (e) { setErr(e.message); }
    setLoading(false);
  };

  const DIM_CFG = [
    { key: "basic_requirements", label: "基础要求", icon: "◎", color: T.cyan },
    { key: "professional_skills", label: "职业技能", icon: "◆", color: T.gold },
    { key: "professional_quality", label: "职业素养", icon: "◈", color: T.green },
    { key: "development_potential", label: "发展潜力", icon: "◉", color: "#a78bfa" },
  ];

  const LEVEL_COLOR = {
    "高度匹配": T.green, "较好匹配": T.gold,
    "基本匹配": T.orange, "有差距": T.red, "暂不建议": T.red,
  };

  const score = matchResult?.overall_score_computed ?? matchResult?.overall_score ?? 0;
  const level = matchResult?.match_level || "";

  return (
    <div className="fade-up">
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, fontFamily: "Sora, sans-serif", marginBottom: 4 }}>人岗匹配分析</h2>
        <p style={{ fontSize: 13, color: T.text2 }}>基础25% + 技能40% + 素养20% + 潜力15%，四维加权评分</p>
      </div>

      {/* 目标岗位信息栏 */}
      <Card style={{ marginBottom: 16, padding: "14px 18px" }} glow>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div style={{ width: 42, height: 42, background: T.gold + "18", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0 }}>◆</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: T.text0 }}>{selectedJob?.title}</div>
            <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>
              {selectedJob?.company_name} · {selectedJob?.city || ""}
              {selectedJob?.salary_min ? ` · ${(selectedJob.salary_min / 1000).toFixed(0)}-${(selectedJob.salary_max / 1000).toFixed(0)}k` : ""}
            </div>
          </div>
        </div>
      </Card>

      {loading && <MatchLoading />}
      <ErrBanner msg={err} onRetry={doMatch} />

      {!matchResult && !loading && (
        <Empty icon="⚡" text="准备开始人岗匹配分析" sub="AI 将从基础要求、职业技能、职业素养、发展潜力四个维度评分">
          <Btn onClick={doMatch} variant="gold" size="lg" style={{ marginTop: 24 }}>开始四维度匹配分析</Btn>
        </Empty>
      )}

      {matchResult && !loading && (
        <div>
          {/* 综合评分大图 */}
          <Card style={{ marginBottom: 16, padding: "24px" }} glow>
            <div className="match-overview" style={{ display: "flex", alignItems: "center", gap: 28 }}>
              <Ring score={Math.round(score)} size={110} color={LEVEL_COLOR[level] || T.gold} thickness={10} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: LEVEL_COLOR[level] || T.gold, marginBottom: 4, fontFamily: "Sora, sans-serif" }}>
                  {level}
                </div>
                <div style={{ fontSize: 12, color: T.text2, marginBottom: 10 }}>综合匹配评分 {score.toFixed(1)} 分</div>
                {matchResult.match_summary && (
                  <p style={{ fontSize: 13, color: T.text1, lineHeight: 1.8, margin: 0, maxWidth: 480 }}>{matchResult.match_summary}</p>
                )}
              </div>
              {/* 权重对比条 */}
              <div style={{ width: 180, flexShrink: 0 }}>
                {DIM_CFG.map(d => {
                  const dim = matchResult.dimensions?.[d.key];
                  if (!dim) return null;
                  return (
                    <div key={d.key} style={{ marginBottom: 10 }}>
                      <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                        <span style={{ fontSize: 11, color: T.text2 }}>{d.label}</span>
                        <span style={{ fontSize: 11, color: d.color, fontFamily: "JetBrains Mono, monospace" }}>
                          {dim.weighted_score?.toFixed(1) || "—"}
                        </span>
                      </div>
                      <Bar value={dim.raw_score || dim.score || 0} color={d.color} h={5} animated />
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>

          {/* 四个维度卡片 */}
          <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
            {DIM_CFG.map(d => {
              const dim = matchResult.dimensions?.[d.key];
              if (!dim) return null;
              const rawScore = dim.raw_score ?? dim.score ?? 0;
              return (
                <Card key={d.key} style={{ borderLeft: `3px solid ${d.color}` }}>
                  <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 16, color: d.color }}>{d.icon}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: T.text0 }}>{d.label}</span>
                    </div>
                    <span style={{ fontSize: 11, color: T.text2 }}>权重 {dim.weight}%</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 10 }}>
                    <Ring score={rawScore} size={56} color={d.color} thickness={5} />
                    <div style={{ flex: 1 }}>
                      <Bar value={rawScore} color={d.color} h={6} />
                      <div style={{ fontSize: 11, color: T.text2 }}>
                        加权分 <span style={{ color: d.color, fontFamily: "JetBrains Mono, monospace" }}>
                          {dim.weighted_score?.toFixed(1) || (rawScore * dim.weight / 100).toFixed(1)}
                        </span>
                      </div>
                    </div>
                  </div>
                  <p style={{ fontSize: 12, color: T.text2, lineHeight: 1.7, margin: "0 0 8px" }}>{dim.analysis}</p>

                  {/* 技能匹配/缺失 */}
                  {(dim.matched_skills || dim.matched_items)?.length > 0 && (
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: 10, color: T.green, marginBottom: 4 }}>✓ 已匹配</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                        {(dim.matched_skills || dim.matched_items).map((s, i) => <Tag key={i} color={T.green}>{s}</Tag>)}
                      </div>
                    </div>
                  )}
                  {(dim.missing_skills || dim.gap_items)?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 10, color: T.orange, marginBottom: 4 }}>→ 待补充</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                        {(dim.missing_skills || dim.gap_items).map((s, i) => <Tag key={i} color={T.orange}>{s}</Tag>)}
                      </div>
                    </div>
                  )}
                  {dim.skill_coverage_rate != null && (
                    <div style={{ marginTop: 8, fontSize: 11, color: T.text2 }}>
                      技能覆盖率 <span style={{ color: d.color, fontFamily: "JetBrains Mono, monospace" }}>{dim.skill_coverage_rate}%</span>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>

          {/* 优先建议 */}
          {matchResult.top_recommendations?.length > 0 && (
            <Card style={{ marginBottom: 16 }}>
              <SectionTitle icon="→">优先提升行动</SectionTitle>
              <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                {matchResult.top_recommendations.map((r, i) => (
                  <div key={i} style={{ padding: "12px 14px", background: T.bg0, borderRadius: 8, borderTop: `2px solid ${T.gold}` }}>
                    <div style={{ fontSize: 10, color: T.gold, marginBottom: 6, letterSpacing: ".6px" }}>P{r.priority} 优先</div>
                    <div style={{ fontSize: 12, color: T.text1, lineHeight: 1.6, marginBottom: 6 }}>{r.action}</div>
                    <div style={{ fontSize: 11, color: T.text2 }}>⏱ {r.timeline}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {matchResult.alternative_jobs?.length > 0 && (
            <Card style={{ marginBottom: 16, padding: "12px 16px" }}>
              <div style={{ fontSize: 12, color: T.text2, marginBottom: 8 }}>备选岗位方向（匹配度更高）</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {matchResult.alternative_jobs.map((j, i) => <Tag key={i} color={T.cyan}>{j}</Tag>)}
              </div>
            </Card>
          )}

          <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", paddingTop: 12, borderTop: `1px solid ${T.line}` }}>
            <Btn onClick={doMatch} variant="ghost">↺ 重新分析</Btn>
            <Btn onClick={onNext} variant="gold">生成职业规划报告 →</Btn>
          </div>
        </div>
      )}

      {!matchResult && !loading && (
        <div style={{ textAlign: "center", marginTop: 20 }}>
          <Btn onClick={doMatch} variant="gold" size="lg">⚡ 开始四维度匹配</Btn>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// 步骤5：职业报告
// ══════════════════════════════════════════════════════════════════
function Step5({ studentData, profile, selectedJob, matchResult, report, setReport, reportWarning, setReportWarning }) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState("summary");
  const [editing, setEditing] = useState(null);   // key of section being edited
  const [editBuf, setEditBuf] = useState("");
  const [polishing, setPolishing] = useState(false);
  const [retryAction, setRetryAction] = useState(null);

  const updateSection = (key, value) => {
    const [section, field] = key.split(".");
    setReport(previous => field
      ? { ...previous, [section]: { ...previous[section], [field]: value } }
      : { ...previous, [section]: value });
  };

  const generate = async () => {
    setLoading(true); setErr("");
    setRetryAction(null);
    try {
      const res = await api("/report/generate", {
        method: "POST",
        body: JSON.stringify({
          student_info: { name: studentData.name, major: studentData.major, university: studentData.university || "", education_level: studentData.education_level || "本科", graduation_year: studentData.graduation_year || "2025" },
          student_profile: profile || {},
          target_job: selectedJob?.title || "",
          match_result: matchResult || null,
          career_goals: null,
          personal_values: [],
        }),
      }, 180000);  // 7章串行约90-150秒，设180秒
      setReport(res.report);
      setReportWarning(res.has_errors ? "部分章节生成失败，已保留成功内容；可重新生成或手动补充。" : "");
      setTab("summary");
    } catch (e) { setErr(e.message); setRetryAction(() => generate); }
    setLoading(false);
  };

  const exportMd = async () => {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 30000);
      const res = await fetch(`${API}/report/export/markdown`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report, student_name: studentData.name, target_job: selectedJob?.title }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`); }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${studentData.name || "报告"}_${selectedJob?.title || "职业"}_职业规划报告.md`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) { alert("导出失败：" + (e.name === "AbortError" ? "请求超时，请重试" : e.message)); }
  };

  const exportWord = async () => {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 30000);
      const res = await fetch(`${API}/report/export/word`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report, student_name: studentData.name, target_job: selectedJob?.title }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`); }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${studentData.name || "报告"}_${selectedJob?.title || "职业"}_职业规划报告.docx`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) { alert("Word导出失败：" + (e.name === "AbortError" ? "请求超时，请重试" : e.message)); }
  };

  const startEdit = (key, content) => {
    setEditing(key);
    setEditBuf(typeof content === "string" ? content : JSON.stringify(content, null, 2));
  };
  const saveEdit = key => {
    try {
      updateSection(key, editBuf);
    } catch (e) { setErr(e.message || "保存失败，请重试"); }
    setEditing(null);
  };

  const polishSection = async (key, content) => {
    if (!content) return;
    setErr("");
    setPolishing(true);
    try {
      const res = await api("/report/polish", {
        method: "POST",
        body: JSON.stringify({ section_key: key, section_content: typeof content === "string" ? content : JSON.stringify(content), polish_type: "comprehensive" }),
      }, 45000);
      updateSection(key, res.polished);
    } catch (e) {
      setErr(e.message || "润色失败，请稍后重试");
      setRetryAction(() => () => polishSection(key, content));
    }
    setPolishing(false);
  };

  const TABS = [
    { id: "summary", label: "执行摘要", icon: "◎" },
    { id: "s1", label: "职业探索", icon: "◉" },
    { id: "s2", label: "职业目标", icon: "◆" },
    { id: "s3", label: "行动计划", icon: "◈" },
    { id: "s4", label: "竞争策略", icon: "◇" },
    { id: "s5", label: "资源推荐", icon: "✦" },
  ];

  // 章节内容编辑框
  const renderEditableSection = ({ skey, content }) => {
    const isEditing = editing === skey;
    const text = typeof content === "string" ? content : "";
    return (
      <div style={{ position: "relative" }}>
        {isEditing ? (
          <div>
            <textarea
              value={editBuf} onChange={e => setEditBuf(e.target.value)}
              rows={6}
              style={{ width: "100%", padding: "10px 12px", fontSize: 13, background: T.bg0, border: `1px solid ${T.gold}`, borderRadius: 6, color: T.text0, resize: "vertical" }}
            />
            <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
              <Btn onClick={() => saveEdit(skey)} variant="gold" size="sm">✓ 保存</Btn>
              <Btn onClick={() => setEditing(null)} variant="ghost" size="sm">取消</Btn>
            </div>
          </div>
        ) : (
          <div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 5, marginBottom: 6 }}>
              <Btn onClick={() => startEdit(skey, content)} variant="ghost" size="sm">✏ 编辑</Btn>
              <Btn onClick={() => polishSection(skey, content)} disabled={polishing} variant="outline" size="sm">{polishing ? "…" : "✨ 润色"}</Btn>
            </div>
            <p style={{ fontSize: 14, color: T.text1, lineHeight: 1.85, margin: 0 }}>{text}</p>
          </div>
        )}
      </div>
    );
  };

  // 行动计划表格
  const ActionTable = ({ actions = [] }) => (
    <div>
      {actions.map((a, i) => (
        <div key={i} style={{ padding: "10px 14px", background: T.bg0, borderRadius: 8, marginBottom: 8, borderLeft: `3px solid ${T.gold}` }}>
          <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <Tag color={T.cyan}>{a.category || "行动"}</Tag>
              <span style={{ fontSize: 13, color: T.text0, fontWeight: 500 }}>{a.action}</span>
            </div>
            <span style={{ fontSize: 11, color: T.text2, fontFamily: "JetBrains Mono, monospace", flexShrink: 0 }}>⏰ {a.deadline}</span>
          </div>
          <div style={{ display: "flex", gap: 16, fontSize: 11, color: T.text2 }}>
            {a.resource && <span>📖 {a.resource}</span>}
            {(a.success_metric || a.metric) && <span>✓ {a.success_metric || a.metric}</span>}
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <div className="fade-up">
      <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, fontFamily: "Sora, sans-serif", marginBottom: 4 }}>职业生涯发展报告</h2>
          <p style={{ fontSize: 13, color: T.text2 }}>AI 生成个性化规划报告，支持手动编辑与 AI 润色</p>
        </div>
        {report && (
          <div className="action-group" style={{ display: "flex", gap: 8 }}>
            <Btn onClick={generate} variant="ghost" size="sm">↺ 重新生成</Btn>
            <Btn onClick={exportMd} variant="ghost" size="sm">⬇ Markdown</Btn>
            <Btn onClick={exportWord} variant="gold" size="sm">⬇ Word</Btn>
          </div>
        )}
      </div>

      {loading && <ReportLoading />}
      <ErrBanner msg={err} onRetry={retryAction} />

      {reportWarning && <p role="status" style={{ color: T.orange, fontSize: 13, lineHeight: 1.8 }}>{reportWarning}</p>}

      {!report && !loading && (
        <div>
          {/* 报告预览卡 */}
          <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 28 }}>
            {[
              { icon: "◎", label: "执行摘要", desc: "核心竞争力与关键结论" },
              { icon: "◆", label: "职业目标", desc: "短期/中期/长期路径规划" },
              { icon: "◈", label: "行动计划", desc: "含评估周期与动态调整机制" },
              { icon: "◉", label: "职业探索", desc: "岗位匹配与机遇分析" },
              { icon: "◇", label: "竞争策略", desc: "差异化核心优势策略" },
              { icon: "✦", label: "资源推荐", desc: "课程、证书、实践建议" },
            ].map((s, i) => (
              <Card key={i} style={{ padding: "16px", textAlign: "center" }}>
                <div style={{ fontSize: 24, color: T.gold, marginBottom: 8, fontFamily: "Sora, sans-serif" }}>{s.icon}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text0, marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: 11, color: T.text2 }}>{s.desc}</div>
              </Card>
            ))}
          </div>

          {/* 信息确认卡 */}
          <Card style={{ marginBottom: 24, padding: "16px 20px", background: T.gold + "08", borderColor: T.gold + "33" }}>
            <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {[
                ["学生", studentData.name || "—"],
                ["专业", studentData.major || "—"],
                ["目标岗位", selectedJob?.title || "—"],
                ["匹配评分", matchResult ? `${(matchResult.overall_score_computed ?? matchResult.overall_score ?? 0).toFixed(1)} 分` : "未匹配"],
              ].map(([k, v]) => (
                <div key={k} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: T.text2, marginBottom: 4, textTransform: "uppercase", letterSpacing: ".6px" }}>{k}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: T.text0 }}>{v}</div>
                </div>
              ))}
            </div>
          </Card>

          <div style={{ textAlign: "center" }}>
            <Btn onClick={generate} variant="gold" size="lg">◇ 生成我的职业规划报告</Btn>
          </div>
        </div>
      )}

      {report && !loading && (
        <div>
          {/* 报告头 */}
          <Card style={{ marginBottom: 16, padding: "20px 24px", background: `linear-gradient(135deg, ${T.gold}0a, ${T.cyan}05)`, borderColor: T.gold + "33" }} glow>
            <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text0, fontFamily: "Sora, sans-serif", marginBottom: 4 }}>
                  {report.report_title || `${studentData.name} · 职业生涯发展规划报告`}
                </h3>
                <div style={{ fontSize: 11, color: T.text2, fontFamily: "JetBrains Mono, monospace" }}>
                  {report.generated_at} · 目标岗位：{selectedJob?.title}
                </div>
              </div>
              <div className="action-group" style={{ display: "flex", gap: 8 }}>
                <Tag color={T.gold}>{matchResult?.match_level || "未匹配"}</Tag>
              </div>
            </div>
          </Card>

          {/* Tab 导航 */}
          <div className="report-tabs" style={{ display: "flex", gap: 2, marginBottom: 16, borderBottom: `1px solid ${T.line2}`, overflowX: "auto" }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                padding: "9px 16px", background: "none", fontSize: 12, whiteSpace: "nowrap",
                color: tab === t.id ? T.gold : T.text2,
                borderBottom: tab === t.id ? `2px solid ${T.gold}` : "2px solid transparent",
                fontWeight: tab === t.id ? 600 : 400,
                fontFamily: "Sora, sans-serif", marginBottom: -1,
              }}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>

          {/* ── 执行摘要 ── */}
          {tab === "summary" && (
            <div className="fade-up">
              <Card style={{ marginBottom: 14 }}>
                <SectionTitle icon="◎">执行摘要</SectionTitle>
                {renderEditableSection({ skey: "executive_summary", content: report.executive_summary })}
              </Card>

              {/* 关键数字 */}
              <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 14 }}>
                {[
                  { label: "匹配评分", val: `${(matchResult?.overall_score_computed ?? matchResult?.overall_score ?? 0).toFixed(1)}`, unit: "分", color: T.gold },
                  { label: "竞争力", val: `${profile?.competitiveness_score ?? "—"}`, unit: "", color: T.cyan },
                  { label: "信息完整度", val: `${profile?.completeness_score ?? "—"}`, unit: "", color: T.green },
                  { label: "匹配等级", val: matchResult?.match_level || "—", unit: "", color: T.gold },
                ].map(({ label, val, unit, color }) => (
                  <Card key={label} style={{ textAlign: "center", padding: "14px 10px" }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color, fontFamily: "JetBrains Mono, monospace" }}>{val}{unit}</div>
                    <div style={{ fontSize: 11, color: T.text2, marginTop: 4 }}>{label}</div>
                  </Card>
                ))}
              </div>

              {report.conclusion && (
                <div style={{ padding: "16px 20px", background: T.gold + "08", borderRadius: 10, border: `1px solid ${T.gold}22`, textAlign: "center" }}>
                  <p style={{ fontSize: 14, color: T.text1, lineHeight: 1.9, margin: 0, fontStyle: "italic" }}>💫 {report.conclusion}</p>
                </div>
              )}
            </div>
          )}

          {/* ── 职业探索 ── */}
          {tab === "s1" && (() => {
            const s = report.section1_career_exploration || {};
            return (
              <div className="fade-up">
                <Card style={{ marginBottom: 12 }}>
                  <SectionTitle icon="◉">{s.title || "第一章 职业探索与岗位匹配"}</SectionTitle>
                  {renderEditableSection({ skey: "section1_career_exploration.match_overview", content: s.match_overview })}
                </Card>
                <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                  <Card>
                    <SectionTitle icon="✦">行业机遇</SectionTitle>
                    <p style={{ fontSize: 13, color: T.text1, lineHeight: 1.8 }}>{s.opportunity_analysis}</p>
                  </Card>
                  <Card>
                    <SectionTitle icon="⚠">竞争风险</SectionTitle>
                    <p style={{ fontSize: 13, color: T.text1, lineHeight: 1.8 }}>{s.risk_analysis}</p>
                  </Card>
                </div>
                {s.skill_gap_analysis && (
                  <Card style={{ marginBottom: 12 }}>
                    <SectionTitle icon="→">核心技能差距</SectionTitle>
                    <p style={{ fontSize: 13, color: T.text1, lineHeight: 1.8 }}>{s.skill_gap_analysis}</p>
                  </Card>
                )}
                {s.transfer_options?.length > 0 && (
                  <Card>
                    <SectionTitle icon="↔">转岗方向建议</SectionTitle>
                    <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                      {s.transfer_options.map((t, i) => (
                        <div key={i} style={{ padding: "10px 12px", background: T.bg0, borderRadius: 6, borderLeft: `3px solid ${T.cyan}` }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: T.text0, marginBottom: 4 }}>→ {t.target}</div>
                          <Tag color={{ 较易: T.green, 中等: T.gold, 较难: T.red }[t.difficulty] || T.gold}>{t.difficulty}</Tag>
                          <p style={{ fontSize: 11, color: T.text2, marginTop: 6, lineHeight: 1.6 }}>{t.reason}</p>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            );
          })()}

          {/* ── 职业目标 ── */}
          {tab === "s2" && (() => {
            const s = report.section2_career_goals || {};
            const st = s.short_term_goal || {};
            const mt = s.mid_term_goal || {};
            return (
              <div className="fade-up">
                <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                  {[
                    { data: st, color: T.gold, icon: "◆", title: "短期目标" },
                    { data: mt, color: T.cyan, icon: "◉", title: "中期目标" },
                  ].map(({ data, color, icon, title }) => (
                    <Card key={title} style={{ borderTop: `3px solid ${color}` }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
                        <span style={{ color, fontSize: 18 }}>{icon}</span>
                        <span style={{ fontSize: 13, fontWeight: 600, color }}>{title}（{data.timeline}）</span>
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: T.text0, marginBottom: 8 }}>{data.position}</div>
                      <p style={{ fontSize: 13, color: T.text1, lineHeight: 1.8, marginBottom: 10 }}>{data.description}</p>
                      {data.key_milestones?.length > 0 && (
                        <div>
                          <div style={{ fontSize: 10, color: T.text2, marginBottom: 6, textTransform: "uppercase", letterSpacing: ".6px" }}>关键里程碑</div>
                          {data.key_milestones.map((m, i) => (
                            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6, fontSize: 12, color: T.text1, alignItems: "flex-start" }}>
                              <span style={{ color, flexShrink: 0 }}>◆</span>
                              <span style={{ lineHeight: 1.6 }}>{m}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </Card>
                  ))}
                </div>

                <Card style={{ marginBottom: 12 }}>
                  <SectionTitle icon="◇">长期愿景</SectionTitle>
                  <p style={{ fontSize: 14, color: T.text1, lineHeight: 1.8 }}>{s.long_term_vision}</p>
                </Card>

                <Card style={{ marginBottom: 12 }}>
                  <SectionTitle icon="→">完整职业发展路径</SectionTitle>
                  <p style={{ fontSize: 14, color: T.text1, lineHeight: 1.8 }}>{s.career_path_description}</p>
                </Card>

                {/* 薪资增长预测表 */}
                {s.salary_growth_forecast?.length > 0 && (
                  <Card>
                    <SectionTitle icon="◎">薪资成长预测</SectionTitle>
                    <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                      {s.salary_growth_forecast.map((row, i) => (
                        <div key={i} style={{ padding: "12px 14px", background: T.bg0, borderRadius: 8, textAlign: "center", borderTop: `2px solid ${T.gold}` }}>
                          <div style={{ fontSize: 11, color: T.text2, marginBottom: 6 }}>{row.period}</div>
                          <div style={{ fontSize: 15, fontWeight: 700, color: T.green, fontFamily: "JetBrains Mono, monospace" }}>{row.expected_salary}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            );
          })()}

          {/* ── 行动计划 ── */}
          {tab === "s3" && (() => {
            const s = report.section3_action_plan || {};
            return (
              <div className="fade-up">
                <Card style={{ marginBottom: 12 }}>
                  <div className="responsive-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                    <SectionTitle icon="◈">短期行动计划（{s.short_term_plan?.timeline}）</SectionTitle>
                  </div>
                  <ActionTable actions={s.short_term_plan?.actions || []} />
                </Card>
                <Card style={{ marginBottom: 12 }}>
                  <SectionTitle icon="◉">中期行动计划（{s.mid_term_plan?.timeline}）</SectionTitle>
                  <ActionTable actions={s.mid_term_plan?.actions || []} />
                </Card>
                <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <Card>
                    <SectionTitle icon="✦">评估机制</SectionTitle>
                    <p style={{ fontSize: 13, color: T.text1, lineHeight: 1.8, marginBottom: 12 }}>{s.evaluation_cycle}</p>
                    {s.evaluation_metrics?.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {s.evaluation_metrics.map((m, i) => <Tag key={i} color={T.gold}>{m}</Tag>)}
                      </div>
                    )}
                  </Card>
                  <Card>
                    <SectionTitle icon="→">动态调整机制</SectionTitle>
                    {s.adjustment_triggers?.length > 0 && (
                      <div style={{ marginBottom: 10 }}>
                        <div style={{ fontSize: 10, color: T.text2, marginBottom: 6, textTransform: "uppercase", letterSpacing: ".6px" }}>触发情形</div>
                        {s.adjustment_triggers.map((t, i) => (
                          <div key={i} style={{ fontSize: 12, color: T.text1, marginBottom: 5, display: "flex", gap: 6, alignItems: "flex-start" }}>
                            <span style={{ color: T.orange, flexShrink: 0 }}>⚡</span>{t}
                          </div>
                        ))}
                      </div>
                    )}
                    <p style={{ fontSize: 12, color: T.text1, lineHeight: 1.7 }}>{s.adjustment_strategy}</p>
                  </Card>
                </div>
              </div>
            );
          })()}

          {/* ── 竞争策略 ── */}
          {tab === "s4" && (() => {
            const s = report.section4_competitive_strategy || {};
            return (
              <div className="fade-up">
                <Card style={{ marginBottom: 12 }}>
                  <SectionTitle icon="◇">核心竞争优势</SectionTitle>
                  {(s.core_advantages || []).map((a, i) => (
                    <div key={i} style={{ display: "flex", gap: 10, marginBottom: 10, padding: "10px 12px", background: T.bg0, borderRadius: 6, borderLeft: `3px solid ${T.gold}` }}>
                      <span style={{ color: T.gold, fontWeight: 700, flexShrink: 0 }}>✦</span>
                      <span style={{ fontSize: 13, color: T.text1, lineHeight: 1.7 }}>{a}</span>
                    </div>
                  ))}
                </Card>
                <Card style={{ marginBottom: 12 }}>
                  <SectionTitle icon="→">差异化竞争策略</SectionTitle>
                  <p style={{ fontSize: 14, color: T.text1, lineHeight: 1.85 }}>{s.differentiation_strategy}</p>
                </Card>
                {s.improvement_priority?.length > 0 && (
                  <Card>
                    <SectionTitle icon="◉">重点提升计划</SectionTitle>
                    <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                      {s.improvement_priority.map((p, i) => (
                        <div key={i} style={{ padding: "12px 14px", background: T.bg0, borderRadius: 8, borderTop: `2px solid ${T.cyan}` }}>
                          <div style={{ fontSize: 11, color: T.cyan, marginBottom: 4 }}>P{p.rank || i + 1}</div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: T.text0, marginBottom: 6 }}>{p.item}</div>
                          <div style={{ fontSize: 12, color: T.text2, marginBottom: 4 }}>方法：{p.method}</div>
                          <div style={{ fontSize: 12, color: T.green }}>效果：{p.expected_outcome}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            );
          })()}

          {/* ── 资源推荐 ── */}
          {tab === "s5" && (() => {
            const s = report.section5_resources || {};
            return (
              <div className="fade-up">
                <div className="responsive-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                  <Card>
                    <SectionTitle icon="◎">推荐在线课程</SectionTitle>
                    {(s.online_courses || []).map((c, i) => (
                      <div key={i} style={{ padding: "10px 12px", background: T.bg0, borderRadius: 6, marginBottom: 8 }}>
                        <div style={{ fontSize: 11, color: T.gold, marginBottom: 3 }}>{c.platform}</div>
                        <div style={{ fontSize: 13, fontWeight: 500, color: T.text0, marginBottom: 3 }}>{c.course}</div>
                        <div style={{ fontSize: 11, color: T.text2 }}>{c.purpose}</div>
                        {c.duration_weeks && <div style={{ fontSize: 10, color: T.text2, marginTop: 3 }}>约 {c.duration_weeks} 周</div>}
                      </div>
                    ))}
                  </Card>
                  <Card>
                    <SectionTitle icon="✦">推荐证书</SectionTitle>
                    {(s.certifications || []).map((c, i) => (
                      <div className="responsive-row" key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", background: T.bg0, borderRadius: 6, marginBottom: 8 }}>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 500, color: T.text0, marginBottom: 2 }}>{c.cert_name}</div>
                          <div style={{ fontSize: 11, color: T.text2 }}>{c.issuing_body}</div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <Tag color={{ 高: T.red, 中: T.gold, 低: T.green }[c.priority] || T.gold}>{c.priority}优先</Tag>
                          {c.prep_weeks && <div style={{ fontSize: 10, color: T.text2, marginTop: 4 }}>备考 {c.prep_weeks} 周</div>}
                        </div>
                      </div>
                    ))}
                  </Card>
                </div>
                {s.practice_projects?.length > 0 && (
                  <Card style={{ marginBottom: 12 }}>
                    <SectionTitle icon="◈">实践项目建议</SectionTitle>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {s.practice_projects.map((p, i) => <Tag key={i} color={T.cyan}>{p}</Tag>)}
                    </div>
                  </Card>
                )}
                {s.networking_advice && (
                  <Card>
                    <SectionTitle icon="◉">人脉建设建议</SectionTitle>
                    <p style={{ fontSize: 13, color: T.text1, lineHeight: 1.8 }}>{s.networking_advice}</p>
                  </Card>
                )}
              </div>
            );
          })()}

          {/* 底部导出栏 */}
          <div className="responsive-row" style={{ marginTop: 20, padding: "14px 20px", background: T.bg1, border: `1px solid ${T.line2}`, borderRadius: 10, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: T.text2 }}>报告生成于 {report.generated_at} · 支持手动编辑和 AI 润色</span>
            <div className="action-group" style={{ display: "flex", gap: 8 }}>
              <Btn onClick={generate} variant="ghost" size="sm">↺ 重新生成</Btn>
              <Btn onClick={exportMd} variant="ghost">⬇ Markdown</Btn>
              <Btn onClick={exportWord} variant="gold">⬇ 导出 Word 报告</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Empty 组件补丁（支持 children）
// ══════════════════════════════════════════════════════════════════
// 覆写原 Empty 使其支持 children
const EmptyFull = ({ icon, text, sub, children }) => (
  <div style={{ textAlign: "center", padding: "50px 0", color: T.text2 }}>
    <div style={{ fontSize: 44, marginBottom: 12, filter: "grayscale(30%)" }}>{icon}</div>
    <p style={{ color: T.text1, fontSize: 15, marginBottom: 6 }}>{text}</p>
    {sub && <p style={{ fontSize: 12, marginBottom: 0 }}>{sub}</p>}
    {children}
  </div>
);

// ══════════════════════════════════════════════════════════════════
// 主 App
// ══════════════════════════════════════════════════════════════════
const DEFAULT_STUDENT = {
  name: "", major: "", university: "", education_level: "本科",
  graduation_year: "2025", gpa: "",
  skills: [], certificates: [], internships: [], projects: [], awards: [],
  self_introduction: "", target_jobs: [], target_cities: [],
  expected_salary: "", work_style: "", willing_to_relocate: false,
};

// ── 历史记录工具函数 ────────────────────────────────────────────
const HISTORY_KEY = "career_planner_history";
const MAX_HISTORY = 5;

function saveHistory(studentData) {
  if (!studentData.name || !studentData.major) return;
  try {
    const existing = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]");
    // 去掉同名的旧记录，再插入最新
    const filtered = existing.filter(h => h.name !== studentData.name);
    const newList = [{ ...studentData, _savedAt: new Date().toLocaleString("zh-CN") }, ...filtered]
      .slice(0, MAX_HISTORY);
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(newList));
  } catch { }
}

function loadHistory() {
  try {
    return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]");
  } catch { return []; }
}

export default function CareerPlanner() {
  const [step, setStep] = useState(1);
  const [studentData, setStudentData] = useState(DEFAULT_STUDENT);
  const [profile, setProfile] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [matchResult, setMatchResult] = useState(null);
  const [report, setReport] = useState(null);
  const [reportWarning, setReportWarning] = useState("");

  const clearReport = () => { setReport(null); setReportWarning(""); };
  const updateStudent = change => {
    setStudentData(previous => typeof change === "function" ? change(previous) : change);
    setProfile(null); setSelectedJob(null); setMatchResult(null); clearReport();
  };
  const updateProfile = value => {
    setProfile(value); setMatchResult(null); clearReport();
  };
  const updateJob = value => {
    setSelectedJob(value); setMatchResult(null); clearReport();
  };
  const updateMatch = value => { setMatchResult(value); clearReport(); };
  const maxStep = matchResult ? 5 : profile && selectedJob ? 4 : profile ? 3 : step === 2 ? 2 : 1;

  return (
    <>
      <style>{GLOBAL_CSS}</style>

      {/* 极光背景 */}
      <div style={{
        position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none",
        background: `radial-gradient(ellipse 80% 50% at 20% -10%, ${T.gold}08, transparent),
                     radial-gradient(ellipse 60% 40% at 80% 110%, ${T.cyan}06, transparent)`,
      }} />

      <div style={{ position: "relative", zIndex: 1, minHeight: "100vh" }}>
        <Header step={step} setStep={setStep} maxStep={maxStep} />

        <main style={{ maxWidth: 980, margin: "0 auto", padding: "28px 24px 60px" }}>
          {step === 1 && (
            <Step1
              data={studentData}
              setData={updateStudent}
              onNext={() => setStep(2)}
            />
          )}
          {step === 2 && (
            <Step2
              studentData={studentData}
              profile={profile}
              setProfile={updateProfile}
              onNext={() => setStep(3)}
            />
          )}
          {step === 3 && (
            <Step3
              selectedJob={selectedJob}
              setSelectedJob={updateJob}
              onNext={() => setStep(4)}
              profile={profile}
              studentData={studentData}
            />
          )}
          {step === 4 && (
            <Step4
              studentData={studentData}
              profile={profile}
              selectedJob={selectedJob}
              matchResult={matchResult}
              setMatchResult={updateMatch}
              onNext={() => setStep(5)}
            />
          )}
          {step === 5 && (
            <Step5
              studentData={studentData}
              profile={profile}
              selectedJob={selectedJob}
              matchResult={matchResult}
              report={report}
              setReport={setReport}
              reportWarning={reportWarning}
              setReportWarning={setReportWarning}
            />
          )}
        </main>
      </div>
    </>
  );
}
