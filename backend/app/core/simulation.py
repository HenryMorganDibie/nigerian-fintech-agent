"""
Fraud Simulation Sandbox
==========================
Pre-built attack scenarios for demos and testing.
Triggers realistic Nigerian fraud patterns and shows NaijaFinAI responding live.

Scenarios:
  1. SIM Swap Account Takeover
  2. Mule Chain / Money Laundering
  3. Structuring / Smurfing
  4. First-Party Loan Fraud
  5. Circular Flow / Layering
  6. Agent Network Attack
"""

from datetime import datetime, timezone
from app.models.schemas import Transaction
import uuid


def _tx(**kwargs) -> Transaction:
    defaults = dict(
        transaction_id=str(uuid.uuid4())[:10],
        amount=50000,
        timestamp=datetime.now(timezone.utc),
        sender_account="".join(["1234567890"[:10]]),
        recipient_account="0987654321",
        channel="transfer",
        is_new_recipient=False,
        is_new_device=False,
        is_agent_terminal=False,
        is_pos=False,
        is_post_loan_disbursement=False,
        device_changed_hours_ago=None,
        sim_replaced_hours_ago=None,
        transactions_last_hour=0,
        agent_tx_count_last_hour=0,
        bvn_verified=True,
        nin_bvn_match=True,
        narration="",
        recent_outbound_ngn=0.0,
        recent_inbound_from_same_ngn=0.0,
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


SIMULATION_SCENARIOS = {

    "sim_swap_attack": {
        "name": "SIM Swap Account Takeover",
        "description": "Attacker replaces victim's SIM, waits for overnight window, drains account via USSD",
        "expected_risk": "critical",
        "attack_story": [
            "22:00 — Attacker walks into MTN shop, swaps victim's SIM using fake ID",
            "02:30 — Attacker initiates ₦85,000 USSD transfer to new account",
            "02:31 — Second transfer ₦90,000 to different account",
            "02:32 — System detects pattern and triggers SIM_SWAP_HIGH_VALUE_USSD signal",
        ],
        "transaction": _tx(
            amount=85000,
            channel="ussd",
            timestamp=datetime(2026, 5, 29, 2, 30, tzinfo=timezone.utc),
            is_new_recipient=True,
            is_new_device=True,
            device_changed_hours_ago=4,
            sim_replaced_hours_ago=5,
            transactions_last_hour=2,
            bvn_verified=True,
            nin_bvn_match=True,
            narration="",
        ),
    },

    "mule_chain_attack": {
        "name": "Agent Network Mule Chain",
        "description": "Criminal uses multiple OPay agent terminals to layer stolen funds through mule accounts",
        "expected_risk": "critical",
        "attack_story": [
            "14:00 — Agent terminal AGT-LOS-0847 begins processing unusual volume",
            "14:00–15:00 — 31 transactions to 28 unique recipients",
            "Narrations contain: 'investment returns', 'profit withdrawal'",
            "System triggers AGENT_VELOCITY_SPIKE + SCAM_KEYWORDS_NARRATION",
        ],
        "transaction": _tx(
            amount=45000,
            channel="agent",
            is_new_recipient=True,
            is_agent_terminal=True,
            agent_tx_count_last_hour=31,
            transactions_last_hour=5,
            narration="investment returns profit withdrawal",
        ),
    },

    "structuring_attack": {
        "name": "Structuring / Smurfing",
        "description": "Criminal splits large sum into sub-₦1M transfers to avoid CBN Currency Transaction Report",
        "expected_risk": "critical",
        "attack_story": [
            "9:00 — Transfer of ₦998,500 (just below ₦1M CTR threshold)",
            "9:15 — Transfer of ₦997,000 to different account",
            "9:30 — Transfer of ₦995,000 to third account",
            "System triggers CBN_STRUCTURING + SPLIT_TRANSACTION_PATTERN",
        ],
        "transaction": _tx(
            amount=998500,
            channel="transfer",
            is_new_recipient=True,
            transactions_last_hour=3,
            narration="",
        ),
    },

    "first_party_loan_fraud": {
        "name": "First-Party Loan Fraud",
        "description": "Customer applies for loan with intent to immediately withdraw and default",
        "expected_risk": "high",
        "attack_story": [
            "10:00 — Loan application approved: ₦500,000 at 4% monthly",
            "10:02 — Full ₦500,000 disbursed to account",
            "10:03 — Immediate full withdrawal to new unverified recipient",
            "System triggers FIRST_PARTY_FRAUD_LOAN signal",
        ],
        "transaction": _tx(
            amount=500000,
            channel="transfer",
            is_new_recipient=True,
            is_post_loan_disbursement=True,
            transactions_last_hour=1,
            narration="withdrawal",
        ),
    },

    "circular_flow_attack": {
        "name": "Circular Flow / Money Laundering",
        "description": "Criminal moves funds A→B→C→A to obscure source — classic layering",
        "expected_risk": "critical",
        "attack_story": [
            "Account A sends ₦2,000,000 to Account B",
            "Account B sends ₦1,950,000 to Account C (taking 2.5% cut)",
            "Account C returns ₦1,900,000 to Account A (appearing as 'payment')",
            "System detects ROUND_TRIP_TRANSFER — funds returned within 24h",
        ],
        "transaction": _tx(
            amount=2000000,
            channel="transfer",
            recent_outbound_ngn=2000000,
            recent_inbound_from_same_ngn=1900000,
            narration="payment",
        ),
    },

    "account_takeover": {
        "name": "Account Takeover — Device + Social Engineering",
        "description": "Victim tricked into sharing OTP. Attacker logs in from new device and transfers",
        "expected_risk": "high",
        "attack_story": [
            "Victim receives WhatsApp: 'Your GTB account will be blocked — confirm OTP'",
            "Victim shares OTP. Attacker logs into account from new device",
            "New device fingerprint detected, ₦180,000 transfer initiated 3 hours later",
            "System triggers DEVICE_CHANGE_BEFORE_TRANSFER + USSD_AFTER_HOURS",
        ],
        "transaction": _tx(
            amount=180000,
            channel="mobile",
            timestamp=datetime(2026, 5, 29, 3, 15, tzinfo=timezone.utc),
            is_new_recipient=True,
            is_new_device=True,
            device_changed_hours_ago=3,
            narration="urgent transfer",
        ),
    },
}


def get_scenario(scenario_id: str) -> dict | None:
    return SIMULATION_SCENARIOS.get(scenario_id)


def list_scenarios() -> list[dict]:
    return [
        {
            "id": k,
            "name": v["name"],
            "description": v["description"],
            "expected_risk": v["expected_risk"],
        }
        for k, v in SIMULATION_SCENARIOS.items()
    ]
