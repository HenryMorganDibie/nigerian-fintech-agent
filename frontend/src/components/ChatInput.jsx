import { useState, useRef } from "react";
import { Send, Mic, MicOff, Paperclip, Loader, X, FileText, Volume2 } from "lucide-react";
import { uploadVoice, uploadFile } from "../utils/api";

export function ChatInput({ onSend, loading, provider }) {
  const [input, setInput]         = useState("");
  const [recording, setRecording] = useState(false);
  const [attachment, setAttachment] = useState(null);
  const [mediaLoading, setMediaLoading] = useState(false);

  const textareaRef = useRef(null);
  const fileRef     = useRef(null);
  const mediaRef    = useRef(null);
  const chunksRef   = useRef([]);

  const autoResize = (el) => {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  };

  const handleSend = () => {
    const text = input.trim();
    if ((!text && !attachment) || loading) return;

    let finalMessage = text;

    if (attachment) {
      if (attachment.type === "voice") {
        finalMessage = `Voice message transcribed:\n\n${attachment.content}${text ? `\n\n${text}` : ""}`;
      } else if (attachment.type === "file") {
        const signals = attachment.fraudSignals?.length
          ? `\n\nFraud signals detected: ${attachment.fraudSignals.join(", ")}`
          : "";
        finalMessage = `File attached: ${attachment.label}\n\n${attachment.summary}${signals}${text ? `\n\n${text}` : ""}`;
      }
      setAttachment(null);
    }

    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    onSend(finalMessage);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = e => chunksRef.current.push(e.data);
      mr.onstop = async () => {
        const blob = new File([new Blob(chunksRef.current, { type: "audio/webm" })], "voice.webm", { type: "audio/webm" });
        setMediaLoading(true);
        try {
          const result = await uploadVoice(blob, provider);
          setAttachment({
            type: "voice",
            label: `Voice (${result.language_detected})`,
            content: result.transcript,
            enriched: result.enriched_transcript,
          });
        } catch {
          setAttachment({ type: "voice", label: "Voice", content: "Transcription failed, check GROQ_API_KEY", fraudSignals: [] });
        } finally {
          setMediaLoading(false);
        }
        stream.getTracks().forEach(t => t.stop());
      };
      mediaRef.current = mr;
      mr.start();
      setRecording(true);
    } catch {
      alert("Microphone access denied.");
    }
  };

  const stopRecording = () => {
    mediaRef.current?.stop();
    setRecording(false);
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMediaLoading(true);
    try {
      const result = await uploadFile(file, provider);
      setAttachment({
        type: "file",
        label: file.name,
        summary: result.summary || result.extracted_text?.slice(0, 200) || "File processed",
        fraudSignals: result.fraud_signals_detected || [],
        riskLevel: result.risk_level,
      });
    } catch {
      setAttachment({ type: "file", label: file.name, summary: "Could not analyse file.", fraudSignals: [] });
    } finally {
      setMediaLoading(false);
      e.target.value = "";
    }
  };

  const RISK_COLOR = { low: "var(--stamp-green)", medium: "var(--stamp-amber)", high: "var(--stamp-rust)", critical: "var(--stamp-rust)", unknown: "var(--ink-faint)" };

  return (
    <div className="no-rule" style={{ borderTop: "1px solid var(--rule-bold)", background: "var(--card)", flexShrink: 0 }}>

      {attachment && (
        <div style={{ margin: "8px 14px 0", padding: "8px 12px", background: "var(--paper-2)", border: "1px solid var(--rule-bold)", borderRadius: 4, display: "flex", alignItems: "flex-start", gap: 10 }}>
          <div style={{ flexShrink: 0, marginTop: 2, color: "var(--ink-soft)" }}>
            {attachment.type === "voice" ? <Volume2 size={14} /> : <FileText size={14} />}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--ink)" }}>{attachment.label}</span>
              {attachment.riskLevel && (
                <span className="stamp" style={{ color: RISK_COLOR[attachment.riskLevel] || "var(--ink-faint)" }}>
                  {attachment.riskLevel}
                </span>
              )}
            </div>
            <p style={{ fontSize: 12, color: "var(--ink-faint)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "100%" }}>
              {attachment.content || attachment.summary}
            </p>
            {attachment.fraudSignals?.length > 0 && (
              <div style={{ marginTop: 4, display: "flex", gap: 4, flexWrap: "wrap" }}>
                {attachment.fraudSignals.map(s => (
                  <span key={s} className="font-mono" style={{ fontSize: 9, color: "var(--stamp-rust)", background: "var(--stamp-rust-wash)", border: "1px solid var(--stamp-rust)", borderRadius: 2, padding: "1px 5px" }}>{s}</span>
                ))}
              </div>
            )}
          </div>
          <button onClick={() => setAttachment(null)} style={{ flexShrink: 0, background: "transparent", border: "none", color: "var(--ink-faint)", cursor: "pointer", padding: 2 }}>
            <X size={13} />
          </button>
        </div>
      )}

      <div style={{ padding: "10px 14px", display: "flex", gap: 8, alignItems: "flex-end" }}>

        <button
          onClick={() => fileRef.current?.click()}
          disabled={loading || mediaLoading}
          title="Attach file (PDF, CSV, image)"
          className="btn-ghost"
          style={{ flexShrink: 0, width: 36, height: 36, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", color: attachment?.type === "file" ? "var(--stamp-green)" : "var(--ink-faint)" }}>
          {mediaLoading && attachment === null ? <Loader size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Paperclip size={14} />}
        </button>
        <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.csv,.txt" onChange={handleFile} style={{ display: "none" }} />

        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => { setInput(e.target.value); autoResize(e.target); }}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          placeholder={attachment ? "Add a note (optional)" : "Ask in English, Pidgin, Yoruba, Hausa, or Igbo"}
          disabled={loading}
          rows={1}
          style={{ flex: 1, background: "var(--paper)", border: "1px solid var(--rule-bold)", borderRadius: 6, padding: "9px 13px", fontSize: 14, color: "var(--ink)", resize: "none", outline: "none", fontFamily: "Inter, sans-serif", lineHeight: 1.5, minHeight: 38, maxHeight: 120, transition: "border-color 0.15s" }}
          onFocus={e => e.target.style.borderColor = "var(--ink-faint)"}
          onBlur={e => e.target.style.borderColor = "var(--rule-bold)"}
        />

        <button
          onClick={recording ? stopRecording : startRecording}
          disabled={loading || (mediaLoading && !recording)}
          title={recording ? "Stop recording" : "Record voice message"}
          style={{ flexShrink: 0, width: 36, height: 36, borderRadius: 6, border: `1px solid ${recording ? "var(--stamp-rust)" : "var(--rule-bold)"}`, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", background: recording ? "var(--stamp-rust)" : "transparent", color: recording ? "var(--paper)" : attachment?.type === "voice" ? "var(--stamp-green)" : "var(--ink-faint)", transition: "all 0.2s" }}>
          {mediaLoading && recording === false && attachment === null
            ? <Loader size={14} />
            : recording ? <MicOff size={14} /> : <Mic size={14} />}
        </button>

        <button
          onClick={handleSend}
          disabled={loading || (!input.trim() && !attachment)}
          className="btn-primary"
          style={{ flexShrink: 0, width: 36, height: 36, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Send size={14} />
        </button>
      </div>

      <div className="font-mono" style={{ fontSize: 9.5, color: "var(--ink-faint)", textAlign: "center", paddingBottom: 8, letterSpacing: "0.02em" }}>
        CBN · NFIU · NDPA 2023 · seven-layer fraud intelligence · Groq, no cost
      </div>
    </div>
  );
}
