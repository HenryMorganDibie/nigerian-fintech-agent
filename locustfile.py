"""
NaijaFinAI Load Testing — Locust
==================================
Tests all major endpoints under load.

Install: pip install locust
Run:     locust -f locustfile.py --host https://nigerian-fintech-agent-production.up.railway.app

Open http://localhost:8089 to control the test.

Recommended test levels:
  Smoke test:  10 users, 2/s spawn, 1 min
  Load test:   50 users, 5/s spawn, 5 mins
  Stress test: 200 users, 10/s spawn, 10 mins
"""

from locust import HttpUser, task, between
from datetime import datetime, timezone
import random
import uuid


# ── Sample Nigerian transaction payloads ─────────────────────────────────────

def _tx(risk_level="low"):
    """Generate a realistic Nigerian transaction payload."""
    base = {
        "transaction_id": str(uuid.uuid4())[:10],
        "amount": random.choice([5000, 25000, 85000, 250000, 498000, 950000]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sender_account": f"07{random.randint(10000000, 99999999)}",
        "recipient_account": f"08{random.randint(10000000, 99999999)}",
        "channel": random.choice(["transfer", "ussd", "mobile", "pos"]),
        "is_new_recipient": random.random() > 0.7,
        "is_new_device": False,
        "is_agent_terminal": False,
        "is_pos": False,
        "is_post_loan_disbursement": False,
        "device_changed_hours_ago": None,
        "sim_replaced_hours_ago": None,
        "transactions_last_hour": random.randint(0, 3),
        "agent_tx_count_last_hour": 0,
        "bvn_verified": True,
        "nin_bvn_match": True,
        "narration": "payment",
        "recent_outbound_ngn": 0,
        "recent_inbound_from_same_ngn": 0,
    }

    if risk_level == "high":
        base.update({
            "amount": random.choice([950000, 998500, 499000]),
            "channel": "ussd",
            "sim_replaced_hours_ago": random.randint(2, 36),
            "is_new_recipient": True,
            "transactions_last_hour": random.randint(4, 8),
            "timestamp": datetime.now(timezone.utc).replace(hour=3).isoformat(),
        })

    elif risk_level == "critical":
        base.update({
            "amount": 999500,
            "nin_bvn_match": False,
            "bvn_verified": False,
            "sim_replaced_hours_ago": 6,
            "channel": "ussd",
            "narration": "urgent forex investment",
        })

    return base


LOAN_PAYLOADS = [
    {"monthly_income_ngn": 180000, "employment_status": "employed",      "bvn_verified": True,  "nin_verified": True,  "account_tier": "tier2", "credit_bureau_score": 620, "existing_loan_count": 0, "requested_amount_ngn": 250000, "tenor_months": 6},
    {"monthly_income_ngn": 80000,  "employment_status": "self_employed", "bvn_verified": True,  "nin_verified": True,  "account_tier": "tier1", "credit_bureau_score": 450, "existing_loan_count": 1, "requested_amount_ngn": 50000,  "tenor_months": 3},
    {"monthly_income_ngn": 350000, "employment_status": "employed",      "bvn_verified": True,  "nin_verified": True,  "account_tier": "tier3", "credit_bureau_score": 750, "existing_loan_count": 0, "requested_amount_ngn": 500000, "tenor_months": 12},
    {"monthly_income_ngn": 60000,  "employment_status": "unemployed",    "bvn_verified": False, "nin_verified": False, "account_tier": "tier1", "credit_bureau_score": 380, "existing_loan_count": 3, "requested_amount_ngn": 100000, "tenor_months": 6},
]

CHAT_MESSAGES = [
    "A customer made a ₦950,000 USSD transfer at 3am. What's the risk?",
    "Abeg, my account don block, wetin happen?",
    "Customer earns ₦220,000/month, bureau score 610, wants ₦300,000 loan.",
    "What are the CBN Tier 2 account KYC requirements?",
    "Three transfers of ₦490,000 each in one hour — is this structuring?",
    "Oga, dem chop my ₦50k twice this morning. What I go do?",
    "Detect SIM swap fraud patterns in Nigerian fintechs.",
]

SIMULATION_SCENARIOS = [
    "sim_swap_attack",
    "structuring_attack",
    "first_party_loan_fraud",
    "mule_chain_attack",
]


class NaijaFinAIUser(HttpUser):
    """Simulates a fintech system sending requests to NaijaFinAI."""
    wait_time = between(0.5, 2.0)  # 0.5–2s between tasks

    @task(5)
    def fraud_analyze_low_risk(self):
        """High frequency — most transactions are legit."""
        self.client.post(
            "/api/fraud/analyze",
            json={"transaction": _tx("low")},
            name="/api/fraud/analyze [low]",
        )

    @task(3)
    def fraud_analyze_high_risk(self):
        """Medium frequency — suspicious transactions."""
        self.client.post(
            "/api/fraud/analyze",
            json={"transaction": _tx("high")},
            name="/api/fraud/analyze [high]",
        )

    @task(1)
    def fraud_analyze_critical(self):
        """Low frequency — critical fraud cases."""
        self.client.post(
            "/api/fraud/analyze",
            json={"transaction": _tx("critical")},
            name="/api/fraud/analyze [critical]",
        )

    @task(3)
    def loan_eligibility(self):
        payload = random.choice(LOAN_PAYLOADS)
        self.client.post(
            "/api/loans/eligibility",
            json=payload,
            name="/api/loans/eligibility",
        )

    @task(2)
    def chat_message(self):
        self.client.post(
            "/api/chat",
            json={
                "message": random.choice(CHAT_MESSAGES),
                "history": [],
                "provider": "groq",
                "stream": False,
            },
            name="/api/chat",
        )

    @task(2)
    def run_simulation(self):
        self.client.post(
            "/api/simulate/run",
            json={"scenario_id": random.choice(SIMULATION_SCENARIOS)},
            name="/api/simulate/run",
        )

    @task(1)
    def drift_report(self):
        self.client.get("/api/fraud/drift", name="/api/fraud/drift")

    @task(1)
    def health_check(self):
        self.client.get("/api/health", name="/api/health")

    @task(1)
    def eval_run(self):
        self.client.post(
            "/api/eval/run",
            json={"use_synthetic": True, "provider": "groq"},
            name="/api/eval/run",
        )

    @task(1)
    def ab_experiments(self):
        self.client.get("/api/ab/experiments", name="/api/ab/experiments")

    @task(1)
    def case_list(self):
        self.client.get("/api/cases/list", name="/api/cases/list")
