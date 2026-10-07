from sqlalchemy import delete, select, update

from tests.conftest import tx


def _decide(client, auth, n=3):
    for i in range(n):
        client.post("/v1/decisions", json={"transaction": tx(transaction_id=f"TX-{i}")}, headers=auth)


def test_chain_is_valid_after_normal_activity(client, make_tenant):
    _, auth = make_tenant()
    _decide(client, auth)
    v = client.get("/v1/audit/verify", headers=auth).json()
    # tenant.created + api_key.created + 3 decisions
    assert v["valid"] is True and v["events_checked"] == 5


def test_altering_an_event_breaks_the_chain(client, make_tenant):
    from app import db
    tenant, auth = make_tenant()
    _decide(client, auth)
    with db.session_scope() as s:
        ev = s.scalars(select(db.AuditEvent).where(db.AuditEvent.tenant_id == tenant["id"],
                                                   db.AuditEvent.seq == 4)).one()
        s.execute(update(db.AuditEvent).where(db.AuditEvent.id == ev.id)
                  .values(payload={**ev.payload, "amount_ngn": 1.0}))
    v = client.get("/v1/audit/verify", headers=auth).json()
    assert v["valid"] is False and v["broken_at_seq"] == 4


def test_deleting_an_event_breaks_the_chain(client, make_tenant):
    from app import db
    tenant, auth = make_tenant()
    _decide(client, auth)
    with db.session_scope() as s:
        s.execute(delete(db.AuditEvent).where(db.AuditEvent.tenant_id == tenant["id"], db.AuditEvent.seq == 3))
    v = client.get("/v1/audit/verify", headers=auth).json()
    assert v["valid"] is False and v["broken_at_seq"] == 3


def test_chains_are_per_tenant(client, make_tenant):
    _, auth_a = make_tenant("A")
    _, auth_b = make_tenant("B")
    _decide(client, auth_a, 4)
    assert client.get("/v1/audit/verify", headers=auth_b).json()["events_checked"] == 2


def test_audit_payload_holds_no_raw_account_numbers(client, make_tenant):
    from app import db
    tenant, auth = make_tenant()
    _decide(client, auth, 1)
    with db.session_scope() as s:
        payloads = [e.payload for e in s.scalars(select(db.AuditEvent)).all()]
    assert "0123456789" not in str(payloads)
