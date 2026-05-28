# 🇳🇬 NaijaFinAI — Production AI Agent for Nigerian Fintechs

> **The only AI fraud intelligence platform built natively for the Nigerian payments ecosystem.**

[![Live Demo](https://img.shields.io/badge/Live_Demo-GitHub_Pages-00E676?style=flat-square&logo=github)](https://henrymorgandibie.github.io/nigerian-fintech-agent)
[![Backend](https://img.shields.io/badge/Backend-Railway-8B5CF6?style=flat-square)](https://nigerian-fintech-agent-production.up.railway.app/docs)
[![Groq](https://img.shields.io/badge/LLM-Groq_Free-00E676?style=flat-square)](https://console.groq.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

---

## What Makes This Different

| Capability | Generic AI Tools | NaijaFinAI v3 |
|---|---|---|
| Fraud signals | Generic velocity checks | 13 Nigerian-specific signals with CBN circular citations |
| Scoring model | Additive rules | **Bayesian log-odds aggregation** — calibrated probabilities |
| Regulatory output | None | NFIU STR/CTR deadlines, EFCC referral thresholds, exact form links |
| Languages | English only | English + Pidgin + Yoruba + Hausa + Igbo with financial glossary |
| Voice input | None | Groq Whisper (free) — all Nigerian languages |
| Compliance | None | NDPA 2023 §40 audit logs, PII scrubbing, 5-year retention |
| Eval harness | None | Precision/recall/F1 per signal + confusion matrix dashboard |
| Workflow demos | None | 3 one-click fintech scenarios (loan fraud, agent monitoring, chargeback) |
| Case output | None | Risk score + top-3 signals + regulatory action + audit ID |

---

## Architecture

```
nigerian-fintech-agent/
│
├── backend/                              FastAPI + LangChain + Groq
│   └── app/
│       ├── core/
│       │   ├── nigeria_intelligence.py   13 Nigerian fraud signals + CBN refs
│       │   ├── bayesian_scorer.py        Bayesian log-odds risk scoring
│       │   ├── evaluation.py             40-sample synthetic eval harness
│       │   ├── workflows.py              3 one-click fintech scenarios
│       │   ├── compliance.py             NDPA audit logs + NFIU filing tracker
│       │   ├── language.py               Pidgin/Yoruba/Hausa/Igbo detection
│       │   ├── llm_factory.py            Multi-provider LLM (Groq default)
│       │   ├── prompts.py                Nigeria-specialised system prompts
│       │   └── config.py                 Groq-first + startup validator
│       ├── tools/fintech_tools.py        3 LangChain agent tools
│       ├── agents/fintech_agent.py       Orchestrator + SSE streaming + audit
│       └── routers/
│           ├── chat.py                   POST /api/chat
│           ├── fraud.py                  POST /api/fraud/analyze → CaseOutput
│           ├── loans.py                  POST /api/loans/eligibility
│           ├── transactions.py           POST /api/transactions/insights
│           ├── eval.py                   POST /api/eval/run
│           ├── workflows.py              POST /api/workflows/run
│           └── media.py                  POST /api/media/voice + /upload
│
├── frontend/                             React 18 + Vite + Tailwind
│   └── src/
│       ├── App.jsx                       4-tab layout
│       ├── components/
│       │   ├── ChatMessage.jsx           Risk-coloured bubbles + audit IDs
│       │   ├── Sidebar.jsx               Provider selector + quick scenarios
│       │   ├── ToolCallBanner.jsx        Live tool invocation display
│       │   ├── EvalDashboard.jsx         Precision/recall/confusion matrix
│       │   ├── WorkflowDemo.jsx          One-click scenario runner
│       │   └── MediaInput.jsx            Voice recorder + file upload
│       ├── hooks/useChat.js              Streaming chat state
│       └── utils/
│           ├── api.js                    Full API client
│           └── health.js                 Backend health check
│
├── .github/workflows/deploy.yml          Auto-deploy frontend to GitHub Pages
├── backend/Dockerfile                    Railway deployment
├── docker-compose.yml                    Local full-stack
└── .env.example                          Groq-first, annotated
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Multi-turn streaming agent (SSE, all 5 Nigerian languages) |
| `POST` | `/api/fraud/analyze` | Bayesian fraud analysis → structured CaseOutput |
| `POST` | `/api/loans/eligibility` | CBN-compliant loan assessment |
| `POST` | `/api/transactions/insights` | Nigerian spending analytics |
| `POST` | `/api/eval/run` | Precision/recall/F1 on 40-sample synthetic dataset |
| `GET`  | `/api/eval/dataset` | View labelled fraud dataset |
| `GET`  | `/api/workflows/scenarios` | List available demo scenarios |
| `POST` | `/api/workflows/run` | Run end-to-end workflow scenario |
| `POST` | `/api/media/voice` | Transcribe audio via Groq Whisper (free) |
| `POST` | `/api/media/upload` | Upload PDF/image/CSV for fraud scan |
| `GET`  | `/api/providers` | List configured LLM providers |
| `GET`  | `/api/health` | Health check |

Interactive docs: `https://nigerian-fintech-agent-production.up.railway.app/docs`

---

## Nigerian Fraud Intelligence — 13 Signals

| Signal | Likelihood Ratio | Severity | Regulation |
|---|---|---|---|
| `NIN_BVN_MISMATCH` | 45× | Critical | CBN Circular BPS/DIR/GEN/CIR/03/002 |
| `SIM_SWAP_HIGH_VALUE_USSD` | 22× | Critical | CBN CPD/DIR/GEN/LAB/13/006 |
| `ROUND_TRIP_TRANSFER` | 19.6× | Critical | CBN AML/CFT 2022 §3.1 |
| `CBN_STRUCTURING` | 18.5× | Critical | CBN AML/CFT 2022 §4.3 |
| `AGENT_VELOCITY_SPIKE` | 14.8× | High | CBN Agent Banking 2019 §6.3 |
| `SPLIT_TRANSACTION_PATTERN` | 13.1× | High | CBN AML/CFT 2022 §4.3 |
| `FIRST_PARTY_FRAUD_LOAN` | 12.4× | High | CBN MFB Guidelines §8.4 |
| `UNVERIFIED_BVN_LARGE_TRANSFER` | 11.2× | High | CBN BPS/DIR/2020/004 |
| `DEVICE_CHANGE_BEFORE_TRANSFER` | 9.3× | High | CBN e-Banking Guidelines 2020 §7 |
| `SCAM_KEYWORDS_NARRATION` | 8.7× | High | EFCC Advisory 2024 |
| `USSD_AFTER_HOURS` | 7.2× | High | CBN Fraud Desk Advisory 2023-07 |
| `POS_ABOVE_CBN_LIMIT` | 4.1× | Medium | CBN POS Guidelines 2023 |
| `WEEKEND_MIDNIGHT_SPIKE` | 3.8× | Medium | CBN Fraud Trend Q3 2024 |

---

## Quickstart (5 minutes, free)

```bash
# 1. Clone
git clone https://github.com/HenryMorganDibie/nigerian-fintech-agent.git
cd nigerian-fintech-agent

# 2. Configure — only GROQ_API_KEY needed (free at console.groq.com)
cp .env.example .env
# Edit .env: GROQ_API_KEY=gsk_your_key_here

# 3. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 4. Frontend (new terminal)
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

---

## Deployment

### Backend — Railway
1. Connect repo to Railway
2. Set root directory to `backend/`
3. Add environment variables:
   ```
   GROQ_API_KEY=gsk_...
   DEFAULT_LLM_PROVIDER=groq
   CORS_ORIGINS=https://henrymorgandibie.github.io,http://localhost:5173
   ```

### Frontend — GitHub Pages
Auto-deploys on every push to `main` via GitHub Actions.
Live at: **https://henrymorgandibie.github.io/nigerian-fintech-agent**

---

## Frontend Tabs

| Tab | Description |
|---|---|
| **Chat** | Multi-turn agent — auto-detects Pidgin, Yoruba, Hausa, Igbo, English |
| **Workflows** | One-click: Loan Fraud Check, Agent Wallet Monitor, Chargeback Investigation |
| **Eval** | Live precision/recall/F1 + confusion matrix on 40-sample Nigerian fraud dataset |
| **Voice & Files** | Groq Whisper transcription + PDF/CSV/image fraud scan |

---

## Compliance Layer

| Requirement | Implementation |
|---|---|
| NDPA 2023 §40 — Automated decision audit | UUID audit log on every AI decision |
| NDPA 2023 §24 — Data minimisation | PII scrubbed before any LLM API call |
| CBN AML/CFT 2022 §10 — Record retention | 5-year expiry stamped at creation |
| NFIU STR — 24h filing deadline | Auto-triggered on high/critical risk |
| NFIU CTR — 7-day filing for >₦5M | Auto-triggered on large transactions |
| EFCC referral — Critical + >₦5M | Escalation path in every critical case |

---

## Roadmap

- [ ] NIBSS BVN API live validation
- [ ] WhatsApp Business API channel
- [ ] Persistent audit store (PostgreSQL)
- [ ] CBN sandbox certification
- [ ] Fine-tuned model on Nigerian transaction data

---

## Author

**Henry Dibie** — ML/Data Engineer
[LinkedIn](https://linkedin.com/in/kinghenrymorgan) · [GitHub](https://github.com/HenryMorganDibie) · [Medium](https://medium.com/@KingHenryMorgan) · [X](https://twitter.com/KingHenryMorgan)
