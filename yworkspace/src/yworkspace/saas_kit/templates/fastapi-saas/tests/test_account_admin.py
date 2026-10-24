import json

from conftest import csrf, signup
from fastapi.testclient import TestClient


def test_export_and_delete(client):
    signup(client)
    data = json.loads(client.get("/account/export").content)
    assert data["user"]["email"] == "ayse@example.com" and data["teams"][0]["role"] == "owner"
    r = client.post("/account/delete", data={"csrf": csrf(client, "/account"), "confirm": "wrong@x.com"})
    assert r.status_code == 400
    r = client.post("/account/delete", data={"csrf": csrf(client, "/account"), "confirm": "ayse@example.com"},
                    follow_redirects=False)
    assert r.headers["location"].endswith("deleted")
    assert client.get("/api/me").status_code == 401


def test_admin_only_for_superadmins(client):
    signup(client, "user@example.com")
    assert client.get("/admin").status_code == 403
    boss = TestClient(client.app)
    signup(boss, "boss@example.com")
    page = boss.get("/admin").text
    assert "MRR" in page and "user@example.com" in page and "signup" in page


def test_health_ready_headers_and_language(client):
    assert client.get("/health").text == "ok"
    assert client.get("/ready").json() == {"ready": True}
    r = client.get("/login")
    assert r.headers["x-content-type-options"] == "nosniff" and "frame-ancestors 'none'" in r.headers[
        "content-security-policy"]
    client.get("/lang/en")
    assert "Log in" in client.get("/login").text
