import { useState, useRef, useEffect } from "react";
import { Send, Trash2, AlertCircle } from "lucide-react";
import { useChat } from "./hooks/useChat";
import { ChatMessage } from "./components/ChatMessage";
import { Sidebar } from "./components/Sidebar";
import { ToolCallBanner } from "./components/ToolCallBanner";

export default function App() {
  const [provider, setProvider] = useState("openai");
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const { messages, send, loading, tools, language, clear } = useChat(provider);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (text) => {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    send(msg);
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* Sidebar */}
      <Sidebar provider={provider} setProvider={setProvider} language={language} onPrompt={handleSend} />

      {/* Main chat area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
        {/* Scan line decoration */}
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
          <div className="scan-line" />
        </div>

        {/* Header */}
        <header style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--ink)", zIndex: 1 }}>
          <div>
            <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 14, color: "var(--white)" }}>
              Agent Console
            </div>
            <div style={{ fontSize: 10, color: "var(--muted)", fontFamily: "IBM Plex Mono" }}>
              {messages.length - 1} exchanges · {provider.toUpperCase()}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div style={{ fontSize: 10, color: "var(--jade)", display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 6, height: 6, background: "var(--jade)", borderRadius: "50%", animation: "pulse-jade 2s infinite" }} />
              LIVE
            </div>
            <button onClick={clear} style={{ background: "transparent", border: "1px solid var(--border)", borderRadius: 6, padding: "5px 8px", cursor: "pointer", color: "var(--muted)", display: "flex", alignItems: "center", gap: 4, fontSize: 11 }}>
              <Trash2 size={11} /> Clear
            </button>
          </div>
        </header>

        {/* Tool call banner */}
        <ToolCallBanner tools={tools} />

        {/* Messages */}
        <div className="grid-bg" style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {messages.map((msg, i) => <ChatMessage key={i} message={msg} />)}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ borderTop: "1px solid var(--border)", padding: "14px 20px", background: "var(--ink)" }}>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 130) + "px"; }}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="Ask in English, Pidgin, Yoruba, Hausa, or Igbo..."
              disabled={loading}
              rows={1}
              style={{
                flex: 1, background: "var(--ink-2)", border: "1px solid var(--border-bright)",
                borderRadius: 12, padding: "10px 14px", fontSize: 13, color: "var(--text)",
                resize: "none", outline: "none", fontFamily: "DM Sans", lineHeight: 1.5,
                minHeight: 42, maxHeight: 130, transition: "border-color 0.2s",
              }}
              onFocus={e => e.target.style.borderColor = "#00E67660"}
              onBlur={e => e.target.style.borderColor = "var(--border-bright)"}
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="btn-primary"
              style={{ width: 42, height: 42, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}
            >
              <Send size={15} />
            </button>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 10, color: "var(--muted)" }}>
            <span>CBN · NFIU · NDPA 2023 compliance layer active</span>
            <span style={{ fontFamily: "IBM Plex Mono" }}>Shift+Enter for new line</span>
          </div>
        </div>
      </div>
    </div>
  );
}
