# 🇳🇬 NaijaFinAI — Production AI Agent for Nigerian Fintechs

> The only AI fraud intelligence platform built natively for the Nigerian payments ecosystem.

[![Live Demo](https://img.shields.io/badge/Live_Demo-GitHub_Pages-00E676?style=flat-square&logo=github)](https://henrymorgandibie.github.io/nigerian-fintech-agent)
[![Backend](https://img.shields.io/badge/Backend-Railway-8B5CF6?style=flat-square)](https://nigerian-fintech-agent-production.up.railway.app/docs)
[![Groq](https://img.shields.io/badge/LLM-Groq_Free_+_Fallback-00E676?style=flat-square)](https://console.groq.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

---

## Architecture — 7 Layers

```
Transaction Event
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1 — Event Stream (event_stream.py)                           │
│  Async queue → Kafka-ready interface                                │
│  POST /api/fraud/events/publish                                     │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2 — Feature Store (feature_store.py)                         │
│  Per-user behavioral memory: velocity, device history,              │
│  beneficiary graph, typical hours, location patterns                │
│  In-memory default → Redis via REDIS_URL env var                    │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3 — Fraud Intelligence (nigeria_intelligence + bayesian)     │
│  13 Nigerian heuristic signals + Bayesian log-odds scoring          │
│  CBN/EFCC/NFIU citations on every signal                            │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 4 — Fraud Graph (fraud_graph.py)                             │
│  Shared device detection, circular flows, mule clusters,            │
│  fan-out smurfing, flagged account propagation                      │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 5 — Decision Engine (decision_engine.py)                     │
│  Composite Score = Bayesian(45%) + Behavioral(30%) + Graph(25%)     │
│  + 5 Hard Override Rules                                            │
│  → auto_approve | review_queue | escalate | freeze_and_str          │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 6 — Analyst Feedback Loop (decision_engine.py FeedbackStore) │
│  POST /api/fraud/feedback → signal weight updates                   │
│  fraud_confirmed | false_positive | chargeback_confirmed            │
└─────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 7 — Drift Monitor (decision_engine.py DriftMonitor)          │
│  PSI drift detection, fraud rate spike alerts, signal decay          │
│  GET /api/fraud/drift                                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Full File Structure

```
nigerian-fintech-agent/
│
├── backend/
│   └── app/
│       ├── core/
│       │   ├── event_stream.py        Layer 1 — Async ingestion (Kafka-ready)
│       │   ├── feature_store.py       Layer 2 — Behavioral memory (Redis-ready)
│       │   ├── nigeria_intelligence.py Layer 3a — 13 Nigerian heuristic signals
│       │   ├── bayesian_scorer.py     Layer 3b — Bayesian log-odds scorer
│       │   ├── fraud_graph.py         Layer 4 — Graph fraud detection
│       │   ├── decision_engine.py     Layers 5+6+7 — Decision + Feedback + Drift
│       │   ├── explainability.py      Human-readable reason codes per decision
│       │   ├── simulation.py          6 pre-built Nigerian attack scenarios
│       │   ├── workflows.py           3 one-click fintech demo workflows
│       │   ├── evaluation.py          40-sample synthetic eval harness
│       │   ├── case_queue.py          Fraud investigation case management
│       │   ├── token_budget.py        Daily token budget + model selection
│       │   ├── compliance.py          NDPA audit logs + NFIU filing tracker
│       │   ├── language.py            Pidgin/Yoruba/Hausa/Igbo detection
│       │   ├── llm_factory.py         Groq primary + fallback + circuit breaker
│       │   └── config.py              Settings + dual Groq model config
│       ├── routers/
│       │   ├── chat.py                POST /api/chat (SSE streaming)
│       │   ├── fraud.py               POST /api/fraud/analyze (4-layer)
│       │   │                          POST /api/fraud/feedback
│       │   │                          GET  /api/fraud/drift
│       │   │                          POST /api/fraud/events/publish
│       │   ├── loans.py               POST /api/loans/eligibility
│       │   ├── transactions.py        POST /api/transactions/insights
│       │   ├── eval.py                POST /api/eval/run
│       │   ├── workflows.py           POST /api/workflows/run
│       │   ├── simulation.py          POST /api/simulate/run
│       │   ├── ab_testing.py          GET/POST /api/ab/*
│       │   ├── cases.py               GET/POST /api/cases/*
│       │   └── media.py               POST /api/media/voice + /upload
│       └── agents/fintech_agent.py    LangChain bind_tools + Groq fallback
│
├── frontend/
│   └── src/
│       ├── App.jsx                    6-tab layout
│       ├── components/
│       │   ├── ChatMessage.jsx        Risk-coloured bubbles + audit IDs
│       │   ├── Sidebar.jsx            Provider selector + quick scenarios
│       │   ├── ToolCallBanner.jsx     Live tool invocation display
│       │   ├── EvalDashboard.jsx      Precision/recall/confusion matrix
│       │   ├── WorkflowDemo.jsx       One-click scenario runner
│       │   ├── SimulationPanel.jsx    6 Nigerian attack simulations
│       │   ├── MonitoringDashboard.jsx PSI drift + feedback loop UI
│       │   └── MediaInput.jsx         Voice recorder + file upload
│       └── utils/
│           ├── api.js                 Complete API client (all endpoints)
│           ├── health.js              Backend health check
│           └── greeting.js            Nigerian multilingual time greeting
│
├── locustfile.py                      Load testing (pip install locust)
├── .github/workflows/deploy.yml       Auto-deploy to GitHub Pages
└── .env.example                       Groq-first, annotated
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Multi-turn streaming agent (SSE) |
| `POST` | `/api/fraud/analyze` | 4-layer fraud analysis → full case output |
| `POST` | `/api/fraud/feedback` | Analyst outcome → feedback loop |
| `GET`  | `/api/fraud/drift` | PSI drift + fraud rate change detection |
| `POST` | `/api/fraud/events/publish` | Publish to async event stream |
| `POST` | `/api/loans/eligibility` | CBN-compliant loan assessment |
| `POST` | `/api/transactions/insights` | Nigerian spending analytics |
| `POST` | `/api/eval/run` | Precision/recall/F1 on 40-sample dataset |
| `GET`  | `/api/eval/dataset` | View labelled fraud dataset |
| `POST` | `/api/workflows/run` | One-click workflow scenario |
| `POST` | `/api/simulate/run` | Nigerian attack simulation (no LLM tokens) |
| `GET`  | `/api/simulate/scenarios` | List all simulation scenarios |
| `GET`  | `/api/ab/experiments` | List A/B experiments + traffic splits |
| `POST` | `/api/ab/fraud/analyze` | Route through A/B experiment |
| `GET`  | `/api/ab/results/{id}` | Compare variant results |
| `GET`  | `/api/cases/list` | List fraud investigation cases |
| `POST` | `/api/cases/create` | Create case from fraud analysis |
| `POST` | `/api/cases/{id}/action` | Approve / Reject / Escalate / Assign |
| `POST` | `/api/media/voice` | Groq Whisper transcription (free) |
| `POST` | `/api/media/upload` | PDF/CSV/image fraud scan |
| `GET`  | `/api/health` | Health + circuit breakers + token budget |

Interactive docs: `https://nigerian-fintech-agent-production.up.railway.app/docs`

---

## Fraud Scoring Formula

```
Final Risk Score =
  Bayesian Signal Score      × 0.45
+ Behavioral Deviation Score × 0.30
+ Graph Risk Score           × 0.25
+ Hard Override Rules        (force CRITICAL regardless of composite)
```

### Hard Overrides (always CRITICAL)
| Rule | Condition |
|---|---|
| `BVN_MISMATCH_HIGH_VALUE` | NIN-BVN mismatch + amount > ₦50,000 |
| `SIM_SWAP_RAPID_TRANSFER` | SIM swap signal on USSD |
| `CIRCULAR_FLOW_ANY_AMOUNT` | Round-trip transfer > ₦100,000 |
| `MULE_CLUSTER_RECIPIENT` | Mule cluster pattern on recipient |
| `STRUCTURING_REPEAT` | Structuring + split transaction combined |

### Decision Tiers
| Score | Decision | Action |
|---|---|---|
| 0–25 | Auto Approve | ✅ Transaction proceeds |
| 26–50 | Review Queue | 🟡 Analyst reviews within 2 hours |
| 51–75 | Escalate | 🔴 Hold + compliance team |
| 76–100 | Freeze + STR | 🚨 Block + file STR with NFIU |

---

## Groq Dual-Model (Both Free)

```
Primary:  llama-3.3-70b-versatile   (100k tokens/day)
Fallback: llama-3.1-8b-instant      (500k tokens/day) ← auto on rate limit
```

Circuit breaker: 3 failures → 10-minute cooldown per provider.

---

## Quickstart

```bash
git clone https://github.com/HenryMorganDibie/nigerian-fintech-agent.git
cd nigerian-fintech-agent
cp .env.example .env
# Add: GROQ_API_KEY=gsk_...

cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

---

## Load Testing

```bash
pip install locust
locust -f locustfile.py --host https://nigerian-fintech-agent-production.up.railway.app

# Open http://localhost:8089
# Recommended: 50 users, 5/s spawn rate, 5 minutes
```

---

## Production Upgrade Paths

| Current | Production Upgrade |
|---|---|
| `asyncio.Queue` event stream | `kafka-python` or `redis.streams` |
| In-memory feature store | Redis (`REDIS_URL` env var already wired) |
| In-memory fraud graph | Neo4j AuraDB |
| In-memory case queue | PostgreSQL (append-only audit table) |
| In-memory A/B results | PostgreSQL + Grafana dashboard |
| Groq free tier | Groq paid or self-hosted Ollama |

---

## Compliance Layer

| Requirement | Implementation |
|---|---|
| NDPA 2023 §40 — Automated decisions | UUID audit log on every AI decision |
| NDPA 2023 §24 — Data minimisation | PII scrubbed before any LLM API call |
| CBN AML/CFT 2022 §10 — Retention | 5-year expiry stamped at creation |
| NFIU STR — 24h filing deadline | Auto-triggered on high/critical |
| NFIU CTR — 7-day for >₦5M | Auto-triggered on large transactions |
| EFCC referral — Critical + >₦5M | Escalation path in every critical case |

---

**Henry Dibie** — ML/Data Engineer
[LinkedIn](https://linkedin.com/in/kinghenrymorgan) · [GitHub](https://github.com/HenryMorganDibie) · [Medium](https://medium.com/@KingHenryMorgan)
