import { useState } from "react";
import { runWorkflow } from "../utils/api";
import { Play, CheckCircle, AlertTriangle, Info, Zap, Loader } from "lucide-react";

const SCENARIOS = [
  { id: "loan_application_fraud_check", label: "Loan Application Fraud", emoji: "💰", desc: "First-party fraud detection on digital loan disbursements" },
  { id: "agent_wallet_monitoring",      label: "Agent Wallet Monitor",  emoji: "🏪", desc: "Mule chain detection through OPay/Moniepoint agent networks" },
  { id: "chargeback_investigation",     label: "Chargeback Investigation", emoji: "🔍", desc: "SIM swap + device change analysis for disputed transactions" },
];

const STATUS_ICONS = {
  pass:   <CheckCircle size={13} color="var(--jade)" />,
  alert:  <AlertTriangle size={13} color="var(--gold)" />,
  action: <Zap size={13} color="var(--ember)" />,
  info:   <Info size={13} color="var(--sky)" />,
};

const RISK_COLORS = { low: "var(--jade)", medium: "var(--gold)", high: "#FF8800", critical: "var(--ember)" };

export function WorkflowDemo({ provider }) {
  const [active, setActive] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async (id) => {
    setActive(id);
    setResult(null);
    setLoading(true);
    try {
      const r = await runWorkflow(id, provider);
      setResult(r);
    } catch { setResult(null); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ padding: 20, overflowY: "auto", height: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 16, color: "var(--white)" }}>Workflow Demos</div>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>One-click end-to-end fintech fraud scenarios with case output</div>
      </div>

      {/* Scenario buttons */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
        {SCENARIOS.map(s => (
          <button key={s.id} onClick={() => run(s.id)} disabled={loading}
            style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "12px 14px", borderRadius: 10, cursor: "pointer",
              background: active === s.id ? "var(--jade-dim)" : "var(--ink-2)",
              border: `1px solid ${active === s.id ? "#00E67650" : "var(--border)"}`,
              transition: "all 0.15s", textAlign: "left",
            }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 18 }}>{s.emoji}</span>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--white)" }}>{s.label}</div>
                <div style={{ fontSize: 10, color: "var(--muted)" }}>{s.desc}</div>
              </div>
            </div>
            {loading && active === s.id
              ? <Loader size={14} color="var(--jade)" className="animate-spin" />
              : <Play size={13} color="var(--jade)" />}
          </button>
        ))}
      </div>

      {/* Result */}
      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 13, color: "var(--white)" }}>{result.scenario_name}</div>

          {/* Steps */}
          {result.steps?.map(step => (
            <div key={step.step} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "10px 12px", background: "var(--ink-2)", borderRadius: 8, border: "1px solid var(--border)" }}>
              <div style={{ marginTop: 1 }}>{STATUS_ICONS[step.status] || STATUS_ICONS.info}</div>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--white)", marginBottom: 2 }}>Step {step.step}: {step.name}</div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{step.result}</div>
              </div>
            </div>
          ))}

          {/* Verdict */}
          <div style={{ padding: "12px 14px", background: "var(--ember-dim, #FF444410)", border: "1px solid #FF444430", borderRadius: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ember)", marginBottom: 4 }}>VERDICT</div>
            <div style={{ fontSize: 12, color: "var(--text)" }}>{result.final_verdict}</div>
          </div>

          {/* Case output */}
          {result.case_output && (
            <div style={{ padding: "12px 14px", background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 10 }}>
              <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>Case Output</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 9, color: "var(--muted)" }}>Risk Score</div>
                  <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 700, fontSize: 18, color: RISK_COLORS[result.case_output.risk_level] }}>
                    {result.case_output.risk_score}/100
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 9, color: "var(--muted)" }}>Fraud Probability</div>
                  <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 700, fontSize: 18, color: RISK_COLORS[result.case_output.risk_level] }}>
                    {(result.case_output.posterior_fraud_probability * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
              {result.case_output.top_3_signals?.map(sig => (
                <div key={sig.name} style={{ fontSize: 10, padding: "4px 0", borderTop: "1px solid var(--border)", color: "var(--muted)" }}>
                  #{sig.rank} <span style={{ fontFamily: "IBM Plex Mono", color: "var(--jade)" }}>{sig.name}</span> — {sig.description.slice(0, 60)}…
                </div>
              ))}
              <div style={{ fontSize: 9, marginTop: 8, fontFamily: "IBM Plex Mono", color: "var(--muted)" }}>
                Audit: {result.case_output.audit_log_id?.slice(0, 12)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
