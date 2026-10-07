from tests.conftest import ADMIN, tx


def test_v1_requires_an_api_key(client):
    r = client.post("/v1/decisions", json={"transaction": tx()})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "invalid_api_key"


def test_unknown_key_is_rejected(client):
    r = client.get("/v1/tenant", headers={"Authorization": "Bearer nfa_live_not-a-real-key"})
    assert r.status_code == 401


def test_x_api_key_header_is_accepted(client, make_tenant):
    tenant, auth = make_tenant()
    key = auth["Authorization"].split(" ", 1)[1]
    r = client.get("/v1/tenant", headers={"X-API-Key": key})
    assert r.status_code == 200 and r.json()["id"] == tenant["id"]


def test_plaintext_key_is_never_stored(client, make_tenant):
    from sqlalchemy import select
    from app import db
    _, auth = make_tenant()
    raw = auth["Authorization"].split(" ", 1)[1]
    with db.session_scope() as s:
        stored = s.scalars(select(db.ApiKey)).all()
    assert all(raw not in (k.key_hash, k.prefix) for k in stored)


def test_revoked_key_stops_working(client, make_tenant):
    tenant, auth = make_tenant()
    keys = client.get(f"/v1/admin/tenants/{tenant['id']}/keys", headers=ADMIN).json()["data"]
    assert client.get("/v1/tenant", headers=auth).status_code == 200
    r = client.delete(f"/v1/admin/tenants/{tenant['id']}/keys/{keys[0]['id']}", headers=ADMIN)
    assert r.status_code == 200
    assert client.get("/v1/tenant", headers=auth).status_code == 401


def test_disabled_tenant_is_forbidden(client, make_tenant):
    tenant, auth = make_tenant()
    client.patch(f"/v1/admin/tenants/{tenant['id']}", json={"active": False}, headers=ADMIN)
    assert client.get("/v1/tenant", headers=auth).status_code == 403


def test_admin_api_rejects_wrong_token(client):
    r = client.post("/v1/admin/tenants", json={"name": "x"}, headers={"X-Admin-Token": "nope"})
    assert r.status_code == 401


def test_admin_api_is_hidden_when_no_token_configured(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "admin_token", "")
    r = client.post("/v1/admin/tenants", json={"name": "x"}, headers=ADMIN)
    assert r.status_code == 404


def test_new_tenants_default_to_shadow_mode(client):
    r = client.post("/v1/admin/tenants", json={"name": "Cautious Bank"}, headers=ADMIN)
    assert r.json()["tenant"]["mode"] == "shadow"


def test_tenant_cannot_read_another_tenants_decision(client, make_tenant):
    _, auth_a = make_tenant("A")
    _, auth_b = make_tenant("B")
    d = client.post("/v1/decisions", json={"transaction": tx()}, headers=auth_a).json()
    assert client.get(f"/v1/decisions/{d['id']}", headers=auth_a).status_code == 200
    assert client.get(f"/v1/decisions/{d['id']}", headers=auth_b).status_code == 404
    assert client.post(f"/v1/decisions/{d['id']}/labels", json={"label": "fraud"}, headers=auth_b).status_code == 404
    assert client.get("/v1/decisions", headers=auth_b).json()["data"] == []


def test_same_transaction_id_is_independent_per_tenant(client, make_tenant):
    _, auth_a = make_tenant("A")
    _, auth_b = make_tenant("B")
    a = client.post("/v1/decisions", json={"transaction": tx()}, headers=auth_a)
    b = client.post("/v1/decisions", json={"transaction": tx(amount=99_000)}, headers=auth_b)
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
