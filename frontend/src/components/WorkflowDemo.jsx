import { useState } from "react";
import { runWorkflow } from "../utils/api";
import { Play, Check, TriangleAlert, Info, Siren, Loader, Landmark, Store, Search } from "lucide-react";

const SCENARIOS = [
  { id: "loan_application_fraud_check", label: "Loan application fraud",   Icon: Landmark, desc: "First-party fraud on a digital loan disbursement" },
  { id: "agent_wallet_monitoring",      label: "Agent wallet monitor",     Icon: Store,    desc: "Mule chain detection through agent-network terminals" },
  { id: "chargeback_investigation",     label: "Chargeback investigation", Icon: Search,   desc: "SIM swap and device-change analysis on a dispute" },
];

const STATUS_ICONS = {
  pass:   <Check size={13} color="var(--stamp-green)" strokeWidth={2.25} />,
  alert:  <TriangleAlert size={13} color="var(--stamp-amber)" strokeWidth={2} />,
  action: <Siren size={13} color="var(--stamp-rust)" strokeWidth={2} />,
  info:   <Info size={13} color="var(--ink-faint)" strokeWidth={2} />,
};

const RISK_COLORS = { low: "var(--stamp-green)", medium: "var(--stamp-amber)", high: "var(--stamp-rust)", critical: "var(--stamp-rust)" };

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
    <div style={{ padding: 22, overflowY: "auto", height: "100%", maxWidth: 880 }}>
      <div style={{ marginBottom: 20 }}>
        <div className="font-display" style={{ fontSize: 19, color: "var(--ink)" }}>Workflow demonstrations</div>
        <div style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 3 }}>End-to-end fintech fraud scenarios, each producing a full case file</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 22 }}>
        {SCENARIOS.map(({ id, label, Icon, desc }) => (
          <button key={id} onClick={() => run(id)} disabled={loading}
            style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "13px 15px", borderRadius: 4, cursor: "pointer",
              background: active === id ? "var(--paper-2)" : "var(--card)",
              border: `1px solid ${active === id ? "var(--ink-faint)" : "var(--rule-bold)"}`,
              borderLeft: active === id ? "4px solid var(--ink)" : "4px solid var(--rule-bold)",
              transition: "background 0.15s, border-color 0.15s", textAlign: "left",
            }}>
            <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
              <Icon size={17} strokeWidth={1.75} color="var(--ink-soft)" />
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>{label}</div>
                <div style={{ fontSize: 11, color: "var(--ink-faint)" }}>{desc}</div>
              </div>
            </div>
            {loading && active === id
              ? <Loader size={14} color="var(--ink-soft)" className="animate-spin" />
              : <Play size={13} color="var(--ink-faint)" />}
          </button>
        ))}
      </div>

      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="font-display" style={{ fontSize: 15, color: "var(--ink)" }}>{result.scenario_name}</div>

          {result.steps?.map(step => (
            <div key={step.step} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "10px 12px", background: "var(--card)", borderRadius: 4, border: "1px solid var(--rule-bold)" }}>
              <div style={{ marginTop: 1 }}>{STATUS_ICONS[step.status] || STATUS_ICONS.info}</div>
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: "var(--ink)", marginBottom: 2 }}>Step {step.step}, {step.name}</div>
                <div style={{ fontSize: 11.5, color: "var(--ink-soft)" }}>{step.result}</div>
              </div>
            </div>
          ))}

          <div className="case-tab" style={{ borderRadius: 4, padding: "12px 14px", borderLeftColor: "var(--stamp-rust)" }}>
            <div className="font-mono" style={{ fontSize: 10.5, fontWeight: 700, color: "var(--stamp-rust)", marginBottom: 4, letterSpacing: "0.04em", textTransform: "uppercase" }}>Verdict</div>
            <div style={{ fontSize: 12.5, color: "var(--ink)" }}>{result.final_verdict}</div>
          </div>

          {result.case_output && (
            <div className="case-tab" style={{ borderRadius: 4, padding: "13px 15px" }}>
              <div style={{ fontSize: 10.5, color: "var(--ink-faint)", marginBottom: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Case file</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 11 }}>
                <div>
                  <div style={{ fontSize: 10, color: "var(--ink-faint)" }}>Risk score</div>
                  <div className="font-mono" style={{ fontWeight: 700, fontSize: 19, color: RISK_COLORS[result.case_output.risk_level] }}>
                    {result.case_output.risk_score}/100
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: "var(--ink-faint)" }}>Fraud probability</div>
                  <div className="font-mono" style={{ fontWeight: 700, fontSize: 19, color: RISK_COLORS[result.case_output.risk_level] }}>
                    {(result.case_output.posterior_fraud_probability * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
              {result.case_output.top_3_signals?.map(sig => (
                <div key={sig.name} style={{ fontSize: 11, padding: "5px 0", borderTop: "1px solid var(--rule)", color: "var(--ink-soft)" }}>
                  #{sig.rank} <span className="font-mono" style={{ color: "var(--ink)" }}>{sig.name}</span>, {sig.description.slice(0, 60)}
                </div>
              ))}
              <div className="font-mono" style={{ fontSize: 9.5, marginTop: 9, color: "var(--ink-faint)" }}>
                audit {result.case_output.audit_log_id?.slice(0, 12)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
