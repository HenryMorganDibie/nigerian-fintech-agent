import { Bot, User, Hash } from "lucide-react";

function md(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong style='color:#EAF1FB'>$1</strong>")
    .replace(/`(.*?)`/g, "<code style='background:#0E1520;padding:1px 5px;border-radius:3px;font-family:monospace;font-size:0.82em;color:#00E676'>$1</code>")
    .replace(/\n\n/g, "</p><p style='margin-top:0.55em'>")
    .replace(/\n/g, "<br/>");
}

const RISK = { low: "#00E676", medium: "#FFB300", high: "#FF8800", critical: "#FF4444" };

export function ChatMessage({ message }) {
  const isUser     = message.role === "user";
  const isError    = message.error;
  const isStreaming = message.streaming && message.content === "";
  const riskMatch  = message.content?.match(/\b(LOW|MEDIUM|HIGH|CRITICAL)\b/);
  const riskColor  = riskMatch ? RISK[riskMatch[1].toLowerCase()] : null;

  return (
    <div className="msg-in" style={{ display: "flex", flexDirection: isUser ? "row-reverse" : "row", gap: 8, marginBottom: 14, alignItems: "flex-end" }}>

      {/* Avatar */}
      <div style={{ flexShrink: 0, width: 26, height: 26, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
        background: isUser ? "var(--border)" : "var(--jade-dim)",
        border: isUser ? "none" : "1px solid #00E67640",
        color: isUser ? "var(--muted)" : "var(--jade)" }}>
        {isUser ? <User size={12} /> : <Bot size={12} />}
      </div>

      {/* Bubble */}
      <div style={{
        maxWidth: "min(82%, 520px)", borderRadius: 14, padding: "10px 13px",
        fontSize: 14, lineHeight: 1.55,
        background:    isUser  ? "var(--ink-3)" : isError ? "#FF44440D" : "var(--ink-2)",
        border:        isUser  ? "1px solid var(--border)" : isError ? "1px solid #FF444430" : `1px solid ${riskColor ? riskColor + "30" : "var(--border)"}`,
        borderTopLeftRadius:  isUser  ? 14 : 4,
        borderTopRightRadius: isUser  ? 4  : 14,
        position: "relative",
      }}>
        {/* Risk accent bar */}
        {riskColor && !isUser && (
          <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: 3, borderRadius: "8px 0 0 8px", background: riskColor }} />
        )}
        <div style={{ paddingLeft: riskColor && !isUser ? 6 : 0 }}>
          {isStreaming ? (
            <div style={{ display: "flex", gap: 4, alignItems: "center", padding: "2px 0" }}>
              <span className="dot" style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--jade)", display: "inline-block" }} />
              <span className="dot" style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--jade)", display: "inline-block" }} />
              <span className="dot" style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--jade)", display: "inline-block" }} />
            </div>
          ) : (
            <p dangerouslySetInnerHTML={{ __html: md(message.content || "") }} style={{ margin: 0, color: "var(--text)" }} />
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 6, justifyContent: isUser ? "flex-end" : "flex-start", alignItems: "center" }}>
            <span style={{ fontSize: 10, color: "var(--muted)" }}>
              {message.timestamp?.toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" })}
            </span>
            {message.audit_id && (
              <span style={{ fontSize: 9, color: "var(--muted)", fontFamily: "monospace", display: "flex", alignItems: "center", gap: 2 }}>
                <Hash size={8} />{message.audit_id.slice(0, 8)}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
