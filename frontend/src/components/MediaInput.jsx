import { useState, useRef } from "react";
import { Mic, MicOff, Upload, FileText, Loader, CheckCircle } from "lucide-react";
import { uploadVoice, uploadFile } from "../utils/api";

export function MediaInput({ provider, onTranscript }) {
  const [recording, setRecording] = useState(false);
  const [voiceResult, setVoiceResult] = useState(null);
  const [fileResult, setFileResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  const fileRef = useRef(null);

  const LANG_FLAGS = { english: "🇬🇧", pidgin: "🇳🇬", yoruba: "🇳🇬", hausa: "🇳🇬", igbo: "🇳🇬" };

  // Voice recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = e => chunksRef.current.push(e.data);
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const file = new File([blob], "voice.webm", { type: "audio/webm" });
        setLoading(true);
        try {
          const result = await uploadVoice(file, provider);
          setVoiceResult(result);
          if (result.transcript) onTranscript?.(result.transcript);
        } catch (e) {
          setVoiceResult({ error: "Transcription failed. Check GROQ_API_KEY." });
        } finally { setLoading(false); }
        stream.getTracks().forEach(t => t.stop());
      };
      mediaRef.current = mr;
      mr.start();
      setRecording(true);
    } catch {
      alert("Microphone access denied. Please allow mic access to use voice input.");
    }
  };

  const stopRecording = () => {
    mediaRef.current?.stop();
    setRecording(false);
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setFileResult(null);
    try {
      const result = await uploadFile(file, provider);
      setFileResult(result);
    } catch {
      setFileResult({ error: "File analysis failed." });
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  };

  const riskColor = { low: "var(--jade)", medium: "var(--gold)", high: "#FF8800", critical: "var(--ember)", unknown: "var(--muted)" };

  return (
    <div style={{ padding: 20, overflowY: "auto", height: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 16, color: "var(--white)" }}>Voice & File Input</div>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>
          Speak in any Nigerian language · Upload PDF, image, CSV for fraud scan
        </div>
      </div>

      {/* Voice recorder */}
      <div style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text)", marginBottom: 12 }}>🎙️ Voice Input</div>
        <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 12 }}>
          Supports English · Pidgin · Yoruba · Hausa · Igbo — transcribed via Groq Whisper (free)
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button
            onClick={recording ? stopRecording : startRecording}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "10px 16px", borderRadius: 10, border: "none", cursor: "pointer",
              background: recording ? "var(--ember)" : "var(--jade)",
              color: "var(--ink)", fontWeight: 600, fontSize: 12, transition: "all 0.2s",
            }}>
            {recording ? <><MicOff size={14} /> Stop Recording</> : <><Mic size={14} /> Start Recording</>}
          </button>
          {loading && <Loader size={14} color="var(--jade)" />}
          {recording && (
            <span style={{ fontSize: 11, color: "var(--ember)", display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--ember)", animation: "pulse-jade 1s infinite" }} />
              Recording…
            </span>
          )}
        </div>

        {voiceResult && (
          <div style={{ marginTop: 12, padding: "10px 12px", background: "var(--ink-3)", borderRadius: 8 }}>
            {voiceResult.error
              ? <div style={{ color: "var(--ember)", fontSize: 11 }}>{voiceResult.error}</div>
              : <>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                    <CheckCircle size={12} color="var(--jade)" />
                    <span style={{ fontSize: 10, color: "var(--jade)" }}>
                      {LANG_FLAGS[voiceResult.language_detected]} {voiceResult.language_detected} · {(voiceResult.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text)", fontStyle: "italic" }}>"{voiceResult.transcript}"</div>
                  <div style={{ fontSize: 10, color: "var(--jade)", marginTop: 6 }}>↑ Sent to chat agent</div>
                </>
            }
          </div>
        )}
      </div>

      {/* File upload */}
      <div style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 12, padding: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text)", marginBottom: 12 }}>📎 File Upload & Fraud Scan</div>
        <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 12 }}>
          Supported: PDF, PNG, JPG, CSV, TXT · Auto-scans for Nigerian fraud signals
        </div>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={loading}
          style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 16px", borderRadius: 10, border: "1px solid var(--border-bright)", background: "var(--ink-3)", cursor: "pointer", color: "var(--text)", fontSize: 12, fontWeight: 500 }}>
          {loading ? <><Loader size={13} color="var(--jade)" /> Analysing…</> : <><Upload size={13} /> Choose File</>}
        </button>
        <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.csv,.txt" onChange={handleFile} style={{ display: "none" }} />

        {fileResult && (
          <div style={{ marginTop: 12, padding: "10px 12px", background: "var(--ink-3)", borderRadius: 8 }}>
            {fileResult.error
              ? <div style={{ color: "var(--ember)", fontSize: 11 }}>{fileResult.error}</div>
              : <>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <FileText size={12} color="var(--jade)" />
                      <span style={{ fontSize: 11, color: "var(--text)", fontWeight: 600 }}>{fileResult.filename}</span>
                    </div>
                    <span style={{ fontSize: 10, fontFamily: "IBM Plex Mono", color: riskColor[fileResult.risk_level] || "var(--muted)", padding: "2px 8px", borderRadius: 4, background: `${riskColor[fileResult.risk_level] || "var(--muted)"}20` }}>
                      {fileResult.risk_level?.toUpperCase()}
                    </span>
                  </div>
                  {fileResult.fraud_signals_detected?.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 9, color: "var(--muted)", marginBottom: 4 }}>Fraud Signals Detected</div>
                      {fileResult.fraud_signals_detected.map(s => (
                        <span key={s} style={{ display: "inline-block", fontSize: 9, fontFamily: "IBM Plex Mono", color: "var(--ember)", background: "#FF444415", border: "1px solid #FF444430", borderRadius: 4, padding: "1px 6px", marginRight: 4, marginBottom: 4 }}>{s}</span>
                      ))}
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>{fileResult.summary}</div>
                </>
            }
          </div>
        )}
      </div>
    </div>
  );
}
