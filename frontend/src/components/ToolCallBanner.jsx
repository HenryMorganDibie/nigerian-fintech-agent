import { Workflow } from "lucide-react";

const TOOL_LABELS = {
  nigerian_fraud_score:    "fraud engine",
  cbn_loan_eligibility:    "loan checker",
  naija_spending_insights: "spending analyser",
};

export function ToolCallBanner({ tools }) {
  if (!tools?.length) return null;
  return (
    <div className="no-rule" style={{ padding: "6px 20px", background: "var(--stamp-green-wash)", borderBottom: "1px solid var(--stamp-green)", display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, color: "var(--stamp-green)" }}>
      <Workflow size={12} strokeWidth={2} />
      <span style={{ fontWeight: 500 }}>Consulted:</span>
      {tools.map(t => (
        <span key={t} className="font-mono" style={{ background: "var(--card)", border: "1px solid var(--stamp-green)", borderRadius: 3, padding: "1px 7px" }}>
          {TOOL_LABELS[t] || t}
        </span>
      ))}
    </div>
  );
}
