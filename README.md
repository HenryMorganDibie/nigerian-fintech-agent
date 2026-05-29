# 🇳🇬 NaijaFinAI — Production AI Agent for Nigerian Fintechs

> **The only AI fraud intelligence platform built natively for the Nigerian payments ecosystem.**

[![Live Demo](https://img.shields.io/badge/Live_Demo-GitHub_Pages-00E676?style=flat-square&logo=github)](https://henrymorgandibie.github.io/nigerian-fintech-agent)
[![Backend](https://img.shields.io/badge/Backend-Railway-8B5CF6?style=flat-square)](https://nigerian-fintech-agent-production.up.railway.app/docs)
[![Groq](https://img.shields.io/badge/LLM-Groq_Free_+_Fallback-00E676?style=flat-square)](https://console.groq.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

---

## What Makes This Different

| Capability | Generic AI Tools | NaijaFinAI v3 |
|---|---|---|
| Fraud scoring | Additive rules | **4-layer Bayesian + Behavioral + Graph + Override** |
| Behavioral memory | None | Feature store — per-user velocity, device history, beneficiary graph |
| Graph fraud | None | Shared devices, circular flows, mule cluster detection |
| Nigerian signals | Generic | 13 CBN/EFCC/NFIU-cited patterns with likelihood ratios |
| Languages | English only | Pidgin + Yoruba + Hausa + Igbo + Nigerian English |
| Voice input | None | Groq Whisper (free, all Nigerian languages) |
| LLM reliability | Single provider | **Dual Groq models — auto-fallback on rate limit** |
| Compliance | None | NDPA 2023 audit logs, PII scrubbing, NFIU STR/CTR |
| Feedback loop | None | Analyst outcomes → signal weight updates + drift detection |
| Drift monitoring | None | PSI-based drift detection, fraud rate spike alerts |
| Event pipeline | Batch only | Async event stream (asyncio.Queue → Kafka-ready) |

---

## Architecture — 7 Layers

```
nigerian-fintech-agent/
│
├── backend/
│   └── app/
│       ├── core/
│       │   ├── event_stream.py         Layer 1 — Async event ingestion (Kafka-ready)
│       │   ├── feature_store.py        Layer 2 — Behavioral memory (Redis-ready)
│       │   ├── nigeria_intelligence.py Layer 3a — 13 Nigerian heuristic signals
│       │   ├── bayesian_scorer.py      Layer 3b — Bayesian log-odds scoring
│       │   ├── fraud_graph.py          Layer 4 — Shared device / mule / circular flow
│       │   ├── decision_engine.py      Layer 5 — Multi-layer weighted decision
│       │   │                                      + analyst feedback loop (Layer 6)
│       │   │                                      + PSI drift monitor (Layer 7)
│       │   ├── compliance.py           NDPA audit logs + NFIU filing tracker
│       │   ├── language.py             Pidgin/Yoruba/Hausa/Igbo detection
│       │   ├── llm_factory.py          Groq primary + auto-fallback to llama3-70b
│       │   ├── workflows.py            3 one-click fintech scenarios
│       │   ├── evaluation.py           40-sample synthetic eval harness
│       │   └── config.py               Groq-first + dual model + Redis URL
│       ├── routers/
│       │   ├── fraud.py                POST /api/fraud/analyze (4-layer scoring)
│       │   │                           POST /api/fraud/feedback (analyst loop)
│       │   │                           GET  /api/fraud/drift   (drift report)
│       │   │                           POST /api/fraud/events/publish
│       │   ├── chat.py                 POST /api/chat (streaming, all languages)
│       │   ├── loans.py                POST /api/loans/eligibility
│       │   ├── transactions.py         POST /api/transactions/insights
│       │   ├── eval.py                 POST /api/eval/run
│       │   ├── workflows.py            POST /api/workflows/run
│       │   └── media.py                POST /api/media/voice + /upload
│       └── agents/fintech_agent.py     LangChain bind_tools loop + Groq fallback
│
├── frontend/                           React 18 + Vite + 4-tab UI
│   └── src/
│       ├── App.jsx                     Chat / Workflows / Eval / Voice tabs
│       ├── components/
│       │   ├── ChatMessage.jsx         Risk-coloured bubbles + audit IDs
│       │   ├── Sidebar.jsx             Provider selector + quick scenarios
│       │   ├── EvalDashboard.jsx       Precision/recall/confusion matrix
│       │   ├── WorkflowDemo.jsx        One-click scenario runner
│       │   └── MediaInput.jsx          Voice recorder + file upload
│       └── utils/
│           ├── api.js                  Full API client
│           └── health.js               Backend health check on load
│
└── .github/workflows/deploy.yml        Auto-deploy to GitHub Pages
```

---

## Fraud Scoring — 4 Layers Combined

```
Final Risk Score =
  Bayesian Signal Score     × 0.45   (13 CBN-cited signals, calibrated LRs)
+ Behavioral Deviation Score × 0.30   (user's own history vs current tx)
+ Graph Risk Score           × 0.25   (network-level patterns)
+ Hard Override Rules        (override to CRITICAL regardless of score)
```

### Hard Override Rules (always trigger CRITICAL)
| Rule | Condition |
|---|---|
| `BVN_MISMATCH_HIGH_VALUE` | NIN-BVN mismatch + amount > ₦50,000 |
| `SIM_SWAP_RAPID_TRANSFER` | SIM swap signal on USSD channel |
| `CIRCULAR_FLOW_ANY_AMOUNT` | Round-trip transfer > ₦100,000 |
| `MULE_CLUSTER_RECIPIENT` | Recipient in mule cluster pattern |
| `STRUCTURING_REPEAT` | Structuring + split transaction together |

### Analyst Decision Tiers
| Score | Decision | Action |
|---|---|---|
| 0–25 | Auto Approve | ✅ Transaction proceeds |
| 26–50 | Review Queue | 🟡 Analyst reviews within 2 hours |
| 51–75 | Escalate | 🔴 Hold + compliance team |
| 76–100 | Freeze + STR | 🚨 Block + NFIU filing |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Multi-turn streaming agent |
| `POST` | `/api/fraud/analyze` | 4-layer fraud analysis → full case output |
| `POST` | `/api/fraud/feedback` | Analyst outcome → feedback loop |
| `GET`  | `/api/fraud/drift` | Signal drift + fraud rate change detection |
| `POST` | `/api/fraud/events/publish` | Publish to async event stream |
| `POST` | `/api/loans/eligibility` | CBN-compliant loan assessment |
| `POST` | `/api/transactions/insights` | Nigerian spending analytics |
| `POST` | `/api/eval/run` | Precision/recall on 40-sample dataset |
| `POST` | `/api/workflows/run` | One-click scenario demo |
| `POST` | `/api/media/voice` | Groq Whisper transcription |
| `POST` | `/api/media/upload` | PDF/CSV/image fraud scan |
| `GET`  | `/api/health` | Health check |

Interactive docs: `https://nigerian-fintech-agent-production.up.railway.app/docs`

---

## Groq Dual-Model Setup (Both Free)

```
Primary:  llama-3.3-70b-versatile   ← best quality
Fallback: llama3-70b-8192           ← auto-used when primary hits rate limit
```

Both models are free on Groq. The system automatically falls back on HTTP 429.

---

## Quickstart

```bash
git clone https://github.com/HenryMorganDibie/nigerian-fintech-agent.git
cd nigerian-fintech-agent
cp .env.example .env
# Add: GROQ_API_KEY=gsk_your_key_here

cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

---

## Compliance Layer

| Requirement | Implementation |
|---|---|
| NDPA 2023 §40 | UUID audit log on every AI decision |
| NDPA 2023 §24 | PII scrubbed before any LLM API call |
| CBN AML/CFT 2022 §10 | 5-year retention stamped at creation |
| NFIU STR 24h deadline | Auto-triggered on high/critical risk |
| NFIU CTR 7-day for >₦5M | Auto-triggered on large transactions |
| EFCC referral | Critical + >₦5M escalation path |

---

## Roadmap

- [ ] Kafka / Redis Streams production backend (swap event_stream.py)
- [ ] Neo4j graph database for persistent fraud graph
- [ ] NIBSS BVN API live validation
- [ ] WhatsApp Business API channel
- [ ] Fine-tuned fraud model on Nigerian transaction data
- [ ] CBN sandbox certification

---

**Henry Dibie** — ML/Data Engineer
[LinkedIn](https://linkedin.com/in/kinghenrymorgan) · [GitHub](https://github.com/HenryMorganDibie) · [Medium](https://medium.com/@KingHenryMorgan)
