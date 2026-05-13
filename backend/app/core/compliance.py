"""
Nigerian Data Protection & Compliance Engine
==============================================
Implements requirements from:
- Nigeria Data Protection Act (NDPA) 2023
- Nigeria Data Protection Regulation (NDPR) 2019
- CBN AML/CFT Regulations 2022
- EFCC (Establishment) Act (Amended) 2004

Key compliance requirements enforced here:
1. Audit trail generation for every AI decision (explainability mandate)
2. NDPA breach notification timeline (72 hours to NDPC)
3. Data minimisation — PII fields stripped from AI context
4. STR/CTR filing deadlines and escalation paths
5. Consent and lawful basis recording
"""

from datetime import datetime, timezone
from dataclasses import dataclass, field
import uuid
import json


# ── Compliance Constants ──────────────────────────────────────────────────────

NDPA_BREACH_NOTIFICATION_HOURS = 72       # NDPA 2023, Section 40(1)
NFIU_STR_FILING_DEADLINE_HOURS = 24       # NFIU STR Guidelines
NFIU_CTR_FILING_DEADLINE_DAYS = 7         # CBN AML/CFT Reg 2022, Section 4.2
CBN_RECORD_RETENTION_YEARS = 5            # CBN AML/CFT Reg 2022, Section 10
EFCC_ESCALATION_THRESHOLD_NGN = 5_000_000 # Mandatory EFCC referral above this


# ── Audit Log Entry ───────────────────────────────────────────────────────────

@dataclass
class AuditLogEntry:
    """
    Immutable audit record for every AI decision.
    Required by NDPA 2023 for automated decision-making affecting individuals.
    """
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str = ""              # fraud_analysis | loan_decision | chat_interaction
    customer_id_hash: str = ""        # SHA-256 of customer ID — never raw PII
    transaction_id: str = ""
    ai_decision: str = ""             # approve | review | hold | block
    risk_score: int = 0
    signals_triggered: list[str] = field(default_factory=list)
    cbn_references: list[str] = field(default_factory=list)
    llm_provider: str = ""
    model_version: str = ""
    human_review_required: bool = False
    ndpa_lawful_basis: str = "legitimate_interest"   # NDPA 2023, Section 25
    data_retention_expires: str = ""  # ISO date, 5 years from now per CBN

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2)


# ── Regulatory Filing Tracker ─────────────────────────────────────────────────

@dataclass
class RegulatoryFiling:
    filing_type: str           # STR | CTR | EFCC_REFERRAL | NDPC_BREACH
    deadline_description: str
    regulatory_body: str
    form_reference: str
    urgency_hours: int
    triggered_by: str


def get_required_filings(
    risk_level: str,
    amount_ngn: float,
    signal_names: list[str],
    is_data_breach: bool = False,
) -> list[RegulatoryFiling]:
    """
    Returns the list of regulatory filings required based on transaction risk assessment.
    Referenced against Nigerian regulatory requirements.
    """
    filings = []

    # STR — Suspicious Transaction Report
    str_triggers = {"critical", "high"}
    if risk_level in str_triggers or "NIN_BVN_MISMATCH" in signal_names or "ROUND_TRIP_TRANSFER" in signal_names:
        filings.append(RegulatoryFiling(
            filing_type="STR",
            deadline_description="File Suspicious Transaction Report with NFIU within 24 hours",
            regulatory_body="Nigerian Financial Intelligence Unit (NFIU)",
            form_reference="NFIU STR Form — goaml.nfiu.gov.ng",
            urgency_hours=24,
            triggered_by=", ".join(signal_names) or risk_level,
        ))

    # CTR — Currency Transaction Report (>₦5M)
    if amount_ngn >= 5_000_000:
        filings.append(RegulatoryFiling(
            filing_type="CTR",
            deadline_description="File Currency Transaction Report with NFIU within 7 days",
            regulatory_body="Nigerian Financial Intelligence Unit (NFIU)",
            form_reference="NFIU CTR Form — CBN AML/CFT Reg 2022, Section 4.2",
            urgency_hours=168,  # 7 days
            triggered_by=f"Amount ₦{amount_ngn:,.0f} exceeds CTR threshold",
        ))

    # EFCC Referral (>₦5M + critical risk)
    if amount_ngn >= EFCC_ESCALATION_THRESHOLD_NGN and risk_level == "critical":
        filings.append(RegulatoryFiling(
            filing_type="EFCC_REFERRAL",
            deadline_description="Refer to EFCC Cybercrime Unit — do not alert customer",
            regulatory_body="Economic and Financial Crimes Commission (EFCC)",
            form_reference="EFCC Cybercrime Reporting Portal — cybercrime.efcc.gov.ng",
            urgency_hours=48,
            triggered_by="Critical risk + large value transaction",
        ))

    # NDPC Breach Notification
    if is_data_breach:
        filings.append(RegulatoryFiling(
            filing_type="NDPC_BREACH",
            deadline_description="Notify NDPC of data breach within 72 hours (NDPA 2023, Section 40)",
            regulatory_body="Nigeria Data Protection Commission (NDPC)",
            form_reference="NDPC Breach Notification Form — ndpc.gov.ng",
            urgency_hours=72,
            triggered_by="Personal data breach detected",
        ))

    return filings


# ── PII Scrubber ──────────────────────────────────────────────────────────────

PII_FIELDS = {
    "bvn", "nin", "phone_number", "email", "full_name",
    "date_of_birth", "address", "account_number",
}

def scrub_pii_for_llm(data: dict) -> dict:
    """
    Removes PII fields before sending to external LLM APIs.
    Required for NDPA 2023 data minimisation (Section 24) and
    CBN cloud outsourcing data residency requirements.
    """
    scrubbed = {}
    for k, v in data.items():
        if k.lower() in PII_FIELDS:
            scrubbed[k] = f"[REDACTED-{k.upper()}]"
        elif isinstance(v, dict):
            scrubbed[k] = scrub_pii_for_llm(v)
        else:
            scrubbed[k] = v
    return scrubbed


# ── Consent / Lawful Basis Registry ──────────────────────────────────────────

LAWFUL_BASIS_OPTIONS = {
    "consent": "Customer provided explicit consent — NDPA 2023, Section 25(a)",
    "contract": "Processing necessary for contract performance — NDPA 2023, Section 25(b)",
    "legal_obligation": "Required by law (CBN, EFCC, NFIU regulations) — NDPA 2023, Section 25(c)",
    "legitimate_interest": "Fraud prevention as legitimate interest — NDPA 2023, Section 25(f)",
    "vital_interest": "Protection of customer's vital interests — NDPA 2023, Section 25(d)",
}
