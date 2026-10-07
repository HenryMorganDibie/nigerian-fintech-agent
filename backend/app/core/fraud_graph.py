"""
Fraud Graph Layer
==================
Detects network-level fraud patterns:
- Shared devices across multiple accounts
- Circular money flows (A→B→C→A)
- Mule account clusters (many senders → one receiver)
- Beneficiary risk propagation

Uses in-memory graph. Can be backed by Neo4j or NetworkX for production.
"""

from collections import defaultdict
from typing import Optional
import time


# ── In-memory graph storage, partitioned per tenant ───────────────────────────
class _TenantGraph:
    def __init__(self):
        self.device_to_accounts: dict[str, set] = defaultdict(set)    # device → {account_ids}
        self.account_to_devices: dict[str, set] = defaultdict(set)    # account → {device_ids}
        self.transfer_graph: dict[str, list] = defaultdict(list)      # sender → [(recipient, amount, ts)]
        self.beneficiary_inflows: dict[str, list] = defaultdict(list) # account → [sender_ids]
        self.flagged_accounts: set = set()                             # known fraud accounts


_graphs: dict[str, _TenantGraph] = defaultdict(_TenantGraph)


def _graph(tenant_id: str) -> _TenantGraph:
    return _graphs[tenant_id]


def reset_graphs():
    """Test helper: drop every tenant's graph."""
    _graphs.clear()


# ── Graph Updates ─────────────────────────────────────────────────────────────

def record_transaction_edge(
    sender_account: str,
    recipient_account: str,
    amount: float,
    device_fingerprint: Optional[str] = None,
    tenant_id: str = "demo",
):
    """Record a transaction edge in the tenant's fraud graph."""
    g = _graph(tenant_id)
    ts = time.time()
    g.transfer_graph[sender_account].append((recipient_account, amount, ts))
    g.beneficiary_inflows[recipient_account].append(sender_account)

    # Keep last 100 edges per account
    if len(g.transfer_graph[sender_account]) > 100:
        g.transfer_graph[sender_account] = g.transfer_graph[sender_account][-100:]
    if len(g.beneficiary_inflows[recipient_account]) > 100:
        g.beneficiary_inflows[recipient_account] = g.beneficiary_inflows[recipient_account][-100:]

    if device_fingerprint:
        g.device_to_accounts[device_fingerprint].add(sender_account)
        g.account_to_devices[sender_account].add(device_fingerprint)


def flag_account(account_id: str, tenant_id: str = "demo"):
    _graph(tenant_id).flagged_accounts.add(account_id)


# ── Graph Risk Analysis ───────────────────────────────────────────────────────

def analyze_graph_risk(
    sender_account: str,
    recipient_account: str,
    device_fingerprint: Optional[str] = None,
    amount: float = 0,
    tenant_id: str = "demo",
) -> dict:
    """
    Analyze transaction for graph-level fraud signals.
    Returns graph_risk_score (0-100) and detected patterns.
    """
    g = _graph(tenant_id)
    patterns = []
    score = 0

    # 1. Shared device across multiple accounts
    if device_fingerprint:
        accounts_on_device = g.device_to_accounts.get(device_fingerprint, set())
        if len(accounts_on_device) > 2:
            score += 35
            patterns.append({
                "type": "SHARED_DEVICE",
                "detail": f"Device used by {len(accounts_on_device)} accounts — possible account farm",
                "severity": "high",
            })
        elif len(accounts_on_device) > 1:
            score += 15
            patterns.append({
                "type": "SHARED_DEVICE",
                "detail": f"Device shared across {len(accounts_on_device)} accounts",
                "severity": "medium",
            })

    # 2. Recipient is a known fraud account
    if recipient_account in g.flagged_accounts:
        score += 50
        patterns.append({
            "type": "FLAGGED_RECIPIENT",
            "detail": "Recipient account is flagged as known fraud/mule account",
            "severity": "critical",
        })

    # 3. Sender is a known fraud account
    if sender_account in g.flagged_accounts:
        score += 45
        patterns.append({
            "type": "FLAGGED_SENDER",
            "detail": "Sender account is flagged as fraud-associated",
            "severity": "critical",
        })

    # 4. Mule cluster detection — many unique senders to same recipient
    inflows = g.beneficiary_inflows.get(recipient_account, [])
    unique_senders = len(set(inflows))
    if unique_senders > 15:
        score += 40
        patterns.append({
            "type": "MULE_CLUSTER",
            "detail": f"Recipient received from {unique_senders} unique senders — mule account pattern",
            "severity": "critical",
        })
    elif unique_senders > 8:
        score += 20
        patterns.append({
            "type": "HIGH_INFLOW_CONCENTRATION",
            "detail": f"Recipient has {unique_senders} unique senders — elevated risk",
            "severity": "high",
        })

    # 5. Circular flow detection — does money come back?
    outflows = g.transfer_graph.get(recipient_account, [])
    circular = any(out[0] == sender_account for out in outflows[-10:])
    if circular:
        score += 40
        patterns.append({
            "type": "CIRCULAR_FLOW",
            "detail": "Circular flow detected: funds returned to original sender via recipient — possible layering",
            "severity": "critical",
        })

    # 6. Fan-out pattern — sender sending to many recipients quickly
    recent_ts = time.time() - 3600  # last 1 hour
    recent_outflows = [o for o in g.transfer_graph.get(sender_account, []) if o[2] > recent_ts]
    unique_recipients_1h = len(set(o[0] for o in recent_outflows))
    if unique_recipients_1h > 8:
        score += 30
        patterns.append({
            "type": "FAN_OUT",
            "detail": f"Sender distributed to {unique_recipients_1h} unique recipients in 1 hour — fan-out smurfing",
            "severity": "high",
        })

    return {
        "graph_risk_score": min(score, 100),
        "patterns_detected": patterns,
        "graph_stats": {
            "recipient_unique_senders": unique_senders,
            "sender_devices": len(g.account_to_devices.get(sender_account, set())),
            "accounts_on_device": len(g.device_to_accounts.get(device_fingerprint, set())) if device_fingerprint else 0,
        }
    }
