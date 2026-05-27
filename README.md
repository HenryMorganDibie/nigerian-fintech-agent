# 🇳🇬 NaijaFinAI — Production AI Agent for Nigerian Fintechs

> **The only AI fraud intelligence platform built natively for the Nigerian payments ecosystem.**
> Not a global tool with a Nigerian skin — built from the ground up for CBN regulations, NFIU filing deadlines, Nigerian fraud typologies, and all five Nigerian languages.

[![Live Demo](https://img.shields.io/badge/Live_Demo-GitHub_Pages-00E676?style=flat-square&logo=github)](https://henrymorgandibie.github.io/nigerian-fintech-agent)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_3.0-009688?style=flat-square)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/LLM-Groq_Free_Tier-8B5CF6?style=flat-square)](https://console.groq.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

---

## What Makes This Different

| Capability | Generic AI Tools | NaijaFinAI v3 |
|---|---|---|
| Fraud signals | Generic velocity checks | 13 Nigerian-specific signals with CBN circular citations |
| Scoring model | Additive rules | **Bayesian log-odds aggregation** — calibrated probabilities |
| Regulatory output | None | NFIU STR/CTR deadlines, EFCC referral thresholds, exact form links |
| Languages | English only | English + Pidgin + Yoruba + Hausa + Igbo with financial glossary |
| Voice input | None | Groq Whisper — free, Nigerian-language aware |
| Compliance | No audit trail | NDPA 2023 §40 audit logs, PII scrubbing, 5-year retention |
| Eval harness | None | **Precision/recall/F1 per signal + confusion matrix dashboard** |
| Workflow demos | None | **3 one-click fintech scenarios** (loan fraud, agent monitoring, chargeback) |
| Case output | None | Structured: risk score, top-3 signals, regulatory action, audit ID |

---

## Architecture

```
nigerian-fintech-agent/
│
├── backend/                            FastAPI + LangChain
│   └── app/
│       ├── core/
│       │   ├── nigeria_intelligence.py  13 Nigerian fraud signals + CBN refs
│       │   ├── bayesian_scorer.py       ← NEW: Bayesian log-odds risk scoring
│       │   ├── evaluation.py            ← NEW: 40-sample synthetic eval harness
│       │   ├── workflows.py             ← NEW: 3 one-click fintech scenarios
│       │   ├── compliance.py            NDPA audit logs + NFIU filing tracker
│       │   ├── language.py              Pidgin/Yoruba/Hausa/Igbo detection
│       │   ├── llm_factory.py           Multi-provider LLM (Groq default)
│       │   ├── prompts.py               Nigeria-specialised system prompts
│       │   └── config.py                Groq-first settings + startup validator
│       ├── tools/
│       │   └── fintech_tools.py         3 LangChain tools (fraud, loans, insights)
│       ├── agents/
│       │   └── fintech_agent.py         Orchestrator + streaming + audit
│       └── routers/
│           ├── chat.py                  POST /api/chat (SSE streaming)
│           ├── fraud.py                 POST /api/fraud/analyze → CaseOutput
│           ├── loans.py                 POST /api/loans/eligibility
│           ├── transactions.py          POST /api/transactions/insights
│           ├── eval.py                  ← NEW: POST /api/eval/run
│           ├── workflows.py             ← NEW: POST /api/workflows/run
│           └── media.py                 ← NEW: POST /api/media/voice + /upload
│
├── frontend/                           React 18 + Vite + Tailwind
│   └── src/
│       ├── App.jsx                      4-tab layout (Chat/Workflows/Eval/Voice)
│       ├── components/
│       │   ├── ChatMessage.jsx          Risk-coloured bubbles + audit IDs
│       │   ├── Sidebar.jsx              Provider selector + quick scenarios
│       │   ├── ToolCallBanner.jsx       Shows tools invoked
│       │   ├── EvalDashboard.jsx        ← NEW: Precision/recall/confusion matrix
│       │   ├── WorkflowDemo.jsx         ← NEW: One-click scenario runner
│       │   └── MediaInput.jsx           ← NEW: Voice recorder + file upload
│       ├── hooks/useChat.js             Streaming chat state
│       └── utils/api.js                 Full API client
│
├── .github/workflows/deploy.yml        ← NEW: Auto-deploy to GitHub Pages
├── docker-compose.yml
└── .env.example                        Groq-first, annotated
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Multi-turn agent (SSE streaming, all 5 languages) |
| `POST` | `/api/fraud/analyze` | Bayesian fraud analysis → structured CaseOutput |
| `POST` | `/api/loans/eligibility` | CBN-compliant loan assessment |
| `POST` | `/api/transactions/insights` | Nigerian spending analytics |
| `POST` | `/api/eval/run` | Run evaluation harness on synthetic dataset |
| `GET`  | `/api/eval/dataset` | View the 40-sample labelled dataset |
| `GET`  | `/api/workflows/scenarios` | List available demo scenarios |
| `POST` | `/api/workflows/run` | Run a workflow scenario end-to-end |
| `POST` | `/api/media/voice` | Transcribe audio (Groq Whisper, all Nigerian languages) |
| `POST` | `/api/media/upload` | Upload PDF/image/CSV for fraud scan |
| `GET`  | `/api/providers` | List configured LLM providers |
| `GET`  | `/api/health` | Health check |

Interactive docs: `http://localhost:8000/docs`

---

## Nigerian Fraud Intelligence — 13 Signals

Each signal has a **CBN/EFCC/NFIU regulatory citation**, **Bayesian likelihood ratio**, and **recommended action**:

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
# Terminal shows startup check — confirms which providers are ready

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Frontend: 4 Tabs

### 1. Chat
Multi-turn agent in any Nigerian language. Detects Pidgin, Yoruba, Hausa, Igbo automatically and responds in kind. Audit ID shown per message. Tools invoked shown in banner.

### 2. Workflows
One-click end-to-end scenarios:
- **Loan Application Fraud Check** — KYC → eligibility → post-disbursement monitoring → STR filing
- **Agent Wallet Monitoring** — terminal baseline → velocity spike → mule chain detection → suspension
- **Chargeback Investigation** — dispute intake → SIM/device analysis → CBN dispute timeline

### 3. Eval Dashboard
Runs the Bayesian scorer against 40 synthetic Nigerian fraud transactions. Shows overall precision/recall/F1, confusion matrix, and per-signal breakdown. Validates the model against ground truth.

### 4. Voice & Files
- **Voice**: Record in any Nigerian language — transcribed by Groq Whisper (free), language auto-detected, transcript sent to chat agent
- **Files**: Upload PDF, image, CSV — text extracted, scanned for Nigerian fraud signals, risk level returned

---

## Deploying to GitHub Pages

The frontend auto-deploys on every push to `main` via GitHub Actions (`.github/workflows/deploy.yml`).

To deploy manually:
```bash
cd frontend
npm install
npm run deploy
```

Live at: **https://henrymorgandibie.github.io/nigerian-fintech-agent**

> **Note:** The live demo connects to a hosted backend. For full functionality, deploy the backend to [Render](https://render.com) or [Railway](https://railway.app) (both have free tiers) and update `VITE_API_URL` in the workflow file.

---

## Compliance Layer

| Requirement | Implementation |
|---|---|
| NDPA 2023 §40 — Automated decision audit | UUID audit log on every AI decision |
| NDPA 2023 §24 — Data minimisation | PII scrubbed before LLM API calls |
| CBN AML/CFT 2022 §10 — Record retention | 5-year expiry stamped at creation |
| NFIU STR — 24-hour filing deadline | Regulatory filing tracker per case |
| NFIU CTR — 7-day filing for >₦5M | Auto-triggered on large transactions |
| EFCC referral — Critical + >₦5M | Escalation path in every critical case |

---

## Roadmap

- [ ] NIBSS BVN API live validation
- [ ] WhatsApp Business API channel
- [ ] Persistent audit store (PostgreSQL append-only)
- [ ] CBN sandbox certification
- [ ] Fine-tuned fraud model on Nigerian transaction data
- [ ] Multi-tenant API with per-fintech configuration

---

## Author

**Henry Dibie** — ML/Data Engineer  
[LinkedIn](https://linkedin.com/in/kinghenrymorgan) · [GitHub](https://github.com/HenryMorganDibie) · [Medium](https://medium.com/@KingHenryMorgan) · [X](https://twitter.com/KingHenryMorgan)
