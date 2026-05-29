"""
NaijaFinAI Load Testing — Locust
==================================
Tests transaction volume handling under realistic Nigerian fintech load.

Install: pip install locust
Run:     locust -f locustfile.py --host=https://nigerian-fintech-agent-production.up.railway.app
         Then open http://localhost:8089

Scenarios modelled:
- Typical daytime transaction volume
- End-of-month salary disbursement spike
- Friday night social engineering surge
"""

from locust import HttpUser, task, between
from datetime import datetime, timezone
import random
import uuid


# ── Sample Nigerian transaction data ─────────────────────────────────────────

CHANNELS     = ["transfer", "ussd", "mobile", "pos", "web", "agent"]
NARRATIONS   = [
    "school fees payment", "rent Lagos Island", "market goods payment",
    "salary advance repayment", "airtime recharge", "family support Abuja",
    "supplier payment", "DSTV subscription", "EKEDC electricity bill",
    "fuel purchase Ikoyi", ""
]
FRAUD_NARRATIONS = [
    "forex investment profit urgent", "oga approved transfer",
    "lottery winnings withdrawal", "double your money returns",
]

def make_transaction(is_suspicious=False):
    hour = random.choice([1, 2, 3]) if is_suspicious else random.randint(8, 20)
    return {
        "transaction": {
            "transaction_id": str(uuid.uuid4())[:12],
            "amount": random.choice([998500, 997000]) if is_suspicious else random.randint(5000, 500000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sender_account":    "".join([str(random.randint(0,9)) for _ in range(10)]),
            "recipient_account": "".join([str(random.randint(0,9)) for _ in range(10)]),
            "channel": "ussd" if is_suspicious else random.choice(CHANNELS),
            "is_new_recipient": is_suspicious,
            "is_new_device": is_suspicious and random.random() > 0.5,
            "is_agent_terminal": False,
            "is_pos": False,
            "is_post_loan_disbursement": False,
            "device_changed_hours_ago": 3 if is_suspicious else None,
            "sim_replaced_hours_ago": 20 if is_suspicious else None,
            "transactions_last_hour": random.randint(4, 8) if is_suspicious else random.randint(0, 2),
            "agent_tx_count_last_hour": 0,
            "bvn_verified": not is_suspicious,
            "nin_bvn_match": not is_suspicious,
            "narration": random.choice(FRAUD_NARRATIONS) if is_suspicious else random.choice(NARRATIONS),
            "recent_outbound_ngn": 0,
            "recent_inbound_from_same_ngn": 0,
        }
    }


class NaijaFintechUser(HttpUser):
    """Simulates a Nigerian fintech processing real-time transactions."""
    wait_time = between(0.5, 2.0)

    @task(6)
    def analyze_legit_transaction(self):
        """Most transactions are legitimate."""
        self.client.post(
            "/api/fraud/analyze",
            json=make_transaction(is_suspicious=False),
            headers={"Content-Type": "application/json"},
        )

    @task(2)
    def analyze_suspicious_transaction(self):
        """Some transactions are suspicious."""
        self.client.post(
            "/api/fraud/analyze",
            json=make_transaction(is_suspicious=True),
            headers={"Content-Type": "application/json"},
        )

    @task(1)
    def check_loan_eligibility(self):
        self.client.post(
            "/api/loans/eligibility",
            json={
                "monthly_income_ngn": random.choice([80000, 150000, 250000, 500000]),
                "employment_status": random.choice(["employed", "self_employed"]),
                "bvn_verified": True,
                "nin_verified": True,
                "account_tier": random.choice(["tier1", "tier2", "tier3"]),
                "credit_bureau_score": random.randint(400, 800),
                "existing_loan_count": random.randint(0, 2),
                "requested_amount_ngn": random.choice([50000, 100000, 250000, 500000]),
                "tenor_months": random.choice([3, 6, 12]),
                "loan_purpose": "working capital",
            },
            headers={"Content-Type": "application/json"},
        )

    @task(1)
    def health_check(self):
        self.client.get("/api/health")

    @task(1)
    def check_drift(self):
        self.client.get("/api/fraud/drift")


class SalaryDisbursementSpike(HttpUser):
    """
    Simulates end-of-month salary disbursement volume spike.
    Higher frequency, mostly legitimate large transfers.
    """
    wait_time = between(0.1, 0.5)

    @task
    def salary_transfer(self):
        self.client.post(
            "/api/fraud/analyze",
            json=make_transaction(is_suspicious=False),
            headers={"Content-Type": "application/json"},
        )


# ── Run config ────────────────────────────────────────────────────────────────
# locust -f locustfile.py --host=https://nigerian-fintech-agent-production.up.railway.app
#   --users 50 --spawn-rate 5 --run-time 2m
#
# For local testing:
#   --host=http://localhost:8000
