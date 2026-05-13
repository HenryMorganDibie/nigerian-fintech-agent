import { useState } from "react";
import { Shield, TrendingUp, Headphones, Cpu, ChevronDown, Zap } from "lucide-react";

const PROVIDERS = [
  { id: "openai",    label: "GPT-4o",   color: "#10B981" },
  { id: "anthropic", label: "Claude",   color: "#F59E0B" },
  { id: "google",    label: "Gemini",   color: "#3B82F6" },
  { id: "groq",      label: "Groq",     color: "#8B5CF6" },
];

const LANG_LABELS = {
  english: "🇳🇬 EN",
  pidgin:  "🇳🇬 Pidgin",
  yoruba:  "🇳🇬 Yoruba",
  hausa:   "🇳🇬 Hausa",
  igbo:    "🇳🇬 Igbo",
};

const QUICK_PROMPTS = [
  { icon: Shield,      label: "SIM Swap Alert",    text: "A customer made a ₦85,000 USSD transfer at 3am, 12 hours after their SIM was replaced. Analyze this." },
  { icon: Shield,      label: "Structuring Check", text: "Three transfers of ₦490,000 each to different accounts in 2 hours from one customer. Is this structuring?" },
  { icon: Headphones,  label: "Loan Eligibility",  text: "Customer earns ₦220,000/month, bureau score 610, Tier 2 account, wants ₦300,000 for 6 months." },
  { icon: TrendingUp,  label: "Spending Insight",  text: "Customer spent ₦45k food, ₦18k transport, ₦12k airtime, ₦8k data, ₦60k transfers in 30 days, earned ₦200k." },
  { icon: Headphones,  label: "CBN KYC Tiers",     text: "What are the CBN KYC tier limits and what does a customer need to upgrade from Tier 1 to Tier 2?" },
  { icon: Zap,         label: "Pidgin Query",       text: "Customer write say: 'Abeg, dem chop my ₦50,000 twice. E happen sharp sharp this morning. Wetin I go do?'" },
];

export function Sidebar({ provider, setProvider, language, onPrompt }) {
  const [open, setOpen] = useState(false);
  const current = PROVIDERS.find(p => p.id === provider) || PROVIDERS[0];

  return (
    <aside style={{ background: "var(--ink-2)", borderRight: "1px solid var(--border)", width: 240, display: "flex", flexDirection: "column", flexShrink: 0 }}>
      {/* Logo */}
      <div style={{ padding: "20px 16px 16px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--jade-dim)", border: "1px solid #00E67650", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Shield size={15} color="var(--jade)" />
          </div>
          <div>
            <div style={{ fontFamily: "Syne", fontWeight: 700, fontSize: 16, color: "var(--white)", letterSpacing: "-0.3px" }}>NaijaFinAI</div>
            <div style={{ fontSize: 10, color: "var(--muted)" }}>v2.0 · Nigeria-native</div>
          </div>
        </div>
        {/* Language badge */}
        <div style={{ marginTop: 8, display: "inline-flex", alignItems: "center", gap: 4, fontSize: 10, color: "var(--jade)", background: "var(--jade-dim)", border: "1px solid #00E67630", borderRadius: 4, padding: "2px 8px" }}>
          {LANG_LABELS[language] || "🇳🇬 EN"} detected
        </div>
      </div>

      {/* Provider picker */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>
          <Cpu size={10} /> LLM Provider
        </div>
        <div style={{ position: "relative" }}>
          <button
            onClick={() => setOpen(o => !o)}
            style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--ink-3)", border: "1px solid var(--border-bright)", borderRadius: 8, padding: "7px 10px", cursor: "pointer", color: current.color, fontSize: 12, fontWeight: 600 }}
          >
            <span>● {current.label}</span>
            <ChevronDown size={12} style={{ color: "var(--muted)" }} />
          </button>
          {open && (
            <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, background: "var(--ink-3)", border: "1px solid var(--border-bright)", borderRadius: 8, overflow: "hidden", zIndex: 10 }}>
              {PROVIDERS.map(p => (
                <button key={p.id} onClick={() => { setProvider(p.id); setOpen(false); }}
                  style={{ width: "100%", textAlign: "left", padding: "8px 12px", fontSize: 12, fontWeight: 500, cursor: "pointer", background: p.id === provider ? "var(--jade-dim)" : "transparent", color: p.id === provider ? "var(--jade)" : "var(--text)", border: "none" }}>
                  {p.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick prompts */}
      <div style={{ padding: "12px 16px", flex: 1, overflowY: "auto" }}>
        <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>Quick Scenarios</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {QUICK_PROMPTS.map(({ icon: Icon, label, text }) => (
            <button key={label} onClick={() => onPrompt(text)}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", borderRadius: 8, background: "transparent", border: "1px solid transparent", cursor: "pointer", textAlign: "left", fontSize: 11, color: "var(--muted)", transition: "all 0.15s", fontFamily: "DM Sans" }}
              onMouseEnter={e => { e.currentTarget.style.background = "var(--jade-dim)"; e.currentTarget.style.borderColor = "#00E67630"; e.currentTarget.style.color = "var(--text)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "transparent"; e.currentTarget.style.color = "var(--muted)"; }}>
              <Icon size={11} style={{ flexShrink: 0 }} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", fontSize: 10, color: "var(--muted)" }}>
        CBN · NFIU · NDPA · EFCC aware
        <div style={{ marginTop: 2, fontFamily: "IBM Plex Mono" }}>Audit logs: NDPA §40 compliant</div>
      </div>
    </aside>
  );
}
