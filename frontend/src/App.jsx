import { useState, useRef, useEffect } from "react";
import { Send, Trash2, MessageSquare, BarChart2, Zap, Mic } from "lucide-react";
import { useChat } from "./hooks/useChat";
import { ChatMessage } from "./components/ChatMessage";
import { Sidebar } from "./components/Sidebar";
import { ToolCallBanner } from "./components/ToolCallBanner";
import { EvalDashboard } from "./components/EvalDashboard";
import { WorkflowDemo } from "./components/WorkflowDemo";
import { MediaInput } from "./components/MediaInput";

const TABS = [
  { id: "chat",      label: "Chat",      Icon: MessageSquare },
  { id: "workflows", label: "Workflows", Icon: Zap },
  { id: "eval",      label: "Eval",      Icon: BarChart2 },
  { id: "voice",     label: "Voice & Files", Icon: Mic },
];

export default function App() {
  const [provider, setProvider] = useState("groq");
  const [tab, setTab] = useState("chat");
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const { messages, send, loading, tools, language, clear } = useChat(provider);

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
        {/* Scan line */}
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
          <div className="scan-line" />
        </div>

        {/* Header */}
        <header style={{ padding: "10px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--ink)", zIndex: 2, gap: 16 }}>
          {/* Tabs */}
          <div style={{ display: "flex", gap: 2 }}>
            {TABS.map(({ id, label, Icon }) => (
              <button key={id} onClick={() => setTab(id)}
                style={{
                  display: "flex", alignItems: "center", gap: 5,
                  padding: "6px 12px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 11, fontWeight: 500,
                  background: tab === id ? "var(--jade-dim)" : "transparent",
                  color: tab === id ? "var(--jade)" : "var(--muted)",
                  transition: "all 0.15s",
                }}>
                <Icon size={11} /> {label}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div style={{ fontSize: 10, color: "var(--jade)", display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 6, height: 6, background: "var(--jade)", borderRadius: "50%", animation: "pulse-jade 2s infinite", display: "inline-block" }} />
              {provider.toUpperCase()} · LIVE
            </div>
            <button onClick={clear} style={{ background: "transparent", border: "1px solid var(--border)", borderRadius: 6, padding: "5px 8px", cursor: "pointer", color: "var(--muted)", display: "flex", alignItems: "center", gap: 4, fontSize: 11 }}>
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
            {/* Input */}
            <div style={{ borderTop: "1px solid var(--border)", padding: "14px 20px", background: "var(--ink)" }}>
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
                CBN · NFIU · NDPA 2023 · Bayesian Fraud Scoring · Groq Free Tier
              </div>
            </div>
          </div>

          {tab === "workflows" && (
            <div style={{ height: "100%", overflowY: "auto" }}>
              <WorkflowDemo provider={provider} />
            </div>
          )}
          {tab === "eval" && (
            <div style={{ height: "100%", overflowY: "auto" }}>
              <EvalDashboard provider={provider} />
            </div>
          )}
          {tab === "voice" && (
            <div style={{ height: "100%", overflowY: "auto" }}>
              <MediaInput provider={provider} onTranscript={(t) => { setInput(t); setTab("chat"); }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
