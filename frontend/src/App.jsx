import { useState, useRef, useEffect } from "react";
import { Trash2, MessageSquare, ListChecks, GaugeCircle, Menu, X, AlertTriangle, CircleCheck } from "lucide-react";
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
  { id: "workflows", label: "Workflows", Icon: ListChecks },
  { id: "eval",      label: "Evaluation",Icon: GaugeCircle },
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
          <div style={{ flex: 1, background: "rgba(27,42,74,0.45)" }} onClick={() => setSidebarOpen(false)} />
          <div style={{ width: 270, background: "var(--paper-2)", overflowY: "auto", borderLeft: "1px solid var(--rule-bold)" }}>
            <div style={{ display: "flex", justifyContent: "flex-end", padding: "12px 12px 0" }}>
              <button onClick={() => setSidebarOpen(false)} style={{ background: "transparent", border: "none", color: "var(--ink-faint)", cursor: "pointer" }}>
                <X size={18} />
              </button>
            </div>
            <Sidebar provider={provider} setProvider={setProvider} language={language} onPrompt={handleSend} />
          </div>
        </div>
      )}

      {/* ── MAIN AREA ────────────────────────────────────────── */}
      <div className="no-rule" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0, position: "relative", background: "var(--paper)" }}>

        {/* ── DESKTOP HEADER ──────────────────────────────── */}
        <header className="desktop-tabs" style={{ padding: "0 18px", borderBottom: "1px solid var(--rule-bold)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--card)", flexShrink: 0, height: 50 }}>
          <div style={{ display: "flex", height: "100%" }}>
            {TABS.map(({ id, label, Icon }) => (
              <button key={id} onClick={() => setTab(id)} style={{
                display: "flex", alignItems: "center", gap: 7, padding: "0 14px", height: "100%",
                border: "none", borderBottom: tab === id ? "2px solid var(--ink)" : "2px solid transparent",
                cursor: "pointer", fontSize: 13, fontFamily: "Inter", fontWeight: tab === id ? 600 : 500,
                background: "transparent", color: tab === id ? "var(--ink)" : "var(--ink-faint)",
                transition: "color 0.15s, border-color 0.15s",
              }}>
                <Icon size={14} strokeWidth={2} /> {label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            {backendStatus === "ok" && (
              <span style={{ fontSize: 11, color: "var(--stamp-green)", display: "flex", alignItems: "center", gap: 4, fontFamily: "Roboto Mono" }}>
                <CircleCheck size={12} strokeWidth={2} /> connected
              </span>
            )}
            {backendStatus === "error" && (
              <span title={backendMsg} style={{ fontSize: 11, color: "var(--stamp-rust)", display: "flex", alignItems: "center", gap: 4, cursor: "help", fontFamily: "Roboto Mono" }}>
                <AlertTriangle size={12} strokeWidth={2} /> offline
              </span>
            )}
            <span className="font-mono" style={{ fontSize: 11, color: "var(--ink-faint)", letterSpacing: "0.03em" }}>
              {provider.toUpperCase()}
            </span>
            <button onClick={clear} className="btn-ghost" style={{ borderRadius: 4, padding: "5px 10px", display: "flex", alignItems: "center", gap: 5, fontSize: 11.5 }}>
              <Trash2 size={12} /> Clear
            </button>
          </div>
        </header>

        {/* ── MOBILE HEADER ───────────────────────────────── */}
        <header className="mobile-header" style={{ padding: "10px 14px", borderBottom: "1px solid var(--rule-bold)", alignItems: "center", justifyContent: "space-between", background: "var(--card)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <button onClick={() => setSidebarOpen(true)} style={{ background: "transparent", border: "none", color: "var(--ink-faint)", cursor: "pointer", padding: 4 }}>
              <Menu size={18} />
            </button>
            <span className="font-display" style={{ fontSize: 16, color: "var(--ink)" }}>NaijaFinAI</span>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            {backendStatus === "ok"    && <CircleCheck size={14} color="var(--stamp-green)" />}
            {backendStatus === "error" && <AlertTriangle size={14} color="var(--stamp-rust)" />}
            <button onClick={clear} style={{ background: "transparent", border: "none", color: "var(--ink-faint)", cursor: "pointer", padding: 4 }}>
              <Trash2 size={15} />
            </button>
          </div>
        </header>

        <ToolCallBanner tools={tools} />

        {/* ── CONTENT ─────────────────────────────────────────── */}
        <div style={{ flex: 1, overflow: "hidden", position: "relative", display: "flex", flexDirection: "column" }}>

          <div style={{ display: tab === "chat" ? "flex" : "none", flexDirection: "column", flex: 1, overflow: "hidden" }}>
            <div style={{ flex: 1, overflowY: "auto", padding: "16px 16px 8px" }}>
              {messages.map((msg, i) => <ChatMessage key={i} message={msg} />)}
              <div ref={bottomRef} />
            </div>
            <ChatInput onSend={handleSend} loading={loading} provider={provider} />
          </div>

          {tab === "workflows" && <div style={{ flex: 1, overflowY: "auto" }}><WorkflowDemo provider={provider} /></div>}
          {tab === "eval"      && <div style={{ flex: 1, overflowY: "auto" }}><EvalDashboard provider={provider} /></div>}
        </div>

        {/* ── MOBILE BOTTOM NAV ─────────────────────────────── */}
        <nav className="mobile-bottom-bar" style={{ borderTop: "1px solid var(--rule-bold)", background: "var(--card)", display: "flex", flexShrink: 0 }}>
          {TABS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 3, padding: "8px 0", border: "none", cursor: "pointer", background: "transparent", color: tab === id ? "var(--ink)" : "var(--ink-faint)", fontSize: 9.5, fontFamily: "Inter", fontWeight: tab === id ? 600 : 400, borderTop: tab === id ? "2px solid var(--ink)" : "2px solid transparent" }}>
              <Icon size={16} strokeWidth={2} />
              {label}
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
