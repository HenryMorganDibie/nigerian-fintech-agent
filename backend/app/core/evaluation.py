"""
Evaluation Harness
===================
Synthetic Nigerian fraud dataset + precision/recall/F1/confusion matrix scoring.
Used to validate the Bayesian signal engine against labelled examples.
"""

from datetime import datetime, timezone
from app.core.nigeria_intelligence import evaluate_transaction
from app.core.bayesian_scorer import bayesian_fraud_score, BAYESIAN_SIGNAL_MAP
from app.models.schemas import EvalSample, Transaction, SignalMetrics, EvalRunResponse
from app.core.config import settings
from collections import defaultdict
import uuid


# ── Synthetic Dataset ────────────────────────────────────────────────────────
# 40 samples: 20 fraud, 20 legit — covering major Nigerian fraud typologies

def build_synthetic_dataset() -> list[EvalSample]:
    now = datetime.now(timezone.utc)

    def tx(**kwargs) -> Transaction:
        defaults = dict(
            transaction_id=str(uuid.uuid4())[:8],
            amount=50000, timestamp=now,
            sender_account="0123456789",
            recipient_account="9876543210",
            channel="transfer",
            is_new_recipient=False, is_new_device=False,
            is_agent_terminal=False, is_pos=False,
            is_post_loan_disbursement=False,
            device_changed_hours_ago=None,
            sim_replaced_hours_ago=None,
            transactions_last_hour=0,
            agent_tx_count_last_hour=0,
            bvn_verified=True, nin_bvn_match=True,
            narration="", recent_outbound_ngn=0,
            recent_inbound_from_same_ngn=0,
        )
        defaults.update(kwargs)
        return Transaction(**defaults)

    fraud_cases = [
        # SIM swap + USSD at 3am
        EvalSample(transaction_id="F001", label="fraud", transaction=tx(
            amount=95000, channel="ussd",
            timestamp=datetime(2025, 5, 1, 3, 12, tzinfo=timezone.utc),
            sim_replaced_hours_ago=18, is_new_recipient=True,
        )),
        # Structuring — just under ₦1M
        EvalSample(transaction_id="F002", label="fraud", transaction=tx(
            amount=998500, channel="transfer",
        )),
        # NIN-BVN mismatch
        EvalSample(transaction_id="F003", label="fraud", transaction=tx(
            amount=250000, nin_bvn_match=False,
        )),
        # Agent velocity spike
        EvalSample(transaction_id="F004", label="fraud", transaction=tx(
            amount=45000, channel="agent", is_agent_terminal=True,
            agent_tx_count_last_hour=28,
        )),
        # Round trip layering
        EvalSample(transaction_id="F005", label="fraud", transaction=tx(
            amount=500000, recent_outbound_ngn=500000,
            recent_inbound_from_same_ngn=495000,
        )),
        # Scam keywords
        EvalSample(transaction_id="F006", label="fraud", transaction=tx(
            amount=150000, narration="forex investment profit returns urgent",
        )),
        # First-party loan fraud
        EvalSample(transaction_id="F007", label="fraud", transaction=tx(
            amount=200000, is_post_loan_disbursement=True,
            is_new_recipient=True, transactions_last_hour=1,
        )),
        # Split transactions
        EvalSample(transaction_id="F008", label="fraud", transaction=tx(
            amount=350000, transactions_last_hour=4,
        )),
        # Device change before large transfer
        EvalSample(transaction_id="F009", label="fraud", transaction=tx(
            amount=180000, is_new_device=True, device_changed_hours_ago=3,
        )),
        # SIM swap weekend midnight
        EvalSample(transaction_id="F010", label="fraud", transaction=tx(
            amount=75000, channel="ussd",
            timestamp=datetime(2025, 5, 3, 2, 45, tzinfo=timezone.utc),
            sim_replaced_hours_ago=30,
        )),
        # Unverified BVN + large
        EvalSample(transaction_id="F011", label="fraud", transaction=tx(
            amount=300000, bvn_verified=False,
        )),
        # POS above limit
        EvalSample(transaction_id="F012", label="fraud", transaction=tx(
            amount=200000, channel="pos", is_pos=True,
        )),
        # Multiple signals combined
        EvalSample(transaction_id="F013", label="fraud", transaction=tx(
            amount=950000, nin_bvn_match=False, is_new_recipient=True,
            timestamp=datetime(2025, 5, 2, 4, 0, tzinfo=timezone.utc),
            channel="ussd",
        )),
        # Agent + scam narration
        EvalSample(transaction_id="F014", label="fraud", transaction=tx(
            amount=80000, is_agent_terminal=True,
            agent_tx_count_last_hour=22,
            narration="double your money investment",
        )),
        # Round trip + structuring
        EvalSample(transaction_id="F015", label="fraud", transaction=tx(
            amount=997000, recent_outbound_ngn=997000,
            recent_inbound_from_same_ngn=990000,
        )),
        # Device change + new recipient after hours
        EvalSample(transaction_id="F016", label="fraud", transaction=tx(
            amount=120000, is_new_device=True, device_changed_hours_ago=2,
            is_new_recipient=True,
            timestamp=datetime(2025, 5, 5, 3, 30, tzinfo=timezone.utc),
        )),
        # Loan fraud + unverified BVN
        EvalSample(transaction_id="F017", label="fraud", transaction=tx(
            amount=500000, is_post_loan_disbursement=True,
            bvn_verified=False, is_new_recipient=True,
            transactions_last_hour=2,
        )),
        # SIM swap + device change
        EvalSample(transaction_id="F018", label="fraud", transaction=tx(
            amount=65000, sim_replaced_hours_ago=6,
            is_new_device=True, device_changed_hours_ago=5,
            channel="ussd",
        )),
        # Scam narration + after hours
        EvalSample(transaction_id="F019", label="fraud", transaction=tx(
            amount=200000,
            timestamp=datetime(2025, 5, 4, 2, 0, tzinfo=timezone.utc),
            narration="oga approved urgent transfer lottery winnings",
        )),
        # Split + agent
        EvalSample(transaction_id="F020", label="fraud", transaction=tx(
            amount=250000, transactions_last_hour=5,
            is_agent_terminal=True, agent_tx_count_last_hour=15,
        )),
    ]

    legit_cases = [
        EvalSample(transaction_id="L001", label="legit", transaction=tx(amount=5000, channel="transfer")),
        EvalSample(transaction_id="L002", label="legit", transaction=tx(amount=50000, channel="web")),
        EvalSample(transaction_id="L003", label="legit", transaction=tx(amount=100000, channel="mobile")),
        EvalSample(transaction_id="L004", label="legit", transaction=tx(amount=15000, channel="pos", is_pos=True)),
        EvalSample(transaction_id="L005", label="legit", transaction=tx(amount=8000, channel="ussd")),
        EvalSample(transaction_id="L006", label="legit", transaction=tx(amount=200000, channel="transfer", narration="school fees payment")),
        EvalSample(transaction_id="L007", label="legit", transaction=tx(amount=450000, channel="transfer", narration="rent payment Lekki")),
        EvalSample(transaction_id="L008", label="legit", transaction=tx(amount=30000, channel="mobile", is_new_recipient=False)),
        EvalSample(transaction_id="L009", label="legit", transaction=tx(amount=75000, channel="web", narration="supplier payment")),
        EvalSample(transaction_id="L010", label="legit", transaction=tx(amount=12000, channel="ussd",
            timestamp=datetime(2025, 5, 6, 14, 0, tzinfo=timezone.utc))),
        EvalSample(transaction_id="L011", label="legit", transaction=tx(amount=60000, channel="transfer")),
        EvalSample(transaction_id="L012", label="legit", transaction=tx(amount=3500, channel="pos", is_pos=True)),
        EvalSample(transaction_id="L013", label="legit", transaction=tx(amount=25000, channel="mobile", narration="airtime recharge")),
        EvalSample(transaction_id="L014", label="legit", transaction=tx(amount=500000, channel="transfer", narration="property deposit")),
        EvalSample(transaction_id="L015", label="legit", transaction=tx(amount=18000, channel="transfer")),
        EvalSample(transaction_id="L016", label="legit", transaction=tx(amount=80000, channel="web", narration="business payment")),
        EvalSample(transaction_id="L017", label="legit", transaction=tx(amount=45000, channel="mobile")),
        EvalSample(transaction_id="L018", label="legit", transaction=tx(amount=120000, channel="transfer", narration="family support")),
        EvalSample(transaction_id="L019", label="legit", transaction=tx(amount=7500, channel="ussd",
            timestamp=datetime(2025, 5, 7, 10, 30, tzinfo=timezone.utc))),
        EvalSample(transaction_id="L020", label="legit", transaction=tx(amount=35000, channel="transfer")),
    ]

    return fraud_cases + legit_cases


