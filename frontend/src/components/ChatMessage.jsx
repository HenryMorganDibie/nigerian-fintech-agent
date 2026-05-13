import { ShieldAlert, Bot, User, Hash } from "lucide-react";

function md(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong style='color:#EAF1FB'>$1</strong>")
    .replace(/`(.*?)`/g, "<code style='background:#0E1520;padding:1px 5px;border-radius:3px;font-family:IBM Plex Mono,monospace;font-size:0.85em;color:#00E676'>$1</code>")
    .replace(/\n\n/g, "</p><p style='margin-top:0.6em'>")
    .replace(/\n/g, "<br/>")
    .replace(/^• /gm, "▸ ");
}

const RISK_COLORS = {
  low: "#00E676", medium: "#FFB300", high: "#FF8800", critical: "#FF4444"
};

export function ChatMessage({ message }) {
  const isUser = message.role === "user";
  const isError = message.error;
  const isStreaming = message.streaming && message.content === "";

  // Check if message content contains risk level
  const riskMatch = message.content?.match(/\b(LOW|MEDIUM|HIGH|CRITICAL)\b/);
  const riskLevel = riskMatch?.[1]?.toLowerCase();
  const riskColor = riskLevel ? RISK_COLORS[riskLevel] : null;

  return (
    <div className={`msg-in flex gap-3 ${isUser ? "flex-row-reverse" : ""} mb-5`}>
      {/* Avatar */}
      <div
        className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs"
        style={isUser
          ? { background: "var(--border)", color: "var(--muted)" }
          : { background: "var(--jade-dim)", border: "1px solid #00E67640", color: "var(--jade)" }
        }
      >
        {isUser ? <User size={12} /> : <Bot size={12} />}
      </div>

      {/* Bubble */}
      <div
        className="relative max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed"
        style={isUser
          ? { background: "var(--ink-3)", border: "1px solid var(--border)", borderTopRightRadius: 4 }
          : isError
          ? { background: "#FF44440D", border: "1px solid #FF444430", borderTopLeftRadius: 4 }
          : { background: "var(--ink-2)", border: `1px solid ${riskColor ? riskColor + "30" : "var(--border)"}`, borderTopLeftRadius: 4 }
        }
      >
        {/* Risk accent bar */}
        {riskColor && !isUser && (
          <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: 3, borderRadius: "8px 0 0 8px", background: riskColor }} />
        )}

        {isStreaming ? (
          <div className="flex gap-1 items-center py-1">
            <span className="dot w-1.5 h-1.5 rounded-full" style={{ background: "var(--jade)" }} />
            <span className="dot w-1.5 h-1.5 rounded-full" style={{ background: "var(--jade)" }} />
            <span className="dot w-1.5 h-1.5 rounded-full" style={{ background: "var(--jade)" }} />
          </div>
        ) : (
          <p dangerouslySetInnerHTML={{ __html: md(message.content || "") }} style={{ margin: 0, color: "var(--text)" }} />
        )}

        {/* Footer row */}
        <div className={`flex items-center gap-2 mt-2 ${isUser ? "justify-end" : "justify-start"}`}>
          <span style={{ fontSize: 10, color: "var(--muted)" }}>
            {message.timestamp?.toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" })}
          </span>
          {message.audit_id && (
            <span style={{ fontSize: 9, color: "var(--muted)", fontFamily: "IBM Plex Mono", display: "flex", alignItems: "center", gap: 2 }}>
              <Hash size={8} /> {message.audit_id.slice(0, 8)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
