import { useState, useRef, useEffect } from "react";
import { Send, Trash2, MessageSquare, BarChart2, Zap, Mic, AlertTriangle, CheckCircle, Activity, FlaskConical } from "lucide-react";
import { useChat } from "./hooks/useChat";
import { ChatMessage } from "./components/ChatMessage";
import { Sidebar } from "./components/Sidebar";
import { ToolCallBanner } from "./components/ToolCallBanner";
import { EvalDashboard } from "./components/EvalDashboard";
import { WorkflowDemo } from "./components/WorkflowDemo";
import { MediaInput } from "./components/MediaInput";
import { MonitoringDashboard } from "./components/MonitoringDashboard";
import { SimulationPanel } from "./components/SimulationPanel";
import { checkBackendHealth } from "./utils/health";
import { getGreeting, getGreetingEmoji } from "./utils/greeting";

const TABS = [
  { id: "chat",       label: "Chat",          Icon: MessageSquare },
  { id: "workflows",  label: "Workflows",     Icon: Zap           },
  { id: "simulate",   label: "Simulate",      Icon: FlaskConical  },
  { id: "eval",       label: "Eval",          Icon: BarChart2     },
  { id: "voice",      label: "Voice & Files", Icon: Mic           },
  { id: "monitor",    label: "Monitor",       Icon: Activity      },
];

export default function App() {
  const [provider, setProvider]           = useState("groq");
  const [tab, setTab]                     = useState("chat");
  const [input, setInput]                 = useState("");
  const [backendStatus, setBackendStatus] = useState(null);
  const [backendMsg, setBackendMsg]       = useState("");
  const bottomRef   = useRef(null);
  const textareaRef = useRef(null);
  const { messages, send, loading, tools, language, clear } = useChat(provider);

  const greeting = getGreeting({ language, nigerianMode: language !== "english" });

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
    send(msg);
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar provider={provider} setProvider={setProvider} language={language} onPrompt={handleSend} />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
          <div className="scan-line" />
        </div>

        {/* Header */}
        <header style={{ padding: "8px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--ink)", zIndex: 2, gap: 12, flexWrap: "wrap" }}>
          {/* Tabs */}
          <div style={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
            {TABS.map(({ id, label, Icon }) => (
              <button key={id} onClick={() => setTab(id)}
                style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 11, fontWeight: 500, background: tab === id ? "var(--jade-dim)" : "transparent", color: tab === id ? "var(--jade)" : "var(--muted)", transition: "all 0.15s", whiteSpace: "nowrap" }}>
                <Icon size={11} /> {label}
              </button>
            ))}
          </div>

          {/* Status row */}
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
            {/* Greeting */}
            <div style={{ fontSize: 10, color: "var(--muted)", borderRight: "1px solid var(--border)", paddingRight: 8 }}>
              {getGreetingEmoji()} {greeting.primary}
              {greeting.secondary && <span style={{ color: "var(--jade)", marginLeft: 4 }}>{greeting.secondary}</span>}
            </div>

            {/* Backend status */}
            {backendStatus === "ok" && (
              <div style={{ fontSize: 10, color: "var(--jade)", display: "flex", alignItems: "center", gap: 3 }}>
                <CheckCircle size={10} /> online
              </div>
            )}
            {backendStatus === "error" && (
              <div title={backendMsg} style={{ fontSize: 10, color: "var(--ember)", display: "flex", alignItems: "center", gap: 3, cursor: "help", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                <AlertTriangle size={10} /> {backendMsg.slice(0, 35)}…
              </div>
            )}

            {/* Provider badge */}
            <div style={{ fontSize: 10, color: "var(--jade)", display: "flex", alignItems: "center", gap: 3 }}>
              <span style={{ width: 6, height: 6, background: "var(--jade)", borderRadius: "50%", animation: "pulse-jade 2s infinite", display: "inline-block" }} />
              {provider.toUpperCase()}
            </div>

            <button onClick={clear} style={{ background: "transparent", border: "1px solid var(--border)", borderRadius: 6, padding: "4px 8px", cursor: "pointer", color: "var(--muted)", display: "flex", alignItems: "center", gap: 3, fontSize: 11 }}>
              <Trash2 size={11} /> Clear
            </button>
          </div>
        </header>

        <ToolCallBanner tools={tools} />

        {/* Tab panels */}
        <div className="grid-bg" style={{ flex: 1, overflow: "hidden", position: "relative" }}>

          {/* Chat */}
          <div style={{ display: tab === "chat" ? "flex" : "none", flexDirection: "column", height: "100%" }}>
            <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
              {messages.map((msg, i) => <ChatMessage key={i} message={msg} />)}
              <div ref={bottomRef} />
            </div>
            <div style={{ borderTop: "1px solid var(--border)", padding: "12px 20px", background: "var(--ink)" }}>
              <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
                <textarea ref={textareaRef} value={input}
                  onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 130) + "px"; }}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  placeholder="Ask in English, Pidgin, Yoruba, Hausa, or Igbo…"
                  disabled={loading} rows={1}
                  style={{ flex: 1, background: "var(--ink-2)", border: "1px solid var(--border-bright)", borderRadius: 12, padding: "10px 14px", fontSize: 13, color: "var(--text)", resize: "none", outline: "none", fontFamily: "DM Sans", lineHeight: 1.5, minHeight: 42, maxHeight: 130 }}
                  onFocus={e => e.target.style.borderColor = "#00E67660"}
                  onBlur={e => e.target.style.borderColor = "var(--border-bright)"} />
                <button onClick={() => handleSend()} disabled={loading || !input.trim()} className="btn-primary"
                  style={{ width: 42, height: 42, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Send size={15} />
                </button>
              </div>
              <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 6, textAlign: "center" }}>
                CBN · NFIU · NDPA 2023 §40 · Bayesian Fraud Engine · Groq Free + Fallback
              </div>
            </div>
          </div>

          {tab === "workflows" && <div style={{ height: "100%", overflowY: "auto" }}><WorkflowDemo provider={provider} /></div>}
          {tab === "simulate"  && <div style={{ height: "100%", overflowY: "auto" }}><SimulationPanel /></div>}
          {tab === "eval"      && <div style={{ height: "100%", overflowY: "auto" }}><EvalDashboard provider={provider} /></div>}
          {tab === "voice"     && <div style={{ height: "100%", overflowY: "auto" }}><MediaInput provider={provider} onTranscript={(t) => { setInput(t); setTab("chat"); }} /></div>}
          {tab === "monitor"   && <div style={{ height: "100%", overflowY: "auto" }}><MonitoringDashboard /></div>}
        </div>
      </div>
    </div>
  );
}
