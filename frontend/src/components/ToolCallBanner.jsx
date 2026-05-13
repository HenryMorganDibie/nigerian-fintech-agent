import { Zap } from "lucide-react";

const TOOL_LABELS = {
  nigerian_fraud_score: "🔍 Nigerian Fraud Engine",
  cbn_loan_eligibility: "📋 CBN Loan Checker",
  naija_spending_insights: "📊 Spending Analyser",
};

export function ToolCallBanner({ tools }) {
  if (!tools?.length) return null;
  return (
    <div style={{ padding: "6px 20px", background: "var(--jade-dim)", borderBottom: "1px solid #00E67625", display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--jade)" }}>
      <Zap size={11} />
      <span style={{ fontWeight: 500 }}>Tools invoked:</span>
      {tools.map(t => (
        <span key={t} style={{ fontFamily: "IBM Plex Mono", background: "#00E67610", border: "1px solid #00E67630", borderRadius: 4, padding: "1px 6px" }}>
          {TOOL_LABELS[t] || t}
        </span>
      ))}
    </div>
  );
}
