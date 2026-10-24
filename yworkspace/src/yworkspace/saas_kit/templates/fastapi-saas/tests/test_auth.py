from app import emails
from conftest import csrf, last_link, signup


def test_signup_verify_logout_login(client):
    r = signup(client)
    assert r.status_code == 303 and r.headers["location"].startswith("/dashboard")
    assert "verify" in emails.OUTBOX[-1].get_content()
    page = client.get("/dashboard").text
    assert "Ayşe Kuaför" in page and "owner" in page
    assert client.get(last_link("verify")).status_code == 200
    assert "doğrulandı" in client.get("/dashboard?msg=verified").text
    client.post("/logout", data={"csrf": csrf(client, "/dashboard")})
    assert client.get("/dashboard", follow_redirects=False).headers["location"].startswith("/login")
    r = client.post("/login", data={"csrf": csrf(client), "email": "AYSE@example.com", "password": "guclu-parola-1"},
                    follow_redirects=False)
    assert r.status_code == 303


def test_signup_validation(client):
    signup(client)
    client.cookies.clear()
    assert "zaten kayıtlı" in signup(client).text
    assert "en az 8" in signup(client, "b@example.com", "kısa").text
    assert "yaygın" in signup(client, "c@example.com", "password1").text
    assert "Geçerli" in signup(client, "not-an-email").text


def test_csrf_required(client):
    r = client.post("/login", data={"email": "x@y.z", "password": "whatever1"})
    assert r.status_code == 400


def test_login_rate_limit_and_same_error(client):
    signup(client)
    client.cookies.clear()
    token = csrf(client)
    wrong_user = client.post("/login", data={"csrf": token, "email": "nobody@example.com", "password": "x" * 9})
    wrong_pw = client.post("/login", data={"csrf": token, "email": "ayse@example.com", "password": "x" * 9})
    assert wrong_user.status_code == wrong_pw.status_code == 400
    for _ in range(5):
        r = client.post("/login", data={"csrf": token, "email": "ayse@example.com", "password": "x" * 9})
    assert r.status_code == 429


def test_password_reset_logs_out_other_sessions(client, settings):
    from fastapi.testclient import TestClient
    signup(client)
    other = TestClient(client.app)
    other.cookies.update(client.cookies)
    client.cookies.clear()
    client.post("/forgot", data={"csrf": csrf(client, "/forgot"), "email": "ayse@example.com"})
    link = last_link("reset")
    token = link.split("token=")[1]
    r = client.post("/reset", data={"csrf": csrf(client, link), "token": token, "password": "yeni-parola-2"},
                    follow_redirects=False)
    assert r.headers["location"].endswith("reset_done")
    assert other.get("/dashboard", follow_redirects=False).status_code == 303  # old session is gone
    again = client.post("/reset", data={"csrf": csrf(client, link), "token": token, "password": "baska-parola-3"},
                        follow_redirects=False)
    assert "link_invalid" in again.headers["location"]  # single use
    assert client.post("/login", data={"csrf": csrf(client), "email": "ayse@example.com",
                                       "password": "yeni-parola-2"}, follow_redirects=False).status_code == 303


def test_unknown_email_reset_gives_same_answer(client):
    r = client.post("/forgot", data={"csrf": csrf(client, "/forgot"), "email": "ghost@example.com"},
                    follow_redirects=False)
    assert r.headers["location"].endswith("reset_sent")
