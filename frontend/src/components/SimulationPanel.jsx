import { useState } from "react";
import { Zap, Shield, AlertTriangle, CheckCircle, Loader, ChevronDown, ChevronUp } from "lucide-react";

const BASE = import.meta.env.VITE_API_URL || "/api";

const SCENARIOS = [
  { id: "sim_swap_attack",      emoji: "📱", label: "SIM Swap Attack",         color: "#FF4444" },
  { id: "mule_chain_attack",    emoji: "🏪", label: "Agent Mule Chain",         color: "#FF8800" },
  { id: "structuring_attack",   emoji: "💸", label: "Structuring / Smurfing",   color: "#FF4444" },
  { id: "first_party_loan_fraud", emoji: "💰", label: "First-Party Loan Fraud", color: "#FF8800" },
  { id: "circular_flow_attack", emoji: "🔄", label: "Circular Flow / Layering", color: "#FF4444" },
  { id: "account_takeover",     emoji: "🔓", label: "Account Takeover",         color: "#FF8800" },
];

const RISK_COLORS = { low: "var(--jade)", medium: "var(--gold)", high: "#FF8800", critical: "#FF4444" };
const RISK_EMOJI  = { low: "✅", medium: "🟡", high: "🔴", critical: "🚨" };

function ReasonCodeCard({ code, index }) {
  return (
    <div style={{ display: "flex", gap: 10, padding: "10px 12px", background: "var(--ink-3)", borderRadius: 8, marginBottom: 6, alignItems: "flex-start" }}>
      <div style={{ flexShrink: 0, width: 22, height: 22, borderRadius: "50%", background: "var(--jade-dim)", border: "1px solid #00E67640", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: "var(--jade)" }}>{index + 1}</span>
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--white)", marginBottom: 2 }}>{code.label}</div>
        <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 4 }}>{code.context}</div>
        {code.cbn_reference && (
          <div style={{ fontSize: 9, fontFamily: "IBM Plex Mono", color: "var(--jade)", opacity: 0.7 }}>{code.cbn_reference}</div>
        )}
      </div>
      <div style={{ flexShrink: 0, fontSize: 10, fontFamily: "IBM Plex Mono", color: "#FF8800", background: "#FF880015", border: "1px solid #FF880030", borderRadius: 4, padding: "1px 6px" }}>
        +{code.score_contribution}
      </div>
    </div>
  );
}

