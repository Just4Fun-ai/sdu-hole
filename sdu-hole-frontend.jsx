import { useState, useEffect, useCallback, useRef } from "react";

// ============================================================
// 山大树洞 SDU Hole — 完整前端（连接后端 API）
// 后端地址默认 http://localhost:8000
// ============================================================

const API =
  (typeof window !== "undefined" && window.__SDU_API_BASE__) ||
  (typeof window !== "undefined" && window.localStorage?.getItem("sdu_api_base")) ||
  "http://localhost:8000";

// ---- API helpers ----
async function api(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (res.status === 401) {
      sessionStorage.removeItem("sdu_token");
      throw new Error("登录已过期，请重新登录");
    }
    throw new Error(err.detail || `请求失败 (${res.status})`);
  }
  return res.json();
}

function formatAuthErrorMessage(message) {
  const msg = String(message || "请求失败");
  if (msg.includes("SMTP")) {
    return `${msg}。请检查 .env 的 SMTP 配置；若使用山大邮箱，建议在校园网环境测试。`;
  }
  if (msg.includes("请求过于频繁")) {
    return `${msg}（每次发送后需等待 60 秒再重发）`;
  }
  return msg;
}

// ---- Design tokens ----
const T = {
  bg: "#f6f5f0",
  surface: "#ffffff",
  surfaceHover: "#fafaf7",
  border: "#e8e6df",
  borderLight: "#f0eeea",
  accent: "#b44a1c",
  accentHover: "#9a3e17",
  accentSoft: "#fdf0ea",
  accentBorder: "rgba(180,74,28,0.15)",
  text: "#2c2a25",
  textSecondary: "#78756d",
  textTertiary: "#a09d96",
  danger: "#c53030",
  shadow: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)",
  shadowHover: "0 4px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)",
  radius: 10,
  radiusLg: 14,
  font: "'LXGW WenKai', 'Noto Serif SC', 'Songti SC', Georgia, serif",
  fontSans: "'LXGW WenKai', 'Noto Sans SC', 'PingFang SC', sans-serif",
};

const TAGS = ["课程评价", "老师评价", "校园活动", "生活吐槽", "求助", "表白墙", "二手交易", "考研交流"];
const TAG_COLORS = {
  "课程评价": { bg: "#eef2ff", text: "#4338ca", border: "#c7d2fe" },
  "老师评价": { bg: "#fef3c7", text: "#92400e", border: "#fcd34d" },
  "校园活动": { bg: "#ecfdf5", text: "#065f46", border: "#a7f3d0" },
  "生活吐槽": { bg: "#fdf2f8", text: "#9d174d", border: "#fbcfe8" },
  "求助":     { bg: "#fff7ed", text: "#9a3412", border: "#fed7aa" },
  "表白墙":   { bg: "#fce7f3", text: "#be185d", border: "#f9a8d4" },
  "二手交易": { bg: "#f0fdfa", text: "#115e59", border: "#99f6e4" },
  "考研交流": { bg: "#eef2ff", text: "#3730a3", border: "#a5b4fc" },
};

// ---- Time formatting ----
function timeAgo(dateStr) {
  const now = new Date();
  const d = new Date(dateStr);
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`;
  return d.toLocaleDateString("zh-CN");
}

// ============================================================
// Shared CSS (injected once)
// ============================================================
const globalCSS = `
  @import url('https://fonts.googleapis.com/css2?family=LXGW+WenKai:wght@300;400;700&family=Noto+Serif+SC:wght@400;700&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: ${T.bg}; }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes slideUp {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
  }
  @keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.3); }
  }

  .card-enter {
    animation: fadeUp 0.35s ease-out both;
  }

  input:focus, textarea:focus {
    outline: none;
    border-color: ${T.accent} !important;
    box-shadow: 0 0 0 3px ${T.accentSoft} !important;
  }

  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: ${T.border}; border-radius: 10px; }

  .tag-chip {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    line-height: 1.4;
    white-space: nowrap;
  }
