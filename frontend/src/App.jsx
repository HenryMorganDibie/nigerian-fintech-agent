import { useState, useRef, useEffect } from "react";
import { Trash2, MessageSquare, BarChart2, Zap, Shield, Menu, X, AlertTriangle, CheckCircle } from "lucide-react";
import { useChat } from "./hooks/useChat";
import { ChatMessage } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import { Sidebar } from "./components/Sidebar";
import { ToolCallBanner } from "./components/ToolCallBanner";
import { EvalDashboard } from "./components/EvalDashboard";
import { WorkflowDemo } from "./components/WorkflowDemo";
import { checkBackendHealth } from "./utils/health";

const TABS = [
  { id: "chat",      label: "Chat",      Icon: MessageSquare },
  { id: "workflows", label: "Workflows", Icon: Zap },
  { id: "eval",      label: "Eval",      Icon: BarChart2 },
];

export default function App() {
  const [provider, setProvider]           = useState("groq");
  const [tab, setTab]                     = useState("chat");
  const [sidebarOpen, setSidebarOpen]     = useState(false);
  const [backendStatus, setBackendStatus] = useState(null);
  const [backendMsg, setBackendMsg]       = useState("");
  const bottomRef = useRef(null);
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

  const handleSend = (msg) => {
    if (!msg) return;
    setTab("chat");
    setSidebarOpen(false);
    send(msg);
  };

  return (
    <div style={{ display: "flex", height: "100dvh", overflow: "hidden" }}>

      {/* ── DESKTOP SIDEBAR ─────────────────────────────────── */}
      <div className="sidebar">
        <Sidebar provider={provider} setProvider={setProvider} language={language} onPrompt={handleSend} />
      </div>

      {/* ── MOBILE SIDEBAR OVERLAY ──────────────────────────── */}
      {sidebarOpen && (
        <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex" }}>
          <div style={{ flex: 1, background: "rgba(0,0,0,0.65)" }} onClick={() => setSidebarOpen(false)} />
          <div style={{ width: 260, background: "var(--ink-2)", overflowY: "auto", borderLeft: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "flex-end", padding: "12px 12px 0" }}>
              <button onClick={() => setSidebarOpen(false)} style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer" }}>
                <X size={18} />
              </button>
            </div>
            <Sidebar provider={provider} setProvider={setProvider} language={language} onPrompt={handleSend} />
          </div>
        </div>
      )}

      {/* ── MAIN AREA ────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0, position: "relative" }}>

        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden", zIndex: 0 }}>
          <div className="scan-line" />
        </div>

        {/* ── DESKTOP HEADER ──────────────────────────────── */}
        <header className="desktop-tabs" style={{ padding: "10px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--ink)", zIndex: 2, flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 2 }}>
            {TABS.map(({ id, label, Icon }) => (
              <button key={id} onClick={() => setTab(id)} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 11, fontWeight: 500, background: tab === id ? "var(--jade-dim)" : "transparent", color: tab === id ? "var(--jade)" : "var(--muted)", transition: "all 0.15s" }}>
                <Icon size={11} /> {label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {backendStatus === "ok"    && <span style={{ fontSize: 10, color: "var(--jade)", display: "flex", alignItems: "center", gap: 3 }}><CheckCircle size={10} /> Online</span>}
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

        {/* ── MOBILE HEADER ───────────────────────────────── */}
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
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {backendStatus === "ok"    && <CheckCircle size={12} color="var(--jade)" />}
            {backendStatus === "error" && <AlertTriangle size={12} color="var(--ember)" />}
            <button onClick={clear} style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", padding: 4 }}>
              <Trash2 size={15} />
            </button>
          </div>
        </header>

        <ToolCallBanner tools={tools} />

        {/* ── CONTENT ─────────────────────────────────────────── */}
        <div className="grid-bg" style={{ flex: 1, overflow: "hidden", position: "relative", zIndex: 1, display: "flex", flexDirection: "column" }}>

          {/* Chat tab — always rendered so messages persist */}
          <div style={{ display: tab === "chat" ? "flex" : "none", flexDirection: "column", flex: 1, overflow: "hidden" }}>
            <div style={{ flex: 1, overflowY: "auto", padding: "16px 16px 8px" }}>
              {messages.map((msg, i) => <ChatMessage key={i} message={msg} />)}
              <div ref={bottomRef} />
            </div>
            {/* Chat input with voice + file built in */}
            <ChatInput onSend={handleSend} loading={loading} provider={provider} />
          </div>

          {/* Other tabs */}
          {tab === "workflows" && <div style={{ flex: 1, overflowY: "auto" }}><WorkflowDemo provider={provider} /></div>}
          {tab === "eval"      && <div style={{ flex: 1, overflowY: "auto" }}><EvalDashboard provider={provider} /></div>}
        </div>

        {/* ── MOBILE BOTTOM NAV (3 tabs now, no media tab) ─── */}
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
