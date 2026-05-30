# 🇳🇬 NaijaFinAI — Production AI Agent for Nigerian Fintechs

> **The only AI fraud intelligence platform built natively for the Nigerian payments ecosystem.**
> Not a global tool with a Nigerian skin — built from the ground up for CBN regulations, NFIU filing deadlines, Nigerian fraud typologies, and all five Nigerian languages.

[![Live Demo](https://img.shields.io/badge/Live_Demo-GitHub_Pages-00E676?style=flat-square&logo=github)](https://henrymorgandibie.github.io/nigerian-fintech-agent)
[![Backend](https://img.shields.io/badge/Backend-Railway-8B5CF6?style=flat-square)](https://nigerian-fintech-agent-production.up.railway.app/docs)
[![Groq](https://img.shields.io/badge/LLM-Groq_Free_+_Fallback-00E676?style=flat-square)](https://console.groq.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

---

## What Makes This Different

| Capability | Generic AI Tools | NaijaFinAI v3 |
|---|---|---|
| Fraud scoring | Additive rules | **4-layer: Bayesian + Behavioral + Graph + Hard Overrides** |
| Behavioral memory | None | Feature store — per-user velocity, device history, beneficiary graph |
| Graph fraud detection | None | Shared devices, circular flows, mule cluster detection |
| Nigerian signals | Generic | 13 CBN/EFCC/NFIU-cited patterns with calibrated likelihood ratios |
| Event ingestion | Batch only | Async event stream (asyncio.Queue → Kafka-ready interface) |
| Languages | English only | Pidgin + Yoruba + Hausa + Igbo + Nigerian English |
| Voice input | None | Groq Whisper (free, all Nigerian languages) |
| LLM reliability | Single model | **Dual Groq — auto-fallback to llama-3.1-8b-instant on rate limit** |
| Compliance | None | NDPA 2023 §40 audit logs, PII scrubbing, NFIU STR/CTR tracker |
| Feedback loop | None | Analyst outcomes → signal accuracy + drift monitor updates |
| Drift monitoring | None | PSI-based drift, fraud rate spike alerts, signal decay detection |
| A/B testing | None | **3-variant experiment router** — rules vs Bayesian vs full pipeline |
| Load testing | None | Locust scripts — realistic Nigerian tx volume + salary spike |
| Monitoring dashboard | None | Live PSI score, false positive rate, drift alerts in frontend |

---

## Architecture — 7 Layers + Full Stack

```
nigerian-fintech-agent/
│
├── backend/
│   └── app/
│       ├── core/
│       │   ├── event_stream.py          Layer 1 — Async event ingestion (Kafka-ready)
│       │   ├── feature_store.py         Layer 2 — Behavioral memory per user (Redis-ready)
│       │   ├── nigeria_intelligence.py  Layer 3a — 13 Nigerian heuristic fraud signals
│       │   ├── bayesian_scorer.py       Layer 3b — Bayesian log-odds risk scoring
│       │   ├── fraud_graph.py           Layer 4 — Shared device / mule / circular flow
│       │   ├── decision_engine.py       Layer 5 — Multi-layer weighted decision engine
│       │   │                                       Layer 6 — Analyst feedback loop
│       │   │                                       Layer 7 — PSI drift monitor
│       │   ├── compliance.py            NDPA audit logs + NFIU/EFCC filing tracker
│       │   ├── language.py              Pidgin/Yoruba/Hausa/Igbo detection + glossary
│       │   ├── llm_factory.py           Groq primary + auto-fallback (llama-3.1-8b-instant)
│       │   ├── workflows.py             3 one-click fintech scenario demos
│       │   ├── evaluation.py            40-sample synthetic Nigerian fraud eval harness
│       │   └── config.py                Groq-first, dual model, Redis URL, CORS validator
│       │
│       └── routers/
│           ├── fraud.py                 POST /api/fraud/analyze    (4-layer scoring)
│           │                            POST /api/fraud/feedback   (analyst loop)
│           │                            GET  /api/fraud/drift      (drift report)
│           │                            POST /api/fraud/events/publish
│           │                            GET  /api/fraud/events/stats
│           ├── ab_testing.py            POST /api/ab/fraud/analyze (variant routing)
│           │                            GET  /api/ab/experiments   (list experiments)
│           │                            GET  /api/ab/results/{id}  (compare variants)
│           │                            POST /api/ab/feedback      (analyst outcome)
│           ├── chat.py                  POST /api/chat             (SSE streaming)
│           ├── loans.py                 POST /api/loans/eligibility
│           ├── transactions.py          POST /api/transactions/insights
│           ├── eval.py                  POST /api/eval/run
│           ├── workflows.py             POST /api/workflows/run
│           └── media.py                 POST /api/media/voice + /upload
│
├── frontend/                            React 18 + Vite + Tailwind
│   └── src/
│       ├── App.jsx                      5-tab layout
│       └── components/
│           ├── ChatMessage.jsx          Risk-coloured bubbles + audit IDs
│           ├── Sidebar.jsx              v3.0 · Provider selector · Quick scenarios
│           ├── EvalDashboard.jsx        Precision / recall / confusion matrix
│           ├── WorkflowDemo.jsx         One-click scenario runner
│           ├── MediaInput.jsx           Voice recorder + file upload
│           ├── MonitoringDashboard.jsx  PSI drift · fraud rate · FP tracking · feedback
│           └── ToolCallBanner.jsx       Live tool invocation display
│
└── tests/
    └── locustfile.py                    Load testing — 50 users, salary spike scenario
```

---

## Fraud Scoring Formula

```
Final Risk Score =
  Bayesian Signal Score      × 0.45   ← 13 CBN-cited signals, calibrated LRs
+ Behavioral Deviation Score × 0.30   ← user's own history vs current tx
+ Graph Risk Score           × 0.25   ← network-level fraud patterns
+ Hard Override Rules                 ← forces CRITICAL regardless of score
```

### Hard Override Rules
| Rule | Condition | Action |
|---|---|---|
| `BVN_MISMATCH_HIGH_VALUE` | NIN-BVN mismatch + amount > ₦50k | Block + STR |
| `SIM_SWAP_RAPID_TRANSFER` | SIM swap signal on USSD | Freeze + BVN re-verify |
| `CIRCULAR_FLOW_ANY_AMOUNT` | Round-trip > ₦100k | Freeze both ends + STR |
| `MULE_CLUSTER_RECIPIENT` | Mule cluster pattern | Suspend + EFCC referral |
| `STRUCTURING_REPEAT` | Structuring + split together | STR + CTR immediately |

### Analyst Decision Tiers
| Score | Decision | Action |
|---|---|---|
| 0–25 | Auto Approve | ✅ Transaction proceeds |
| 26–50 | Review Queue | 🟡 Analyst reviews within 2 hours |
| 51–75 | Escalate | 🔴 Hold + compliance team |
| 76–100 | Freeze + STR | 🚨 Block + NFIU filing within 24h |

---

## A/B Testing — 3 Variants

| Variant | Strategy | Traffic |
|---|---|---|
| A | Rule-based only (legacy baseline) | 20% |
| B | Bayesian scorer only | 30% |
| C | Full 4-layer pipeline (current default) | 50% |

```bash
# Test a specific variant
POST /api/ab/fraud/analyze
{ "transaction": {...}, "force_variant": "A" }

# Compare results across variants
GET /api/ab/results/fraud_scoring_strategy
```

---

## Groq Dual-Model Setup (Both Free)

```
Primary:  llama-3.3-70b-versatile   ← best quality, used by default
Fallback: llama-3.1-8b-instant      ← auto-used on HTTP 429 rate limit
```

Set in Railway environment variables:
```
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant
DEFAULT_LLM_PROVIDER=groq
```

---

## API Endpoints — Full Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Multi-turn streaming agent (all 5 Nigerian languages) |
| `POST` | `/api/fraud/analyze` | 4-layer fraud analysis → full case output |
| `POST` | `/api/fraud/feedback` | Analyst outcome → feedback loop + drift monitor |
| `GET`  | `/api/fraud/drift` | PSI drift report + fraud rate change detection |
| `POST` | `/api/fraud/events/publish` | Publish transaction to async event stream |
| `GET`  | `/api/fraud/events/stats` | Event queue depth + processing stats |
| `POST` | `/api/ab/fraud/analyze` | A/B variant routing for fraud scoring |
| `GET`  | `/api/ab/experiments` | List experiments + sample counts per variant |
| `GET`  | `/api/ab/results/{id}` | Compare avg scores + risk distributions per variant |
| `POST` | `/api/ab/feedback` | Record analyst outcome for A/B run |
| `POST` | `/api/loans/eligibility` | CBN-compliant loan assessment |
| `POST` | `/api/transactions/insights` | Nigerian spending analytics |
| `POST` | `/api/eval/run` | Precision/recall/F1 on 40-sample labelled dataset |
| `GET`  | `/api/eval/dataset` | View the labelled fraud dataset |
| `GET`  | `/api/workflows/scenarios` | List demo scenarios |
| `POST` | `/api/workflows/run` | Run end-to-end scenario |
| `POST` | `/api/media/voice` | Groq Whisper transcription (all Nigerian languages) |
| `POST` | `/api/media/upload` | PDF/CSV/image fraud signal scan |
| `GET`  | `/api/providers` | List configured LLM providers |
| `GET`  | `/api/health` | Health check |

Interactive docs: `https://nigerian-fintech-agent-production.up.railway.app/docs`

---

## Frontend — 5 Tabs

| Tab | Description |
|---|---|
| **Chat** | Multi-turn agent — auto-detects Pidgin, Yoruba, Hausa, Igbo, English. Asks for data before scoring. |
| **Workflows** | One-click: Loan Fraud Check, Agent Wallet Monitor, Chargeback Investigation |
| **Eval** | Live precision/recall/F1 + confusion matrix on 40-sample Nigerian fraud dataset |
| **Voice & Files** | Groq Whisper transcription + PDF/CSV/image fraud scan |
| **Monitor** | PSI drift score, fraud rate alerts, false positive tracking, analyst feedback submission |

---

## Nigerian Fraud Signals — 13 Signals

| Signal | Likelihood Ratio | Severity | Regulation |
|---|---|---|---|
| `NIN_BVN_MISMATCH` | 45× | Critical | CBN BPS/DIR/GEN/CIR/03/002 |
| `SIM_SWAP_HIGH_VALUE_USSD` | 22× | Critical | CBN CPD/DIR/GEN/LAB/13/006 |
| `ROUND_TRIP_TRANSFER` | 19.6× | Critical | CBN AML/CFT 2022 §3.1 |
| `CBN_STRUCTURING` | 18.5× | Critical | CBN AML/CFT 2022 §4.3 |
| `AGENT_VELOCITY_SPIKE` | 14.8× | High | CBN Agent Banking 2019 §6.3 |
| `SPLIT_TRANSACTION_PATTERN` | 13.1× | High | CBN AML/CFT 2022 §4.3 |
| `FIRST_PARTY_FRAUD_LOAN` | 12.4× | High | CBN MFB Guidelines §8.4 |
| `UNVERIFIED_BVN_LARGE_TRANSFER` | 11.2× | High | CBN BPS/DIR/2020/004 |
| `DEVICE_CHANGE_BEFORE_TRANSFER` | 9.3× | High | CBN e-Banking 2020 §7 |
| `SCAM_KEYWORDS_NARRATION` | 8.7× | High | EFCC Advisory 2024 |
| `USSD_AFTER_HOURS` | 7.2× | High | CBN Fraud Desk Advisory 2023-07 |
| `POS_ABOVE_CBN_LIMIT` | 4.1× | Medium | CBN POS Guidelines 2023 |
| `WEEKEND_MIDNIGHT_SPIKE` | 3.8× | Medium | CBN Fraud Trend Q3 2024 |

---

## Load Testing

```bash
pip install locust
locust -f tests/locustfile.py \
  --host=https://nigerian-fintech-agent-production.up.railway.app \
  --users 50 --spawn-rate 5 --run-time 2m
# Open http://localhost:8089
```

Two scenarios: `NaijaFintechUser` (realistic daily volume) and `SalaryDisbursementSpike` (end-of-month volume spike).

---

## Compliance Layer

| Requirement | Implementation |
|---|---|
| NDPA 2023 §40 — Automated decision audit | UUID audit log on every AI decision |
| NDPA 2023 §24 — Data minimisation | PII scrubbed before any LLM API call |
| CBN AML/CFT 2022 §10 — Record retention | 5-year expiry stamped at creation |
| NFIU STR — 24h filing deadline | Auto-triggered on high/critical risk |
| NFIU CTR — 7-day for >₦5M | Auto-triggered on large transactions |
| EFCC referral — Critical + >₦5M | Escalation path in every critical case |

---

## Quickstart (5 minutes, free)

```bash
git clone https://github.com/HenryMorganDibie/nigerian-fintech-agent.git
cd nigerian-fintech-agent
cp .env.example .env
# Add GROQ_API_KEY=gsk_... (free at console.groq.com)

cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

---

## Production Upgrade Paths

| Component | Current | Production Upgrade |
|---|---|---|
| Event stream | asyncio.Queue | kafka-python or redis streams |
| Feature store | In-memory dict | Redis (set REDIS_URL env var) |
| Fraud graph | In-memory | Neo4j AuraDB |
| Audit logs | In-memory | PostgreSQL append-only table |
| Model retraining | Manual | MLflow + labelled feedback pipeline |
| Monitoring | In-app dashboard | Grafana + Prometheus |

---

## Author

**Henry Dibie** — ML/Data Engineer
[LinkedIn](https://linkedin.com/in/kinghenrymorgan) · [GitHub](https://github.com/HenryMorganDibie) · [Medium](https://medium.com/@KingHenryMorgan) · [X](https://twitter.com/KingHenryMorgan)

---

## Latest Upgrades (v3.1)

### Tool Schema Fix
All agent tools now have type coercion (`_bool`, `_int`, `_float` helpers) and safe defaults. The LLM no longer crashes when it passes `"unknown"` instead of a typed value. Every parameter is optional with sensible fallbacks.

### Multi-Provider Fallback Chain + Circuit Breaker
```
1. Groq llama-3.3-70b-versatile   (primary)
2. Groq llama-3.1-8b-instant      (Groq fallback — same key)
3. OpenAI GPT-4o                   (if OPENAI_API_KEY set)
4. Anthropic Claude                (if ANTHROPIC_API_KEY set)
5. Rules-only degraded mode        (always works)
```
Circuit breaker trips after 3 consecutive failures, cools down for 10 minutes, auto-resets. Status visible at `GET /api/health`.

### LLM Off Critical Path
Fraud scoring never calls the LLM — Bayesian + behavioral + graph layers are fully deterministic. LLM is only called for narrative explanation, and only when risk is medium or higher (saves ~70% of tokens vs previous version).

### Explainability Engine
Every fraud decision now returns structured reason codes:
```json
{
  "summary": "Transaction scored 84/100 (HIGH) — Primary: SIM swap detected",
  "top_reason_codes": [
    { "rank": 1, "label": "SIM replacement + high-value USSD", "score_contribution": 22, "context": "SIM replaced 5 hours ago", "cbn_reference": "CBN CPD/DIR/GEN/LAB/13/006" },
    { "rank": 2, "label": "New device fingerprint", "score_contribution": 17, "context": "New device 3 hours before transfer" }
  ],
  "confidence": "Very High (>85%)",
  "escalation_path": "Compliance → NFIU STR within 24h"
}
```

### Fraud Simulation Sandbox
6 pre-built Nigerian attack scenarios — test NaijaFinAI live:
- SIM Swap Account Takeover
- Agent Network Mule Chain
- Structuring / Smurfing
- First-Party Loan Fraud
- Circular Flow / Layering
- Account Takeover via Social Engineering

`GET /api/simulate/scenarios` · `POST /api/simulate/run`

### Localized Greeting System
Time-based greeting with Nigerian language support:
- English: "Good morning / afternoon / evening" (always shown)
- Yoruba: "Ẹ káàárọ̀ / Ẹ káàsán / Ẹ káàlẹ́" (additive, when detected)
- Igbo: "Ụtụtụ ọma / Ehihie ọma / Anyasị ọma"
- Hausa: "Ina kwana / Ina wuni / Ina yini"
- Pidgin: "Eku morning / How far / Eku evening"

English is always primary — Nigerian greetings are additive, never replacing.

### Frontend: 6 Tabs
Chat · Workflows · **Simulate** · Eval · Voice & Files · Monitor
