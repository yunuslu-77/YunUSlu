import json

from app import emails
from conftest import csrf, last_link, signup
from fastapi.testclient import TestClient


def test_tenant_isolation_and_invites(client):
    signup(client, "owner@example.com", org="Alpha")
    bob = TestClient(client.app)
    signup(bob, "bob@example.com", org="Beta")
    # Bob cannot act on Alpha's members
    alpha_members = client.get("/members").text
    assert "owner@example.com" in alpha_members and "bob@example.com" not in alpha_members
    r = bob.post("/members/1/remove", data={"csrf": csrf(bob, "/members")})
    assert r.status_code == 404
    # invite Bob as admin into Alpha
    client.post("/members/invite", data={"csrf": csrf(client, "/members"), "email": "bob@example.com", "role": "admin"})
    link = last_link("invite/accept")
    assert bob.get(link).status_code == 200
    assert "Alpha" in bob.get("/dashboard").text
    # the last owner cannot be removed or demoted
    r = client.post("/members/1/role", data={"csrf": csrf(client, "/members"), "role": "member"}, follow_redirects=False)
    assert "last_owner" in r.headers["location"]


def test_invite_requires_matching_email(client):
    signup(client, "owner@example.com")
    client.post("/members/invite", data={"csrf": csrf(client, "/members"), "email": "x@example.com"})
    link = last_link("invite/accept")
    eve = TestClient(client.app)
    signup(eve, "eve@example.com")
    assert "link_invalid" in eve.get(link, follow_redirects=False).headers["location"]


def test_fake_checkout_webhook_and_cancel(client):
    signup(client)
    r = client.post("/billing/checkout/pro", data={"csrf": csrf(client, "/billing")}, follow_redirects=False)
    assert r.headers["location"].startswith("/billing/fake-pay")
    page = client.get(r.headers["location"]).text
    assert "TEST MODE" in page
    client.post("/billing/fake-pay", data={"csrf": csrf(client, "/billing"), "plan": "pro"})
    assert "<strong>pro</strong>" in client.get("/billing").text
    client.post("/billing/cancel", data={"csrf": csrf(client, "/billing")})
    assert "dönem sonunda" in client.get("/billing").text


def test_webhook_signature_and_idempotency(client):
    signup(client)
    provider = client.app.state.billing
    body, headers = provider.make_event(1, "pro")
    assert client.post("/billing/webhook/fake", content=body, headers=headers).json()["applied"] == 1
    assert client.post("/billing/webhook/fake", content=body, headers=headers).json()["applied"] == 0
    bad = client.post("/billing/webhook/fake", content=body, headers={"x-fake-signature": "nope"})
    assert bad.status_code == 400


def test_stripe_signature_verification(settings):
    import hashlib
    import hmac
    import time

    from app.billing import WebhookError
    from app.billing.stripe import StripeProvider
    settings.stripe_webhook_secret = "whsec_test"
    p = StripeProvider(settings)
    event = {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": "7", "customer": "cus_1", "subscription": "sub_1", "metadata": {"plan": "pro"}}}}
    body = json.dumps(event).encode()
    ts = str(int(time.time()))
    sig = hmac.new(b"whsec_test", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    ev = p.parse_webhook(body, {"stripe-signature": f"t={ts},v1={sig}"})[0]
    assert (ev.org_id, ev.plan, ev.subscription_ref) == (7, "pro", "sub_1")
    try:
        p.parse_webhook(body, {"stripe-signature": f"t={ts},v1=bad"})
        raise AssertionError("bad signature accepted")
    except WebhookError:
        pass
    old = str(int(time.time()) - 3600)
    sig_old = hmac.new(b"whsec_test", f"{old}.".encode() + body, hashlib.sha256).hexdigest()
    try:
        p.parse_webhook(body, {"stripe-signature": f"t={old},v1={sig_old}"})
        raise AssertionError("replayed event accepted")
    except WebhookError:
        pass


def test_member_cannot_upgrade(client):
    signup(client, "owner@example.com")
    client.post("/members/invite", data={"csrf": csrf(client, "/members"), "email": "m@example.com", "role": "member"})
    link = last_link("invite/accept")
    m = TestClient(client.app)
    signup(m, "m@example.com", org="Own")
    m.get(link)
    r = m.post("/billing/checkout/pro", data={"csrf": csrf(m, "/billing")})
    assert r.status_code == 403
    assert emails.OUTBOX
