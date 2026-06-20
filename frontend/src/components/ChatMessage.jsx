import { UserRound, ShieldHalf, Fingerprint } from "lucide-react";

function md(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong style='color:var(--ink)'>$1</strong>")
    .replace(/`(.*?)`/g, "<code style='background:var(--paper-3);padding:1px 5px;border-radius:2px;font-family:\"Roboto Mono\",monospace;font-size:0.84em;color:var(--stamp-navy)'>$1</code>")
    .replace(/\n\n/g, "</p><p style='margin-top:0.55em'>")
    .replace(/\n/g, "<br/>");
}

const RISK = {
  low:      { c: "var(--stamp-green)", w: "var(--stamp-green-wash)" },
  medium:   { c: "var(--stamp-amber)", w: "var(--stamp-amber-wash)" },
  high:     { c: "var(--stamp-rust)",  w: "var(--stamp-rust-wash)" },
  critical: { c: "var(--stamp-rust)",  w: "var(--stamp-rust-wash)" },
};

export function ChatMessage({ message }) {
  const isUser      = message.role === "user";
  const isError     = message.error;
  const isStreaming = message.streaming && message.content === "";
  const riskMatch   = message.content?.match(/\b(LOW|MEDIUM|HIGH|CRITICAL)\b/);
  const risk        = riskMatch ? RISK[riskMatch[1].toLowerCase()] : null;

  return (
    <div className="msg-in" style={{ display: "flex", flexDirection: isUser ? "row-reverse" : "row", gap: 9, marginBottom: 14, alignItems: "flex-end" }}>

      {/* Marker */}
      <div style={{ flexShrink: 0, width: 24, height: 24, borderRadius: 3, display: "flex", alignItems: "center", justifyContent: "center",
        background: isUser ? "var(--paper-3)" : "var(--card)",
        border: isUser ? "1px solid var(--rule-bold)" : "1px solid var(--rule-bold)",
        color: isUser ? "var(--ink-faint)" : "var(--ink-soft)" }}>
        {isUser ? <UserRound size={12} strokeWidth={1.75} /> : <ShieldHalf size={12} strokeWidth={1.75} />}
      </div>

      {/* Case tab */}
      <div className={!isUser ? "case-tab" : ""} style={{
        maxWidth: "min(82%, 540px)", borderRadius: 3, padding: "10px 13px",
        fontSize: 14, lineHeight: 1.55,
        background:    isUser ? "var(--paper-3)" : isError ? "var(--stamp-rust-wash)" : "var(--card)",
        border:        isUser ? "1px solid var(--rule-bold)" : isError ? "1px solid var(--stamp-rust)" : undefined,
        borderLeftColor: !isUser && !isError ? (risk ? risk.c : "var(--rule-bold)") : undefined,
        position: "relative",
      }}>
        {isStreaming ? (
          <div style={{ display: "flex", gap: 5, alignItems: "center", padding: "2px 0" }}>
            <span className="tick" style={{ width: 4, height: 11, background: "var(--ink-faint)", display: "inline-block" }} />
            <span className="tick" style={{ width: 4, height: 11, background: "var(--ink-faint)", display: "inline-block" }} />
            <span className="tick" style={{ width: 4, height: 11, background: "var(--ink-faint)", display: "inline-block" }} />
          </div>
        ) : (
          <p dangerouslySetInnerHTML={{ __html: md(message.content || "") }} style={{ margin: 0, color: "var(--ink)" }} />
        )}
        <div style={{ display: "flex", gap: 9, marginTop: 7, justifyContent: isUser ? "flex-end" : "flex-start", alignItems: "center" }}>
          <span className="font-mono" style={{ fontSize: 10, color: "var(--ink-faint)" }}>
            {message.timestamp?.toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" })}
          </span>
          {message.audit_id && (
            <span className="font-mono" style={{ fontSize: 9.5, color: "var(--ink-faint)", display: "flex", alignItems: "center", gap: 3 }}>
              <Fingerprint size={10} strokeWidth={1.75} />{message.audit_id.slice(0, 8)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
