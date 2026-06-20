import { useState } from "react";
import { ShieldHalf, TrendingUp, Headset, Cpu, ChevronDown, Zap } from "lucide-react";

const PROVIDERS = [
  { id: "openai",    label: "GPT-4o",   color: "#3B6E55" },
  { id: "anthropic", label: "Claude",   color: "#9C6B12" },
  { id: "google",    label: "Gemini",   color: "#3B5A8A" },
  { id: "groq",      label: "Groq",     color: "#1F6E43" },
];

const LANG_LABELS = {
  english: "English",
  pidgin:  "Pidgin",
  yoruba:  "Yoruba",
  hausa:   "Hausa",
  igbo:    "Igbo",
};

const QUICK_PROMPTS = [
  { icon: ShieldHalf,  label: "SIM swap alert",    text: "A customer made a ₦85,000 USSD transfer at 3am, 12 hours after their SIM was replaced. Analyze this." },
  { icon: ShieldHalf,  label: "Structuring check", text: "Three transfers of ₦490,000 each to different accounts in 2 hours from one customer. Is this structuring?" },
  { icon: Headset,     label: "Loan eligibility",  text: "Customer earns ₦220,000/month, bureau score 610, Tier 2 account, wants ₦300,000 for 6 months." },
  { icon: TrendingUp,  label: "Spending insight",  text: "Customer spent ₦45k food, ₦18k transport, ₦12k airtime, ₦8k data, ₦60k transfers in 30 days, earned ₦200k." },
  { icon: Headset,     label: "CBN KYC tiers",     text: "What are the CBN KYC tier limits and what does a customer need to upgrade from Tier 1 to Tier 2?" },
  { icon: Zap,         label: "Pidgin query",      text: "Customer write say: 'Abeg, dem chop my ₦50,000 twice. E happen sharp sharp this morning. Wetin I go do?'" },
];

export function Sidebar({ provider, setProvider, language, onPrompt }) {
  const [open, setOpen] = useState(false);
  const current = PROVIDERS.find(p => p.id === provider) || PROVIDERS[0];

  return (
    <aside className="no-rule" style={{ background: "var(--paper-2)", borderRight: "1px solid var(--rule-bold)", width: 250, display: "flex", flexDirection: "column", flexShrink: 0 }}>

      {/* Masthead */}
      <div style={{ padding: "18px 16px 14px", borderBottom: "1px solid var(--rule-bold)" }}>
        <div className="font-display" style={{ fontSize: 19, color: "var(--ink)", lineHeight: 1.1 }}>NaijaFinAI</div>
        <div className="font-mono" style={{ fontSize: 10, color: "var(--ink-faint)", marginTop: 3, letterSpacing: "0.02em" }}>
          fraud intelligence · v3
        </div>
        <div style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--stamp-green)", display: "inline-block" }} />
          <span style={{ fontSize: 11, color: "var(--ink-soft)" }}>
            reading in <strong style={{ color: "var(--ink)" }}>{LANG_LABELS[language] || "English"}</strong>
          </span>
        </div>
      </div>

      {/* Provider picker */}
      <div style={{ padding: "13px 16px", borderBottom: "1px solid var(--rule-bold)" }}>
        <div style={{ fontSize: 10, color: "var(--ink-faint)", marginBottom: 7, display: "flex", alignItems: "center", gap: 5, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>
          <Cpu size={11} /> Model
        </div>
        <div style={{ position: "relative" }}>
          <button
            onClick={() => setOpen(o => !o)}
            style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--card)", border: "1px solid var(--rule-bold)", borderRadius: 4, padding: "7px 10px", cursor: "pointer", color: current.color, fontSize: 12.5, fontWeight: 600, fontFamily: "Inter" }}
          >
            <span>{current.label}</span>
            <ChevronDown size={13} style={{ color: "var(--ink-faint)" }} />
          </button>
          {open && (
            <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, background: "var(--card)", border: "1px solid var(--rule-bold)", borderRadius: 4, overflow: "hidden", zIndex: 10 }}>
              {PROVIDERS.map(p => (
                <button key={p.id} onClick={() => { setProvider(p.id); setOpen(false); }}
                  style={{ width: "100%", textAlign: "left", padding: "8px 12px", fontSize: 12.5, fontWeight: 500, cursor: "pointer", background: p.id === provider ? "var(--paper-2)" : "transparent", color: p.id === provider ? p.color : "var(--ink-soft)", border: "none", fontFamily: "Inter" }}>
                  {p.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick scenarios */}
      <div style={{ padding: "13px 16px", flex: 1, overflowY: "auto" }}>
        <div style={{ fontSize: 10, color: "var(--ink-faint)", marginBottom: 9, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>Sample cases</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {QUICK_PROMPTS.map(({ icon: Icon, label, text }) => (
            <button key={label} onClick={() => onPrompt(text)}
              style={{ display: "flex", alignItems: "center", gap: 9, padding: "8px 9px", borderRadius: 4, background: "transparent", border: "1px solid transparent", cursor: "pointer", textAlign: "left", fontSize: 12, color: "var(--ink-soft)", transition: "background 0.12s, border-color 0.12s", fontFamily: "Inter" }}
              onMouseEnter={e => { e.currentTarget.style.background = "var(--card)"; e.currentTarget.style.borderColor = "var(--rule-bold)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "transparent"; }}>
              <Icon size={13} strokeWidth={1.75} style={{ flexShrink: 0, color: "var(--ink-faint)" }} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div style={{ padding: "12px 16px", borderTop: "1px solid var(--rule-bold)" }}>
        <div style={{ fontSize: 10.5, color: "var(--ink-soft)" }}>CBN · NFIU · NDPA · EFCC</div>
        <div className="font-mono" style={{ marginTop: 3, fontSize: 9.5, color: "var(--ink-faint)" }}>audit log — NDPA §40</div>
      </div>
    </aside>
  );
}
