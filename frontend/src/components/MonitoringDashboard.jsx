import { useState, useEffect } from "react";
import { Activity, AlertTriangle, CheckCircle, TrendingUp, RefreshCw, Send } from "lucide-react";

const BASE = import.meta.env.VITE_API_URL || "/api";

async function fetchDrift() {
  const r = await fetch(`${BASE}/fraud/drift`);
  return r.json();
}

async function submitFeedback(payload) {
  const r = await fetch(`${BASE}/fraud/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return r.json();
}

const STATUS_COLORS = {
  STABLE:         "var(--jade)",
  DRIFT_DETECTED: "var(--ember)",
  insufficient_data: "var(--muted)",
};

const OUTCOMES = [
  { value: "fraud_confirmed",    label: "✅ Fraud Confirmed",    color: "var(--ember)" },
  { value: "fraud_rejected",     label: "❌ Not Fraud",          color: "var(--jade)" },
  { value: "false_positive",     label: "⚠️ False Positive",     color: "var(--gold)" },
  { value: "chargeback_confirmed", label: "🔄 Chargeback",       color: "#8B5CF6" },
];

export function MonitoringDashboard() {
  const [drift, setDrift]         = useState(null);
  const [loading, setLoading]     = useState(false);
  const [feedback, setFeedback]   = useState({ transaction_id: "", audit_id: "", outcome: "fraud_confirmed", notes: "" });
  const [fbResult, setFbResult]   = useState(null);
  const [fbLoading, setFbLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try { setDrift(await fetchDrift()); } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleFeedback = async () => {
    if (!feedback.transaction_id) return;
    setFbLoading(true);
    try {
      const r = await submitFeedback(feedback);
      setFbResult(r);
    } catch { setFbResult({ error: "Failed to submit" }); }
    setFbLoading(false);
  };

  const driftStatus = drift?.overall_drift_status || "insufficient_data";

  return (
    <div style={{ padding: 20, overflowY: "auto", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 16, color: "var(--white)" }}>
            Monitoring & Drift Detection
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)" }}>
            PSI drift · fraud rate · false positive tracking · analyst feedback
          </div>
        </div>
        <button onClick={load} disabled={loading}
          style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 14px", borderRadius: 8, border: "1px solid var(--border)", background: "transparent", cursor: "pointer", color: "var(--muted)", fontSize: 11 }}>
          <RefreshCw size={12} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} /> Refresh
        </button>
      </div>

      {/* Drift status banner */}
      {drift && (
        <div style={{ padding: "12px 16px", borderRadius: 10, marginBottom: 16, border: `1px solid ${STATUS_COLORS[driftStatus]}40`, background: `${STATUS_COLORS[driftStatus]}10`, display: "flex", alignItems: "center", gap: 10 }}>
          {driftStatus === "STABLE"
            ? <CheckCircle size={16} color="var(--jade)" />
            : driftStatus === "DRIFT_DETECTED"
            ? <AlertTriangle size={16} color="var(--ember)" />
            : <Activity size={16} color="var(--muted)" />}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: STATUS_COLORS[driftStatus] }}>
              {driftStatus === "STABLE" ? "System Stable" : driftStatus === "DRIFT_DETECTED" ? "Drift Detected" : "Collecting Data"}
            </div>
            <div style={{ fontSize: 10, color: "var(--muted)" }}>
              {drift.window_size} decisions analysed · PSI {drift.psi_score ?? "—"} · FP rate {drift.false_positive_rate != null ? (drift.false_positive_rate * 100).toFixed(1) + "%" : "—"}
            </div>
          </div>
        </div>
      )}

      {/* Key metrics */}
      {drift && drift.recent_mean_score != null && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
          {[
            { label: "Avg Risk Score", val: drift.recent_mean_score?.toFixed(1) ?? "—", unit: "/100" },
            { label: "PSI Score",      val: drift.psi_score?.toFixed(3) ?? "—",       unit: drift.psi_score > 0.25 ? " ⚠️" : " ✅" },
            { label: "Confirmed Fraud",val: drift.confirmed_fraud_count ?? 0,          unit: " cases" },
          ].map(({ label, val, unit }) => (
            <div key={label} style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px" }}>
              <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 4 }}>{label}</div>
              <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 700, fontSize: 18, color: "var(--white)" }}>
                {val}<span style={{ fontSize: 11, color: "var(--muted)" }}>{unit}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Drift alerts */}
      {drift?.drift_alerts?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "var(--ember)", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            ⚠️ Drift Alerts
          </div>
          {drift.drift_alerts.map((a, i) => (
            <div key={i} style={{ padding: "10px 14px", background: "#FF444410", border: "1px solid #FF444430", borderRadius: 8, marginBottom: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ember)", marginBottom: 4 }}>{a.type}</div>
              <div style={{ fontSize: 11, color: "var(--text)", marginBottom: 4 }}>{a.detail}</div>
              <div style={{ fontSize: 10, color: "var(--jade)", fontStyle: "italic" }}>→ {a.recommendation}</div>
            </div>
          ))}
        </div>
      )}

      {/* Signal frequency alerts */}
      {drift?.signal_frequency_alerts?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "var(--gold)", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Signal Frequency Alerts
          </div>
          {drift.signal_frequency_alerts.map((a, i) => (
            <div key={i} style={{ padding: "8px 12px", background: "var(--gold-dim, #FFB30010)", border: "1px solid #FFB30030", borderRadius: 8, marginBottom: 6 }}>
              <span style={{ fontFamily: "IBM Plex Mono", fontSize: 10, color: "var(--gold)" }}>{a.signal}</span>
              <span style={{ fontSize: 10, color: "var(--muted)", marginLeft: 8 }}>hit rate: {(a.recent_hit_rate * 100).toFixed(1)}%</span>
              <div style={{ fontSize: 10, color: "var(--text)", marginTop: 3 }}>{a.alert}</div>
            </div>
          ))}
        </div>
      )}

      {/* Insufficient data state */}
      {drift?.status === "insufficient_data" && (
        <div style={{ textAlign: "center", padding: "30px 20px", color: "var(--muted)", fontSize: 13 }}>
          <Activity size={28} style={{ marginBottom: 10, opacity: 0.4 }} />
          <div>Need at least 20 fraud analyses to start drift detection.</div>
          <div style={{ fontSize: 11, marginTop: 6 }}>Use the Workflows tab or run fraud analyses to build up history.</div>
        </div>
      )}

      {/* Analyst Feedback Loop */}
      <div style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 12, padding: 16, marginTop: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--white)", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
          <TrendingUp size={13} color="var(--jade)" /> Analyst Feedback Loop
        </div>
        <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 14 }}>
          Submit real-world outcomes to improve signal weights and update Bayesian priors
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input value={feedback.transaction_id} onChange={e => setFeedback(f => ({ ...f, transaction_id: e.target.value }))}
            placeholder="Transaction ID"
            style={{ background: "var(--ink-3)", border: "1px solid var(--border-bright)", borderRadius: 8, padding: "8px 12px", fontSize: 12, color: "var(--text)", outline: "none", fontFamily: "IBM Plex Mono" }} />
          <input value={feedback.audit_id} onChange={e => setFeedback(f => ({ ...f, audit_id: e.target.value }))}
            placeholder="Audit Log ID (from case output)"
            style={{ background: "var(--ink-3)", border: "1px solid var(--border-bright)", borderRadius: 8, padding: "8px 12px", fontSize: 12, color: "var(--text)", outline: "none", fontFamily: "IBM Plex Mono" }} />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {OUTCOMES.map(o => (
              <button key={o.value} onClick={() => setFeedback(f => ({ ...f, outcome: o.value }))}
                style={{ padding: "8px 10px", borderRadius: 8, border: `1px solid ${feedback.outcome === o.value ? o.color : "var(--border)"}`, background: feedback.outcome === o.value ? `${o.color}15` : "transparent", cursor: "pointer", fontSize: 11, color: feedback.outcome === o.value ? o.color : "var(--muted)", transition: "all 0.15s", textAlign: "left" }}>
                {o.label}
              </button>
            ))}
          </div>

          <input value={feedback.notes} onChange={e => setFeedback(f => ({ ...f, notes: e.target.value }))}
            placeholder="Analyst notes (optional)"
            style={{ background: "var(--ink-3)", border: "1px solid var(--border-bright)", borderRadius: 8, padding: "8px 12px", fontSize: 12, color: "var(--text)", outline: "none" }} />

          <button onClick={handleFeedback} disabled={fbLoading || !feedback.transaction_id}
            className="btn-primary" style={{ padding: "10px 0", borderRadius: 10, fontSize: 12, display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            <Send size={13} /> {fbLoading ? "Submitting…" : "Submit Feedback"}
          </button>
        </div>

        {fbResult && (
          <div style={{ marginTop: 12, padding: "10px 12px", background: fbResult.error ? "#FF444415" : "var(--jade-dim)", borderRadius: 8 }}>
            {fbResult.error
              ? <div style={{ fontSize: 11, color: "var(--ember)" }}>{fbResult.error}</div>
              : <div style={{ fontSize: 11, color: "var(--jade)" }}>
                  ✅ Recorded · Total feedback: {fbResult.feedback_summary?.total_feedback} · FP rate: {((fbResult.feedback_summary?.false_positive_rate || 0) * 100).toFixed(1)}%
                </div>
            }
          </div>
        )}
      </div>
    </div>
  );
}
