import { useState, useRef } from "react";
import { runEval, uploadEvalCsv, evalCsvTemplateUrl } from "../utils/api";
import { GaugeCircle, Check, X, Loader, Upload, Download, FileWarning } from "lucide-react";

export function EvalDashboard({ provider }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [source, setSource] = useState(null);   // "synthetic" | "upload"
  const [uploadError, setUploadError] = useState(null);
  const fileRef = useRef(null);

  const runSynthetic = async () => {
    setLoading(true);
    setUploadError(null);
    try {
      const r = await runEval(provider);
      setResult(r);
      setSource("synthetic");
    } catch { setResult(null); }
    finally { setLoading(false); }
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setUploadError(null);
    try {
      const r = await uploadEvalCsv(file, provider);
      setResult(r);
      setSource("upload");
    } catch (err) {
      setUploadError(err.message || "Upload failed.");
      setResult(null);
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  };

  const tone = (v) => v > 0.8 ? "var(--stamp-green)" : v > 0.6 ? "var(--stamp-amber)" : "var(--stamp-rust)";

  const bar = (val) => (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, background: "var(--rule)", borderRadius: 2, height: 5 }}>
        <div style={{ width: `${val * 100}%`, background: tone(val), height: "100%", borderRadius: 2, transition: "width 0.5s" }} />
      </div>
      <span className="font-mono" style={{ fontSize: 11, color: "var(--ink-soft)", minWidth: 38 }}>{(val * 100).toFixed(1)}%</span>
    </div>
  );

  return (
    <div style={{ padding: 22, overflowY: "auto", height: "100%", maxWidth: 880 }}>
      <div style={{ marginBottom: 18 }}>
        <div className="font-display" style={{ fontSize: 19, color: "var(--ink)" }}>Signal evaluation</div>
        <div style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 3 }}>
          Score the Bayesian fraud engine against a labelled dataset, the built-in 40-sample synthetic set, or your own real transaction history.
        </div>
      </div>

      {/* Source controls */}
      <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={runSynthetic} disabled={loading} className="btn-primary"
          style={{ padding: "8px 16px", borderRadius: 4, fontSize: 12.5, display: "flex", alignItems: "center", gap: 7 }}>
          {loading ? <><Loader size={13} className="animate-spin" /> Running</> : <><GaugeCircle size={13} /> Run synthetic set</>}
        </button>

        <button onClick={() => fileRef.current?.click()} disabled={loading} className="btn-ghost"
          style={{ padding: "8px 16px", borderRadius: 4, fontSize: 12.5, display: "flex", alignItems: "center", gap: 7 }}>
          <Upload size={13} /> Upload your own CSV
        </button>
        <input ref={fileRef} type="file" accept=".csv" onChange={handleFile} style={{ display: "none" }} />

        <a href={evalCsvTemplateUrl} download className="font-mono"
          style={{ fontSize: 11, color: "var(--ink-faint)", display: "flex", alignItems: "center", gap: 5, textDecoration: "none" }}>
          <Download size={12} /> download template
        </a>
      </div>

      {uploadError && (
        <div className="case-tab" style={{ borderRadius: 4, padding: "10px 13px", marginBottom: 16, borderLeftColor: "var(--stamp-rust)", display: "flex", gap: 9, alignItems: "flex-start" }}>
          <FileWarning size={14} color="var(--stamp-rust)" style={{ flexShrink: 0, marginTop: 1 }} />
          <div style={{ fontSize: 12.5, color: "var(--ink)" }}>{uploadError}</div>
        </div>
      )}

      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {source === "upload" && result.upload_summary && (
            <div className="font-mono" style={{ fontSize: 11, color: "var(--ink-faint)" }}>
              {result.upload_summary.filename}, {result.upload_summary.rows_parsed} rows scored
              {result.upload_summary.rows_skipped > 0 && `, ${result.upload_summary.rows_skipped} skipped`}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
            {[
              { label: "Accuracy",  val: result.accuracy },
              { label: "Precision", val: result.overall_precision },
              { label: "Recall",    val: result.overall_recall },
              { label: "F1 score",  val: result.overall_f1 },
            ].map(({ label, val }) => (
              <div key={label} className="case-tab" style={{ borderRadius: 4, padding: "12px 14px", borderLeftColor: tone(val) }}>
                <div style={{ fontSize: 10.5, color: "var(--ink-faint)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
                <div className="font-display" style={{ fontSize: 23, color: tone(val) }}>
                  {(val * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>

          <div className="case-tab" style={{ borderRadius: 4, padding: "14px 16px" }}>
            <div style={{ fontSize: 12, color: "var(--ink-soft)", marginBottom: 11, fontWeight: 600 }}>Confusion matrix</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[
                { label: "True positives",  val: result.confusion_matrix.TP, good: true },
                { label: "False positives", val: result.confusion_matrix.FP, good: false },
                { label: "True negatives",  val: result.confusion_matrix.TN, good: true },
                { label: "False negatives", val: result.confusion_matrix.FN, good: false },
              ].map(({ label, val, good }) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", background: "var(--paper-2)", borderRadius: 4 }}>
                  {good ? <Check size={14} color="var(--stamp-green)" strokeWidth={2.25} /> : <X size={14} color="var(--stamp-rust)" strokeWidth={2.25} />}
                  <div>
                    <div style={{ fontSize: 10.5, color: "var(--ink-faint)" }}>{label}</div>
                    <div className="font-mono" style={{ fontWeight: 600, color: "var(--ink)" }}>{val}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="case-tab" style={{ borderRadius: 4, padding: "14px 16px" }}>
            <div style={{ fontSize: 12, color: "var(--ink-soft)", marginBottom: 13, fontWeight: 600 }}>Per-signal metrics</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
              {result.per_signal_metrics.map(s => (
                <div key={s.signal} style={{ borderBottom: "1px solid var(--rule)", paddingBottom: 11 }}>
                  <div className="font-mono" style={{ fontSize: 11.5, color: "var(--ink)", marginBottom: 7 }}>{s.signal}</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                    <div><div style={{ fontSize: 9.5, color: "var(--ink-faint)" }}>precision</div>{bar(s.precision)}</div>
                    <div><div style={{ fontSize: 9.5, color: "var(--ink-faint)" }}>recall</div>{bar(s.recall)}</div>
                    <div><div style={{ fontSize: 9.5, color: "var(--ink-faint)" }}>f1</div>{bar(s.f1)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!result && !loading && (
        <div style={{ marginTop: 30, color: "var(--ink-faint)", fontSize: 13, lineHeight: 1.6, maxWidth: 460 }}>
          Run the built-in synthetic set, 20 confirmed fraud and 20 confirmed legitimate Nigerian transactions, or upload a CSV of your own labelled history to see how the same engine performs on real data.
        </div>
      )}
    </div>
  );
}