`;

// ============================================================
// Login Page
// ============================================================
function LoginPage({ onLogin }) {
  const [step, setStep] = useState("input"); // input | verify
  const [studentId, setStudentId] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [countdown, setCountdown] = useState(0);
  const codeRef = useRef(null);

  useEffect(() => {
    if (countdown > 0) {
      const t = setTimeout(() => setCountdown(c => c - 1), 1000);
      return () => clearTimeout(t);
    }
  }, [countdown]);

  const handleSendCode = async () => {
    if (!studentId || studentId.length < 6) return;
    setLoading(true);
    setError("");
    try {
      await api("/api/auth/send-code", { method: "POST", body: { student_id: studentId } });
      setStep("verify");
      setCountdown(60);
      setTimeout(() => codeRef.current?.focus(), 100);
    } catch (e) {
      setError(formatAuthErrorMessage(e.message));
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (code.length !== 6) return;
    setLoading(true);
    setError("");
    try {
      const data = await api("/api/auth/verify", {
        method: "POST",
        body: { student_id: studentId, code },
      });
      onLogin(data.access_token);
    } catch (e) {
      setError(formatAuthErrorMessage(e.message));
    } finally {
      setLoading(false);
    }
  };

  const s = {
    page: {
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      padding: 20, fontFamily: T.font, background: T.bg,
      backgroundImage: "radial-gradient(circle at 20% 50%, rgba(180,74,28,0.04) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(180,74,28,0.03) 0%, transparent 40%)",
    },
    card: {
      width: "100%", maxWidth: 400, background: T.surface, borderRadius: 20,
      padding: "40px 32px", border: `1px solid ${T.border}`, boxShadow: T.shadow,
      animation: "fadeUp 0.5s ease-out",
    },
    logo: {
      textAlign: "center", marginBottom: 28,
    },
    logoMark: {
      width: 56, height: 56, borderRadius: 16, margin: "0 auto 14px",
      background: `linear-gradient(145deg, ${T.accent}, #d4622c)`,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 26, boxShadow: "0 4px 16px rgba(180,74,28,0.25)",
    },
    title: { fontSize: 22, fontWeight: 700, color: T.text, letterSpacing: 1 },
    subtitle: { fontSize: 13, color: T.textSecondary, marginTop: 6, lineHeight: 1.6 },
    label: { display: "block", fontSize: 13, fontWeight: 500, color: T.textSecondary, marginBottom: 6 },
    input: {
      width: "100%", padding: "12px 14px", borderRadius: T.radius,
      border: `1px solid ${T.border}`, background: T.bg, color: T.text,
      fontSize: 15, fontFamily: T.fontSans, transition: "all 0.2s",
    },
    emailPreview: {
      padding: "10px 14px", borderRadius: T.radius, background: T.accentSoft,
      border: `1px solid ${T.accentBorder}`, fontSize: 13, color: T.accent,
      fontWeight: 500, marginTop: 8, fontFamily: "monospace",
    },
    btn: (disabled) => ({
      width: "100%", padding: "13px 0", borderRadius: T.radius, border: "none",
      background: disabled ? T.border : T.accent, color: disabled ? T.textTertiary : "#fff",
      fontSize: 15, fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
      fontFamily: T.fontSans, transition: "all 0.2s", marginTop: 20,
      boxShadow: disabled ? "none" : "0 2px 8px rgba(180,74,28,0.2)",
    }),
    error: {
      padding: "10px 14px", borderRadius: 8, background: "#fef2f2",
      border: "1px solid #fecaca", color: T.danger, fontSize: 13, marginTop: 12,
    },
    hint: { fontSize: 12, color: T.textTertiary, marginTop: 8, lineHeight: 1.5 },
    footer: { textAlign: "center", fontSize: 11, color: T.textTertiary, marginTop: 24, lineHeight: 1.8 },
  };

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.logo}>
          <div style={s.logoMark}>🕳️</div>
          <div style={s.title}>山大树洞</div>
          <div style={s.subtitle}>SDU Hole · 匿名校园社区</div>
        </div>

        {step === "input" ? (
          <>
            <div style={{ marginBottom: 4 }}>
              <label style={s.label}>学号</label>
              <input
                style={s.input}
                placeholder="请输入你的学号"
                value={studentId}
                onChange={e => setStudentId(e.target.value.replace(/\D/g, ""))}
                maxLength={14}
                onKeyDown={e => e.key === "Enter" && handleSendCode()}
              />
              {studentId.length >= 6 && (
                <div style={s.emailPreview}>
                  📧 验证码将发送至 {studentId}@mail.sdu.edu.cn
                </div>
              )}
              <div style={s.hint}>
                💡 控制台模式会打印在终端；SMTP 模式会发送到邮箱
              </div>
            </div>
            {error && <div style={s.error}>{error}</div>}
            <button
              style={s.btn(loading || studentId.length < 6)}
              onClick={handleSendCode}
              disabled={loading || studentId.length < 6}
            >
              {loading ? "发送中..." : "发送验证码"}
            </button>
          </>
        ) : (
          <>
            <div style={{ textAlign: "center", marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: T.textSecondary, lineHeight: 1.6 }}>
                验证码已发送至
              </div>
              <div style={{ fontSize: 14, color: T.accent, fontWeight: 600, marginTop: 4 }}>
                {studentId}@mail.sdu.edu.cn
              </div>
            </div>
            <input
              ref={codeRef}
              style={{ ...s.input, textAlign: "center", letterSpacing: 12, fontSize: 22, fontWeight: 700 }}
              placeholder="· · · · · ·"
              value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              maxLength={6}
              onKeyDown={e => e.key === "Enter" && handleVerify()}
            />
            <div style={s.hint}>
              💡 控制台模式看后端终端；SMTP 模式看邮箱收件箱/垃圾箱
            </div>
            {error && <div style={s.error}>{error}</div>}
            <button
              style={s.btn(loading || code.length !== 6)}
              onClick={handleVerify}
              disabled={loading || code.length !== 6}
            >
              {loading ? "验证中..." : "验证并登录"}
            </button>
            <div style={{ textAlign: "center", marginTop: 14 }}>
              <button
                style={{ background: "none", border: "none", color: countdown > 0 ? T.textTertiary : T.accent, fontSize: 13, cursor: countdown > 0 ? "default" : "pointer", fontFamily: T.fontSans }}
                onClick={() => { if (countdown === 0) { handleSendCode(); } }}
                disabled={countdown > 0}
              >
                {countdown > 0 ? `${countdown}s 后重新发送` : "重新发送验证码"}
              </button>
            </div>
          </>
        )}

        <div style={s.footer}>
          学号仅用于验证在校生身份，发言完全匿名<br />
          登录即同意《用户协议》和《隐私政策》
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Tag Chip
// ============================================================
function TagChip({ tag, style: extraStyle }) {
  const c = TAG_COLORS[tag] || { bg: "#f3f4f6", text: "#374151", border: "#d1d5db" };
  return (
    <span className="tag-chip" style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}`, ...extraStyle }}>
      {tag}
    </span>
  );
}

// ============================================================
// Post Card
// ============================================================
function PostCard({ post, token, onClick, delay = 0 }) {
  const [liked, setLiked] = useState(post.is_liked);
  const [likeCount, setLikeCount] = useState(post.like_count);
  const [animLike, setAnimLike] = useState(false);

  const handleLike = async (e) => {
    e.stopPropagation();
    try {
      const data = await api(`/api/posts/${post.id}/like`, { method: "POST", token });
      setLiked(data.liked);
      setLikeCount(data.like_count);
      if (data.liked) { setAnimLike(true); setTimeout(() => setAnimLike(false), 400); }
    } catch (e) { console.error(e); }
  };

  const s = {
    card: {
      background: T.surface, borderRadius: T.radiusLg, padding: "18px 20px",
      border: `1px solid ${T.border}`, cursor: "pointer", transition: "all 0.2s",
      animationDelay: `${delay * 60}ms`,
    },
    header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
    anon: { display: "flex", alignItems: "center", gap: 8 },
    avatar: {
      width: 30, height: 30, borderRadius: 8,
      background: `hsl(${(post.id * 67) % 360}, 35%, 88%)`,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 13, fontWeight: 700, color: `hsl(${(post.id * 67) % 360}, 40%, 40%)`,
    },
    name: { fontSize: 13, fontWeight: 600, color: T.text },
    time: { fontSize: 12, color: T.textTertiary },
    content: {
      fontSize: 15, lineHeight: 1.8, color: T.text, marginBottom: 14,
      fontFamily: T.font, wordBreak: "break-word",
    },
    actions: { display: "flex", alignItems: "center", gap: 18 },
    actionBtn: (active) => ({
      display: "flex", alignItems: "center", gap: 5, fontSize: 13,
      color: active ? T.accent : T.textTertiary, cursor: "pointer",
      background: "none", border: "none", fontFamily: T.fontSans,
      transition: "color 0.2s", padding: 0,
    }),
  };

  return (
    <div
      className="card-enter"
      style={s.card}
      onClick={onClick}
      onMouseEnter={e => { e.currentTarget.style.boxShadow = T.shadowHover; e.currentTarget.style.borderColor = T.accentBorder; }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.borderColor = T.border; }}
    >
      <div style={s.header}>
        <div style={s.anon}>
          <div style={s.avatar}>{post.anon_name?.[2] || "?"}</div>
          <div>
            <div style={s.name}>{post.anon_name}</div>
            <div style={s.time}>{timeAgo(post.created_at)}</div>
          </div>
        </div>
        <TagChip tag={post.tag} />
      </div>
      <div style={s.content}>{post.content}</div>
      <div style={s.actions}>
        <button style={s.actionBtn(liked)} onClick={handleLike}>
          <span style={animLike ? { animation: "pulse 0.4s ease" } : {}}>
            {liked ? "❤️" : "🤍"}
          </span>
          {likeCount}
        </button>
        <button style={s.actionBtn(false)} onClick={e => { e.stopPropagation(); onClick(); }}>
          💬 {post.comment_count}
        </button>
      </div>
    </div>
  );
}

// ============================================================
// Post Detail Page
// ============================================================
function PostDetail({ post, token, onBack }) {
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef(null);

  const loadComments = useCallback(async () => {
    try {
      const data = await api(`/api/posts/${post.id}/comments`, { token });
      setComments(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [post.id, token]);

  useEffect(() => { loadComments(); }, [loadComments]);

  const handleSubmit = async () => {
    if (!newComment.trim() || submitting) return;
    setSubmitting(true);
    try {
      const c = await api(`/api/posts/${post.id}/comments`, {
        method: "POST", token, body: { content: newComment.trim() },
      });
      setComments(prev => [...prev, c]);
      setNewComment("");
    } catch (e) { alert(e.message); }
    setSubmitting(false);
  };

  const s = {
    page: { minHeight: "100vh", background: T.bg, fontFamily: T.font },
    container: { maxWidth: 640, margin: "0 auto", padding: "0 16px" },
    header: {
      display: "flex", alignItems: "center", gap: 12, padding: "16px 0",
      borderBottom: `1px solid ${T.border}`, marginBottom: 16,
      position: "sticky", top: 0, background: T.bg, zIndex: 10,
    },
    backBtn: {
      background: "none", border: "none", cursor: "pointer", padding: "6px 10px",
      borderRadius: 8, color: T.textSecondary, fontSize: 14, fontFamily: T.fontSans,
      display: "flex", alignItems: "center", gap: 4, transition: "background 0.2s",
    },
    postCard: {
      background: T.surface, borderRadius: T.radiusLg, padding: 22,
      border: `1px solid ${T.border}`, marginBottom: 20, animation: "fadeUp 0.3s ease-out",
    },
    sectionTitle: {
      fontSize: 14, fontWeight: 600, color: T.textSecondary, padding: "8px 0 12px",
      borderBottom: `1px solid ${T.borderLight}`, marginBottom: 4,
    },
    commentItem: {
      padding: "14px 0", borderBottom: `1px solid ${T.borderLight}`,
      animation: "fadeIn 0.3s ease-out",
    },
    commentBar: {
      position: "fixed", bottom: 0, left: 0, right: 0,
      background: T.surface, borderTop: `1px solid ${T.border}`,
      padding: "12px 16px", display: "flex", gap: 10, alignItems: "center", zIndex: 50,
    },
    commentInput: {
      flex: 1, padding: "10px 14px", borderRadius: T.radius,
      border: `1px solid ${T.border}`, background: T.bg, color: T.text,
      fontSize: 14, fontFamily: T.fontSans, transition: "all 0.2s",
    },
    sendBtn: {
      padding: "10px 18px", borderRadius: T.radius, border: "none",
      background: T.accent, color: "#fff", fontSize: 14, fontWeight: 600,
      cursor: "pointer", fontFamily: T.fontSans, whiteSpace: "nowrap",
      transition: "background 0.2s",
    },
    empty: { textAlign: "center", padding: 40, color: T.textTertiary, fontSize: 14 },
  };

  return (
    <div style={s.page}>
      <div style={s.container}>
        <div style={s.header}>
          <button
            style={s.backBtn}
            onClick={onBack}
            onMouseEnter={e => e.currentTarget.style.background = T.borderLight}
            onMouseLeave={e => e.currentTarget.style.background = "none"}
          >
            ← 返回
          </button>
          <span style={{ fontWeight: 600, fontSize: 15, color: T.text }}>帖子详情</span>
        </div>

        <div style={s.postCard}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: `hsl(${(post.id * 67) % 360}, 35%, 88%)`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 14, fontWeight: 700, color: `hsl(${(post.id * 67) % 360}, 40%, 40%)`,
              }}>{post.anon_name?.[2]}</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{post.anon_name}</div>
                <div style={{ fontSize: 12, color: T.textTertiary }}>{timeAgo(post.created_at)}</div>
              </div>
            </div>
            <TagChip tag={post.tag} />
          </div>
          <div style={{ fontSize: 16, lineHeight: 1.9, color: T.text, fontFamily: T.font }}>
            {post.content}
          </div>
        </div>

        <div style={s.sectionTitle}>
          💬 全部回复 ({comments.length})
        </div>

        {loading ? (
          <div style={s.empty}>加载中...</div>
        ) : comments.length === 0 ? (
          <div style={s.empty}>还没有回复，来说两句吧 ✍️</div>
        ) : (
          comments.map((c, i) => (
            <div key={c.id} style={{ ...s.commentItem, animationDelay: `${i * 50}ms` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <div style={{
                  width: 24, height: 24, borderRadius: 6,
                  background: `hsl(${(c.id * 123) % 360}, 35%, 88%)`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 11, fontWeight: 700, color: `hsl(${(c.id * 123) % 360}, 40%, 40%)`,
                }}>{c.anon_name?.[2]}</div>
                <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{c.anon_name}</span>
                <span style={{ fontSize: 12, color: T.textTertiary, marginLeft: "auto" }}>{timeAgo(c.created_at)}</span>
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.7, color: T.text, paddingLeft: 32, fontFamily: T.font }}>
                {c.content}
              </div>
            </div>
          ))
        )}
        <div style={{ height: 80 }} />
      </div>

      <div style={s.commentBar}>
        <input
          ref={inputRef}
          style={s.commentInput}
          placeholder="写下你的回复..."
          value={newComment}
          onChange={e => setNewComment(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleSubmit()}
          maxLength={500}
        />
        <button
          style={{ ...s.sendBtn, opacity: newComment.trim() ? 1 : 0.5 }}
          onClick={handleSubmit}
          disabled={!newComment.trim() || submitting}
        >
          {submitting ? "..." : "发送"}
        </button>
      </div>
    </div>
  );
}

// ============================================================
// New Post Modal
// ============================================================
function NewPostModal({ token, onClose, onCreated }) {
  const [content, setContent] = useState("");
  const [tag, setTag] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!content.trim() || !tag || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const post = await api("/api/posts/", {
        method: "POST", token, body: { content: content.trim(), tag },
      });
      onCreated(post);
      onClose();
    } catch (e) {
      setError(e.message);
    }
    setSubmitting(false);
  };

  const s = {
    overlay: {
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
      backdropFilter: "blur(4px)", zIndex: 200,
      display: "flex", alignItems: "flex-end", justifyContent: "center",
      animation: "fadeIn 0.2s ease-out",
    },
    modal: {
      background: T.surface, borderRadius: "20px 20px 0 0", padding: 28,
      width: "100%", maxWidth: 640, maxHeight: "85vh", overflowY: "auto",
      border: `1px solid ${T.border}`, borderBottom: "none",
      animation: "slideUp 0.3s ease-out",
    },
    title: {
      display: "flex", alignItems: "center", justifyContent: "space-between",
      marginBottom: 20, fontSize: 17, fontWeight: 700, color: T.text,
    },
    closeBtn: {
      background: "none", border: "none", fontSize: 20, color: T.textTertiary,
      cursor: "pointer", padding: "4px 8px", borderRadius: 6,
    },
    tagsWrap: { display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 18 },
    tagSelect: (active) => ({
      padding: "7px 14px", borderRadius: 20, fontSize: 13, fontWeight: 500,
      cursor: "pointer", whiteSpace: "nowrap", transition: "all 0.2s",
      border: `1px solid ${active ? T.accent : T.border}`,
      background: active ? T.accentSoft : "transparent",
      color: active ? T.accent : T.textSecondary,
    }),
    textarea: {
      width: "100%", minHeight: 140, padding: 16, borderRadius: T.radius,
      border: `1px solid ${T.border}`, background: T.bg, color: T.text,
      fontSize: 15, lineHeight: 1.7, resize: "vertical", fontFamily: T.font,
      transition: "all 0.2s",
    },
    counter: { textAlign: "right", fontSize: 12, color: T.textTertiary, marginTop: 4 },
    btn: (disabled) => ({
      width: "100%", padding: "13px 0", borderRadius: T.radius, border: "none",
      background: disabled ? T.border : T.accent, color: disabled ? T.textTertiary : "#fff",
      fontSize: 15, fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
      fontFamily: T.fontSans, marginTop: 18, transition: "all 0.2s",
    }),
    error: {
      padding: "10px 14px", borderRadius: 8, background: "#fef2f2",
      border: "1px solid #fecaca", color: T.danger, fontSize: 13, marginTop: 12,
    },
    note: { textAlign: "center", fontSize: 12, color: T.textTertiary, marginTop: 14 },
  };

  return (
    <div style={s.overlay} onClick={onClose}>
      <div style={s.modal} onClick={e => e.stopPropagation()}>
        <div style={s.title}>
          <span>✏️ 发表新树洞</span>
          <button style={s.closeBtn} onClick={onClose}>✕</button>
        </div>
        <div style={{ fontSize: 13, color: T.textSecondary, marginBottom: 8 }}>选择标签</div>
        <div style={s.tagsWrap}>
          {TAGS.map(t => (
            <span key={t} style={s.tagSelect(tag === t)} onClick={() => setTag(tag === t ? "" : t)}>
              {t}
            </span>
          ))}
        </div>
        <textarea
          style={s.textarea}
          placeholder="说点什么吧……你的发言完全匿名 🌳"
          value={content}
          onChange={e => setContent(e.target.value)}
          maxLength={2000}
          autoFocus
        />
        <div style={s.counter}>
          <span style={{ color: content.length > 1800 ? T.danger : T.textTertiary }}>
            {content.length}
          </span> / 2000
        </div>
        {error && <div style={s.error}>{error}</div>}
        <button
          style={s.btn(!content.trim() || !tag || submitting)}
          onClick={handleSubmit}
          disabled={!content.trim() || !tag || submitting}
        >
          {submitting ? "发布中..." : "匿名发布"}
        </button>
        <div style={s.note}>请遵守社区规范，文明发言</div>
      </div>
    </div>
  );
}

// ============================================================
// Main Feed Page
// ============================================================
function FeedPage({ token, onLogout }) {
  const [posts, setPosts] = useState([]);
  const [activeTag, setActiveTag] = useState("全部");
  const [order, setOrder] = useState("new");
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [selectedPost, setSelectedPost] = useState(null);
  const [error, setError] = useState("");

  const loadPosts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const tag = activeTag === "全部" ? "" : activeTag;
      const params = new URLSearchParams({ order, page: "1", size: "50" });
      if (tag) params.set("tag", tag);
      const data = await api(`/api/posts/?${params}`, { token });
      setPosts(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [token, activeTag, order]);

  useEffect(() => { loadPosts(); }, [loadPosts]);

  if (selectedPost) {
    return <PostDetail post={selectedPost} token={token} onBack={() => { setSelectedPost(null); loadPosts(); }} />;
  }

  const s = {
    page: { minHeight: "100vh", background: T.bg, fontFamily: T.font },
    container: { maxWidth: 640, margin: "0 auto", padding: "0 16px" },
    header: {
      padding: "20px 0 14px", borderBottom: `1px solid ${T.border}`,
      marginBottom: 16, position: "sticky", top: 0, zIndex: 100, background: T.bg,
    },
    headerRow: { display: "flex", alignItems: "center", justifyContent: "space-between" },
    logo: { display: "flex", alignItems: "center", gap: 10 },
    logoMark: {
      width: 34, height: 34, borderRadius: 10,
      background: `linear-gradient(145deg, ${T.accent}, #d4622c)`,
      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17,
    },
    logoText: { fontSize: 19, fontWeight: 700, color: T.text, letterSpacing: 0.5 },
    betaBadge: {
      fontSize: 10, background: T.accent, color: "#fff",
      padding: "2px 7px", borderRadius: 5, fontWeight: 700, marginLeft: 4,
      fontFamily: T.fontSans,
    },
    logoutBtn: {
      background: "none", border: `1px solid ${T.border}`, borderRadius: 8,
      padding: "6px 14px", fontSize: 12, color: T.textSecondary, cursor: "pointer",
      fontFamily: T.fontSans, transition: "all 0.2s",
    },
    tabBar: {
      display: "flex", gap: 6, alignItems: "center", marginTop: 12,
    },
    orderBtn: (active) => ({
      padding: "6px 12px", borderRadius: 8, fontSize: 13, fontWeight: 500,
      cursor: "pointer", border: "none", fontFamily: T.fontSans, transition: "all 0.2s",
      background: active ? T.text : "transparent", color: active ? T.surface : T.textTertiary,
    }),
    tagBar: {
      display: "flex", gap: 6, overflowX: "auto", padding: "12px 0",
      scrollbarWidth: "none", WebkitOverflowScrolling: "touch",
    },
    tagPill: (active) => ({
      padding: "6px 14px", borderRadius: 20, fontSize: 13, fontWeight: 500,
      cursor: "pointer", whiteSpace: "nowrap", transition: "all 0.2s",
      border: `1px solid ${active ? T.accent : T.border}`,
      background: active ? T.accentSoft : T.surface,
      color: active ? T.accent : T.textSecondary,
      flexShrink: 0,
    }),
    postList: { display: "flex", flexDirection: "column", gap: 10 },
    fab: {
      position: "fixed", bottom: 24, right: 24, width: 52, height: 52,
      borderRadius: 14, border: "none", cursor: "pointer",
      background: `linear-gradient(145deg, ${T.accent}, #d4622c)`, color: "#fff",
      fontSize: 24, display: "flex", alignItems: "center", justifyContent: "center",
      boxShadow: "0 4px 20px rgba(180,74,28,0.35)", zIndex: 50, transition: "transform 0.2s",
    },
    empty: {
      textAlign: "center", padding: 60, color: T.textTertiary,
    },
    errBox: {
      padding: 16, borderRadius: T.radius, background: "#fef2f2",
      border: "1px solid #fecaca", color: T.danger, fontSize: 14, textAlign: "center",
    },
  };

  return (
    <div style={s.page}>
      <div style={s.container}>
        {/* Header */}
        <div style={s.header}>
          <div style={s.headerRow}>
            <div style={s.logo}>
              <div style={s.logoMark}>🕳️</div>
              <span style={s.logoText}>山大树洞</span>
              <span style={s.betaBadge}>BETA</span>
            </div>
            <button
              style={s.logoutBtn}
              onClick={onLogout}
              onMouseEnter={e => e.currentTarget.style.borderColor = T.accent}
              onMouseLeave={e => e.currentTarget.style.borderColor = T.border}
            >
              退出登录
            </button>
          </div>
          <div style={s.tabBar}>
            <button style={s.orderBtn(order === "new")} onClick={() => setOrder("new")}>🕐 最新</button>
            <button style={s.orderBtn(order === "hot")} onClick={() => setOrder("hot")}>🔥 最热</button>
          </div>
        </div>

        {/* Tags */}
        <div style={s.tagBar}>
          {["全部", ...TAGS].map(t => (
            <span key={t} style={s.tagPill(activeTag === t)} onClick={() => setActiveTag(t)}>
              {t}
            </span>
          ))}
        </div>

        {/* Content */}
        {error ? (
          <div style={s.errBox}>
            {error}
            <div style={{ marginTop: 10 }}>
              <button onClick={loadPosts} style={{ ...s.logoutBtn, borderColor: T.danger, color: T.danger }}>
                重试
              </button>
            </div>
          </div>
        ) : loading ? (
          <div style={s.empty}>
            <div style={{ fontSize: 28, marginBottom: 10 }}>🌳</div>
            加载中...
          </div>
        ) : posts.length === 0 ? (
          <div style={s.empty}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>🌲</div>
            <div style={{ fontSize: 16, marginBottom: 6 }}>这里还很安静</div>
            <div>来发第一条树洞吧</div>
          </div>
        ) : (
          <div style={s.postList}>
            {posts.map((p, i) => (
              <PostCard
                key={p.id}
                post={p}
                token={token}
                delay={i}
                onClick={() => setSelectedPost(p)}
              />
            ))}
          </div>
        )}

        <div style={{ height: 80 }} />
      </div>

      {/* FAB */}
      <button
        style={s.fab}
        onClick={() => setShowNew(true)}
        onMouseEnter={e => e.currentTarget.style.transform = "scale(1.08)"}
        onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}
      >
        ✏️
      </button>

      {/* New Post Modal */}
      {showNew && (
        <NewPostModal
          token={token}
          onClose={() => setShowNew(false)}
          onCreated={(post) => { setPosts(prev => [post, ...prev]); }}
        />
      )}
    </div>
  );
}

// ============================================================
// Root App
// ============================================================
export default function App() {
  const [token, setToken] = useState(() => {
    try { return window.sessionStorage?.getItem?.("sdu_token") || ""; } catch { return ""; }
  });

  const handleLogin = (t) => {
    setToken(t);
    try { window.sessionStorage?.setItem?.("sdu_token", t); } catch {}
  };

  const handleLogout = () => {
    setToken("");
    try { window.sessionStorage?.removeItem?.("sdu_token"); } catch {}
  };

  return (
    <>
      <style>{globalCSS}</style>
      {token ? (
        <FeedPage token={token} onLogout={handleLogout} />
      ) : (
        <LoginPage onLogin={handleLogin} />
      )}
    </>
  );
}