export function SimulationPanel() {
  const [running, setRunning] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const runScenario = async (id) => {
    setRunning(id);
    setResult(null);
    setError(null);
    try {
      const r = await fetch(`${BASE}/simulate/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: id }),
      });
      const data = await r.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(null);
    }
  };

  const explain = result?.explainability;
  const riskLevel = explain?.risk_level;

  return (
    <div style={{ padding: 20, overflowY: "auto", height: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 16, color: "var(--white)" }}>
          Fraud Simulation Sandbox
        </div>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>
          Trigger real Nigerian fraud attack patterns — see NaijaFinAI detect them live
        </div>
      </div>

      {/* Scenario buttons */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 20 }}>
        {SCENARIOS.map(s => (
          <button key={s.id} onClick={() => runScenario(s.id)} disabled={!!running}
            style={{
              display: "flex", alignItems: "center", gap: 10, padding: "10px 12px",
              borderRadius: 10, cursor: "pointer", textAlign: "left", transition: "all 0.15s",
              background: running === s.id ? `${s.color}15` : "var(--ink-2)",
              border: `1px solid ${running === s.id ? s.color + "50" : "var(--border)"}`,
            }}>
            <span style={{ fontSize: 18 }}>{s.emoji}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--white)" }}>{s.label}</div>
            </div>
            {running === s.id
              ? <Loader size={13} color="var(--jade)" style={{ animation: "spin 1s linear infinite" }} />
              : <Zap size={12} color="var(--muted)" />}
          </button>
        ))}
      </div>

      {/* Result */}
      {error && (
        <div style={{ padding: 12, background: "#FF444415", border: "1px solid #FF444430", borderRadius: 10, color: "var(--ember)", fontSize: 12 }}>
          {error}
        </div>
      )}

      {result && explain && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Detection banner */}
          <div style={{ padding: "12px 16px", borderRadius: 10, border: `1px solid ${RISK_COLORS[riskLevel]}40`, background: `${RISK_COLORS[riskLevel]}10`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: RISK_COLORS[riskLevel] }}>
                {RISK_EMOJI[riskLevel]} {result.scenario_name} — {riskLevel?.toUpperCase()} RISK DETECTED
              </div>
              <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 3 }}>
                {result.detection_correct ? "✅ Correct detection" : "❌ Expected: " + result.expected_risk} · Audit: {result.audit_log_id}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 700, fontSize: 24, color: RISK_COLORS[riskLevel] }}>
                {explain.risk_score}
              </div>
              <div style={{ fontSize: 9, color: "var(--muted)" }}>/ 100</div>
            </div>
          </div>

          {/* Summary */}
          <div style={{ fontSize: 12, color: "var(--text)", padding: "10px 14px", background: "var(--ink-2)", borderRadius: 8, border: "1px solid var(--border)" }}>
            {explain.summary}
          </div>

          {/* Attack story */}
          <div style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px" }}>
            <div style={{ fontSize: 10, color: "var(--muted)", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>Attack Timeline</div>
            {result.attack_story?.map((step, i) => (
              <div key={i} style={{ fontSize: 11, color: "var(--text)", padding: "4px 0", borderBottom: i < result.attack_story.length - 1 ? "1px solid var(--border)" : "none" }}>
                {step}
              </div>
            ))}
          </div>

          {/* Reason codes — explainability */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--white)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
              <Shield size={12} color="var(--jade)" />
              Why this was flagged — Top {explain.top_reason_codes?.length} contributors
            </div>
            {explain.top_reason_codes?.map((code, i) => (
              <ReasonCodeCard key={i} code={code} index={i} />
            ))}
          </div>

          {/* Recommended action */}
          <div style={{ padding: "10px 14px", background: "#FF444410", border: "1px solid #FF444430", borderRadius: 8 }}>
            <div style={{ fontSize: 10, color: "#FF4444", fontWeight: 600, marginBottom: 4 }}>RECOMMENDED ACTION</div>
            <div style={{ fontSize: 12, color: "var(--text)" }}>{explain.recommended_action}</div>
            <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 4 }}>Escalation: {explain.escalation_path}</div>
          </div>

          {/* Regulatory filings */}
          {result.regulatory_filings?.length > 0 && (
            <div style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px" }}>
              <div style={{ fontSize: 10, color: "var(--gold)", fontWeight: 600, marginBottom: 8 }}>REGULATORY FILINGS REQUIRED</div>
              {result.regulatory_filings.map((f, i) => (
                <div key={i} style={{ fontSize: 11, color: "var(--text)", marginBottom: 4 }}>
                  <span style={{ color: "var(--gold)", fontFamily: "IBM Plex Mono" }}>{f.type}</span> — {f.deadline} ({f.urgency_hours}h)
                </div>
              ))}
            </div>
          )}

          {/* Layer breakdown toggle */}
          <button onClick={() => setExpanded(e => !e)}
            style={{ display: "flex", alignItems: "center", gap: 6, background: "transparent", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px", cursor: "pointer", color: "var(--muted)", fontSize: 11 }}>
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? "Hide" : "Show"} layer breakdown
          </button>

          {expanded && result.layer_breakdown && (
            <div style={{ background: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px" }}>
              <div style={{ fontSize: 10, color: "var(--muted)", fontWeight: 600, marginBottom: 10 }}>SCORING BREAKDOWN</div>
              {Object.entries(result.layer_breakdown).filter(([k]) => k !== "composite" && k !== "hard_override").map(([layer, info]) => (
                <div key={layer} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <div style={{ fontSize: 10, color: "var(--muted)", width: 100 }}>{layer} ({info.weight})</div>
                  <div style={{ flex: 1, background: "var(--border)", borderRadius: 4, height: 6 }}>
                    <div style={{ width: `${info.score}%`, background: "var(--jade)", height: "100%", borderRadius: 4 }} />
                  </div>
                  <div style={{ fontSize: 10, fontFamily: "IBM Plex Mono", color: "var(--white)", width: 30 }}>{info.score}</div>
                </div>
              ))}
              <div style={{ fontSize: 10, color: "var(--jade)", fontFamily: "IBM Plex Mono", marginTop: 6 }}>
                ⚡ {result.note}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
