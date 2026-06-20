from pydantic import BaseModel, Field
from typing import Literal, Optional, Any
from datetime import datetime


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    provider: Optional[str] = None
    tenant_id: Optional[str] = None
    stream: bool = True


class ChatResponse(BaseModel):
    reply: str
    provider_used: str
    language_detected: str = "english"
    tool_calls: list[str] = []
    audit_id: Optional[str] = None


# ── Transaction ───────────────────────────────────────────────────────────────

class Transaction(BaseModel):
    transaction_id: str
    amount: float
    timestamp: datetime
    sender_account: str
    recipient_account: str
    channel: str = "transfer"          # accept any string — no strict enum
    direction: str = "debit"
    is_new_recipient: bool = False
    is_new_device: bool = False
    is_agent_terminal: bool = False
    is_pos: bool = False
    is_post_loan_disbursement: bool = False
    device_changed_hours_ago: Optional[int] = None
    sim_replaced_hours_ago: Optional[int] = None
    transactions_last_hour: int = 0
    agent_tx_count_last_hour: int = 0
    bvn_verified: bool = True
    nin_bvn_match: bool = True
    narration: str = ""
    recent_outbound_ngn: float = 0
    recent_inbound_from_same_ngn: float = 0
    # Extended fields — richer scoring
    failed_attempts_last_1h: int = 0       # card testing / brute force
    account_age_days: int = 365            # new account = higher risk
    beneficiary_count_24h: int = 0         # fan-out / mule distribution
    bvn_linked_accounts: int = 1           # shared BVN across accounts
    immediate_cashout_ratio: float = 0.0   # outflow / recent inflow (0–1)
    micro_tx_last_10min: int = 0           # card testing — rapid micro-transactions
    is_pos_reversal: bool = False          # POS reversal after flagged tx
    new_beneficiaries_last_hour: int = 0   # beneficiary explosion detection


class FraudAnalysisRequest(BaseModel):
    transaction: Transaction
    provider: Optional[str] = None


class FraudSignalOut(BaseModel):
    name: str
    severity: str
    description: str
    score_delta: int
    cbn_reference: str


class RegulatoryFilingOut(BaseModel):
    filing_type: str
    deadline_description: str
    regulatory_body: str
    form_reference: str
    urgency_hours: int


class FraudAnalysisResponse(BaseModel):
    transaction_id: str
    risk_score: int
    risk_level: str
    recommended_action: str
    triggered_signals: list[FraudSignalOut]
    cbn_references: list[str]
    regulatory_filings_required: list[RegulatoryFilingOut]
    llm_explanation: str
    audit_id: str
    provider_used: str


# ── CaseOutput ────────────────────────────────────────────────────────────────

class CaseOutput(BaseModel):
    case_id: str
    transaction_id: str
    risk_score: int
    posterior_fraud_probability: float
    risk_level: str
    top_3_signals: list[dict]
    regulatory_action: str
    filings_required: list[RegulatoryFilingOut]
    audit_log_id: str
    llm_narrative: str
    provider_used: str
    created_at: str


# ── Transaction Insights ──────────────────────────────────────────────────────

class TransactionRecord(BaseModel):
    date: str
    amount: float
    type: Literal["debit", "credit"]
    category: Optional[str] = None
    description: Optional[str] = None
    merchant: Optional[str] = None


class TransactionInsightsRequest(BaseModel):
    transactions: list[TransactionRecord]
    period_days: int = 30
    provider: Optional[str] = None


class TransactionInsightsResponse(BaseModel):
    total_inflow: float
    total_outflow: float
    net_flow: float
    savings_rate_pct: float
    top_categories: list[dict[str, Any]]
    anomalies: list[str]
    insights: str
    provider_used: str


# ── Loan ──────────────────────────────────────────────────────────────────────

class LoanEligibilityRequest(BaseModel):
    monthly_income_ngn: float
    employment_status: Literal["employed", "self_employed", "unemployed", "student"]
    bvn_verified: bool
    nin_verified: bool
    account_tier: Literal["tier1", "tier2", "tier3"]
    credit_bureau_score: int = Field(..., ge=300, le=900)
    existing_loan_count: int = 0
    requested_amount_ngn: float
    tenor_months: int
    loan_purpose: str = ""
    provider: Optional[str] = None


class LoanEligibilityResponse(BaseModel):
    eligible: bool
    decision: str
    approved_amount_ngn: Optional[float]
    monthly_rate_pct: Optional[float]
    tenor_months: int
    estimated_monthly_repayment_ngn: Optional[float]
    reasons: list[str]
    warnings: list[str]
    cbn_references: list[str]
    audit_id: str
    provider_used: str


# ── Eval ──────────────────────────────────────────────────────────────────────

class EvalSample(BaseModel):
    transaction_id: str
    label: Literal["fraud", "legit"]
    transaction: Transaction


class EvalRunRequest(BaseModel):
    samples: list[EvalSample] = []
    use_synthetic: bool = True
    provider: Optional[str] = None


class SignalMetrics(BaseModel):
    signal: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


class EvalRunResponse(BaseModel):
    total_samples: int
    fraud_samples: int
    legit_samples: int
    overall_precision: float
    overall_recall: float
    overall_f1: float
    accuracy: float
    confusion_matrix: dict[str, int]
    per_signal_metrics: list[SignalMetrics]
    provider_used: str


class UploadEvalResponse(EvalRunResponse):
    upload_summary: dict[str, Any] = {}


# ── Workflow ──────────────────────────────────────────────────────────────────

class WorkflowScenario(BaseModel):
    scenario_id: str
    name: str
    description: str


class WorkflowRunRequest(BaseModel):
    scenario_id: Literal[
        "loan_application_fraud_check",
        "agent_wallet_monitoring",
        "chargeback_investigation",
    ]
    provider: Optional[str] = None


class WorkflowRunResponse(BaseModel):
    scenario_id: str
    scenario_name: str
    steps: list[dict]
    final_verdict: str
    case_output: CaseOutput
    provider_used: str


# ── Voice & File ──────────────────────────────────────────────────────────────

class VoiceTranscribeResponse(BaseModel):
    transcript: str
    language_detected: str
    confidence: float


class FileAnalysisResponse(BaseModel):
    filename: str
    file_type: str
    extracted_text: str
    summary: str
    fraud_signals_detected: list[str]
    provider_used: str
