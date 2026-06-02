import { useState, useRef, useEffect } from "react";
import { Send, Trash2, MessageSquare, BarChart2, Zap, Mic, Shield, Menu, X, AlertTriangle, CheckCircle } from "lucide-react";
import { useChat } from "./hooks/useChat";
import { ChatMessage } from "./components/ChatMessage";
import { Sidebar } from "./components/Sidebar";
import { ToolCallBanner } from "./components/ToolCallBanner";
import { EvalDashboard } from "./components/EvalDashboard";
import { WorkflowDemo } from "./components/WorkflowDemo";
import { MediaInput } from "./components/MediaInput";
import { checkBackendHealth } from "./utils/health";

const TABS = [
  { id: "chat",      label: "Chat",      Icon: MessageSquare },
  { id: "workflows", label: "Workflows", Icon: Zap },
  { id: "eval",      label: "Eval",      Icon: BarChart2 },
  { id: "voice",     label: "Media",     Icon: Mic },
];

export default function App() {
  const [provider, setProvider]           = useState("groq");
  const [tab, setTab]                     = useState("chat");
  const [input, setInput]                 = useState("");
  const [sidebarOpen, setSidebarOpen]     = useState(false);
  const [backendStatus, setBackendStatus] = useState(null);
  const [backendMsg, setBackendMsg]       = useState("");
  const bottomRef   = useRef(null);
  const textareaRef = useRef(null);
  const { messages, send, loading, tools, language, clear } = useChat(provider);

  useEffect(() => {
    checkBackendHealth().then(({ ok, reason }) => {
      setBackendStatus(ok ? "ok" : "error");
      if (!ok) setBackendMsg(reason);
    });
  }, []);

  useEffect(() => {
    if (tab === "chat") bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, tab]);

  const handleSend = (text) => {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setTab("chat");
    setSidebarOpen(false);
    send(msg);
  };

  const tabContent = {
    chat: null, // rendered inline below
    workflows: <WorkflowDemo provider={provider} />,
    eval:      <EvalDashboard provider={provider} />,
    voice:     <MediaInput provider={provider} onTranscript={(t) => { setInput(t); setTab("chat"); }} />,
  };

  return (
    <div style={{ display: "flex", height: "100dvh", overflow: "hidden", position: "relative" }}>

      {/* ── DESKTOP SIDEBAR ─────────────────────────────────── */}
      <div className="sidebar">
        <Sidebar provider={provider} setProvider={setProvider} language={language} onPrompt={handleSend} />
      </div>

      {/* ── MOBILE SIDEBAR OVERLAY ──────────────────────────── */}
      {sidebarOpen && (
        <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex" }}>
          <div style={{ flex: 1, background: "rgba(0,0,0,0.6)" }} onClick={() => setSidebarOpen(false)} />
          <div style={{ width: 260, background: "var(--ink-2)", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "flex-end", padding: "12px 12px 0" }}>
              <button onClick={() => setSidebarOpen(false)} style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer" }}>
                <X size={18} />
              </button>
            </div>
            <Sidebar provider={provider} setProvider={setProvider} language={language} onPrompt={handleSend} mobile />
          </div>
        </div>
      )}

      {/* ── MAIN AREA ────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

        {/* Scan line decoration */}
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden", zIndex: 0 }}>
          <div className="scan-line" />
        </div>

        {/* ── DESKTOP HEADER ──────────────────────────────────── */}
        <header className="desktop-tabs" style={{ padding: "10px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--ink)", zIndex: 2, gap: 16, flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 2 }}>
            {TABS.map(({ id, label, Icon }) => (
              <button key={id} onClick={() => setTab(id)} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 11, fontWeight: 500, background: tab === id ? "var(--jade-dim)" : "transparent", color: tab === id ? "var(--jade)" : "var(--muted)", transition: "all 0.15s" }}>
                <Icon size={11} /> {label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {backendStatus === "ok" && <span style={{ fontSize: 10, color: "var(--jade)", display: "flex", alignItems: "center", gap: 3 }}><CheckCircle size={10} /> Backend online</span>}
            {backendStatus === "error" && <span title={backendMsg} style={{ fontSize: 10, color: "var(--ember)", display: "flex", alignItems: "center", gap: 3, cursor: "help" }}><AlertTriangle size={10} /> Offline</span>}
            <span style={{ fontSize: 10, color: "var(--jade)", display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 6, height: 6, background: "var(--jade)", borderRadius: "50%", animation: "pulse-jade 2s infinite", display: "inline-block" }} />
              {provider.toUpperCase()}
            </span>
            <button onClick={clear} style={{ background: "transparent", border: "1px solid var(--border)", borderRadius: 6, padding: "5px 8px", cursor: "pointer", color: "var(--muted)", display: "flex", alignItems: "center", gap: 4, fontSize: 11 }}>
              <Trash2 size={11} /> Clear
            </button>
          </div>
        </header>

        {/* ── MOBILE HEADER ───────────────────────────────────── */}
        <header className="mobile-header" style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", alignItems: "center", justifyContent: "space-between", background: "var(--ink)", zIndex: 2, flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button onClick={() => setSidebarOpen(true)} style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", padding: 4 }}>
              <Menu size={18} />
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 26, height: 26, borderRadius: 6, background: "var(--jade-dim)", border: "1px solid #00E67650", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Shield size={12} color="var(--jade)" />
              </div>
              <span style={{ fontFamily: "Syne, sans-serif", fontWeight: 700, fontSize: 14, color: "var(--white)" }}>NaijaFinAI</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {backendStatus === "ok"    && <CheckCircle size={12} color="var(--jade)" />}
            {backendStatus === "error" && <AlertTriangle size={12} color="var(--ember)" />}
            <button onClick={clear} style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", padding: 4 }}>
              <Trash2 size={15} />
            </button>
          </div>
        </header>

        <ToolCallBanner tools={tools} />

        {/* ── CONTENT ─────────────────────────────────────────── */}
        <div className="grid-bg" style={{ flex: 1, overflow: "hidden", position: "relative", zIndex: 1 }}>

          {/* Chat */}
          <div style={{ display: tab === "chat" ? "flex" : "none", flexDirection: "column", height: "100%" }}>
            <div style={{ flex: 1, overflowY: "auto", padding: "16px 16px 8px" }}>
              {messages.map((msg, i) => <ChatMessage key={i} message={msg} />)}
              <div ref={bottomRef} />
            </div>

            {/* Input bar */}
            <div style={{ borderTop: "1px solid var(--border)", padding: "10px 14px", background: "var(--ink)", flexShrink: 0 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                <textarea ref={textareaRef} value={input}
                  onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px"; }}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  placeholder="Ask in English, Pidgin, Yoruba, Hausa, or Igbo…"
                  disabled={loading} rows={1}
                  style={{ flex: 1, background: "var(--ink-2)", border: "1px solid var(--border-bright)", borderRadius: 12, padding: "10px 13px", fontSize: 14, color: "var(--text)", resize: "none", outline: "none", fontFamily: "DM Sans, sans-serif", lineHeight: 1.5, minHeight: 42, maxHeight: 120 }}
                  onFocus={e => e.target.style.borderColor = "#00E67660"}
                  onBlur={e => e.target.style.borderColor = "var(--border-bright)"} />
                <button onClick={() => handleSend()} disabled={loading || !input.trim()} className="btn-primary"
                  style={{ width: 42, height: 42, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Send size={15} />
                </button>
              </div>
              <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 6, textAlign: "center" }}>
                CBN · NFIU · NDPA 2023 · 7-Layer Fraud Intelligence · Groq Free
              </div>
            </div>
          </div>

          {/* Other tabs */}
          {tab !== "chat" && (
            <div style={{ height: "100%", overflowY: "auto" }}>
              {tabContent[tab]}
            </div>
          )}
        </div>

        {/* ── MOBILE BOTTOM NAV ────────────────────────────────── */}
        <nav className="mobile-bottom-bar" style={{ borderTop: "1px solid var(--border)", background: "var(--ink)", display: "flex", flexShrink: 0, zIndex: 2 }}>
          {TABS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 3, padding: "8px 0", border: "none", cursor: "pointer", background: "transparent", color: tab === id ? "var(--jade)" : "var(--muted)", fontSize: 9, fontWeight: tab === id ? 600 : 400, borderTop: tab === id ? "2px solid var(--jade)" : "2px solid transparent", transition: "all 0.15s" }}>
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

      </div>
    </div>
  );
}