# ── Evaluation Runner ─────────────────────────────────────────────────────────

def run_evaluation(samples: list[EvalSample], provider: str | None = None) -> EvalRunResponse:
    provider = provider or settings.default_llm_provider
    threshold = 0.40  # posterior probability threshold for fraud classification

    tp = fp = tn = fn = 0
    signal_tp: dict[str, int] = defaultdict(int)
    signal_fp: dict[str, int] = defaultdict(int)
    signal_fn: dict[str, int] = defaultdict(int)

    for sample in samples:
        tx = sample.transaction
        # Run heuristic engine to get signal names
        heuristic = evaluate_transaction(
            amount=tx.amount,
            channel=tx.channel,
            hour_of_day=tx.timestamp.hour,
            day_of_week=tx.timestamp.weekday(),
            is_new_recipient=tx.is_new_recipient,
            is_new_device=tx.is_new_device,
            device_changed_hours_ago=tx.device_changed_hours_ago,
            sim_replaced_hours_ago=tx.sim_replaced_hours_ago,
            transactions_last_hour=tx.transactions_last_hour,
            bvn_verified=tx.bvn_verified,
            nin_bvn_match=tx.nin_bvn_match,
            narration=tx.narration,
            is_post_loan_disbursement=tx.is_post_loan_disbursement,
            is_agent_terminal=tx.is_agent_terminal,
            agent_tx_count_last_hour=tx.agent_tx_count_last_hour,
            is_pos=tx.is_pos,
            recent_outbound_ngn=tx.recent_outbound_ngn,
            recent_inbound_from_same_ngn=tx.recent_inbound_from_same_ngn,
        )

        triggered = [s.name for s in heuristic.triggered_signals]
        bayes = bayesian_fraud_score(triggered)
        predicted_fraud = bayes.posterior_fraud_probability >= threshold
        actual_fraud = sample.label == "fraud"

        if predicted_fraud and actual_fraud:
            tp += 1
        elif predicted_fraud and not actual_fraud:
            fp += 1
        elif not predicted_fraud and actual_fraud:
            fn += 1
        else:
            tn += 1

        # Per-signal metrics
        for sig_name in triggered:
            if actual_fraud:
                signal_tp[sig_name] += 1
            else:
                signal_fp[sig_name] += 1
        # Count FN for signals that should have triggered but didn't
        if actual_fraud and not predicted_fraud:
            for sig_name in BAYESIAN_SIGNAL_MAP:
                if sig_name not in triggered:
                    signal_fn[sig_name] += 1

    # Overall metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy  = (tp + tn) / len(samples) if samples else 0.0

    # Per-signal metrics
    all_signals = set(signal_tp) | set(signal_fp) | set(signal_fn)
    per_signal = []
    for sig in sorted(all_signals):
        s_tp = signal_tp.get(sig, 0)
        s_fp = signal_fp.get(sig, 0)
        s_fn = signal_fn.get(sig, 0)
        s_prec = s_tp / (s_tp + s_fp) if (s_tp + s_fp) > 0 else 0.0
        s_rec  = s_tp / (s_tp + s_fn) if (s_tp + s_fn) > 0 else 0.0
        s_f1   = 2 * s_prec * s_rec / (s_prec + s_rec) if (s_prec + s_rec) > 0 else 0.0
        per_signal.append(SignalMetrics(
            signal=sig,
            true_positives=s_tp, false_positives=s_fp, false_negatives=s_fn,
            precision=round(s_prec, 3), recall=round(s_rec, 3), f1=round(s_f1, 3),
        ))

    return EvalRunResponse(
        total_samples=len(samples),
        fraud_samples=sum(1 for s in samples if s.label == "fraud"),
        legit_samples=sum(1 for s in samples if s.label == "legit"),
        overall_precision=round(precision, 3),
        overall_recall=round(recall, 3),
        overall_f1=round(f1, 3),
        accuracy=round(accuracy, 3),
        confusion_matrix={"TP": tp, "FP": fp, "TN": tn, "FN": fn},
        per_signal_metrics=per_signal,
        provider_used=provider,
    )
