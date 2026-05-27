import { useState } from "react";
import { runEval } from "../utils/api";
import { BarChart2, CheckCircle, XCircle, Loader } from "lucide-react";

export function EvalDashboard({ provider }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const r = await runEval(provider);
      setResult(r);
    } catch { setResult(null); }
    finally { setLoading(false); }
  };

  const bar = (val) => (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, background: "var(--border)", borderRadius: 4, height: 6 }}>
        <div style={{ width: `${val * 100}%`, background: val > 0.8 ? "var(--jade)" : val > 0.6 ? "var(--gold)" : "var(--ember)", height: "100%", borderRadius: 4, transition: "width 0.6s" }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: "IBM Plex Mono", color: "var(--text)", minWidth: 36 }}>{(val * 100).toFixed(1)}%</span>
    </div>
  );

  return (
    <div style={{ padding: 20, overflowY: "auto", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 16, color: "var(--white)" }}>Signal Evaluation</div>
          <div style={{ fontSize: 11, color: "var(--muted)" }}>40-sample synthetic Nigerian fraud dataset · Bayesian scorer</div>
        </div>
        <button onClick={run} disabled={loading} className="btn-primary"
          style={{ padding: "8px 16px", borderRadius: 8, fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
          {loading ? <><Loader size={13} className="animate-spin" /> Running…</> : <><BarChart2 size={13} /> Run Eval</>}
        </button>
      </div>

      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Overall metrics */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
            {[
              { label: "Accuracy",  val: result.accuracy },
              { label: "Precision", val: result.overall_precision },
              { label: "Recall",    val: result.overall_recall },
              { label: "F1 Score",  val: result.overall_f1 },
            ].map(({ label, val }) => (
              <div key={label} style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px" }}>
                <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 4 }}>{label}</div>
                <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 22, color: val > 0.8 ? "var(--jade)" : val > 0.6 ? "var(--gold)" : "var(--ember)" }}>
                  {(val * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>

          {/* Confusion matrix */}
          <div style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px" }}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 10, fontWeight: 600 }}>Confusion Matrix</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[
                { label: "True Positives",  val: result.confusion_matrix.TP, good: true },
                { label: "False Positives", val: result.confusion_matrix.FP, good: false },
                { label: "True Negatives",  val: result.confusion_matrix.TN, good: true },
                { label: "False Negatives", val: result.confusion_matrix.FN, good: false },
              ].map(({ label, val, good }) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", background: "var(--ink-3)", borderRadius: 8 }}>
                  {good ? <CheckCircle size={14} color="var(--jade)" /> : <XCircle size={14} color="var(--ember)" />}
                  <div>
                    <div style={{ fontSize: 10, color: "var(--muted)" }}>{label}</div>
                    <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 600, color: "var(--white)" }}>{val}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Per-signal table */}
          <div style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px" }}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 12, fontWeight: 600 }}>Per-Signal Metrics</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {result.per_signal_metrics.map(s => (
                <div key={s.signal} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 10 }}>
                  <div style={{ fontSize: 11, fontFamily: "IBM Plex Mono", color: "var(--jade)", marginBottom: 6 }}>{s.signal}</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
                    <div><div style={{ fontSize: 9, color: "var(--muted)" }}>Precision</div>{bar(s.precision)}</div>
                    <div><div style={{ fontSize: 9, color: "var(--muted)" }}>Recall</div>{bar(s.recall)}</div>
                    <div><div style={{ fontSize: 9, color: "var(--muted)" }}>F1</div>{bar(s.f1)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!result && !loading && (
        <div style={{ textAlign: "center", marginTop: 60, color: "var(--muted)", fontSize: 13 }}>
          Click <strong style={{ color: "var(--jade)" }}>Run Eval</strong> to test the Bayesian fraud engine against 40 synthetic Nigerian transactions.
        </div>
      )}
    </div>
  );
}
