import threading
import time

import pytest
from fastapi.testclient import TestClient
from test_web_ui import SCRIPTS, scripted_factory

from yworkspace.config import Config
from yworkspace.interfaces.web.server import create_app
from yworkspace.remote import qr
from yworkspace.remote.devices import Devices


def test_qr_codes_decode(tmp_path):
    cv2 = pytest.importorskip("cv2")
    for text in ["HELLO", "http://192.168.1.25:8700/m/#pair=K7Q2-9XPA", "ş" * 50, "x" * 200]:
        p = tmp_path / "q.png"
        qr.png(text, p, scale=6)
        val, _pts, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(p)))
        assert val == text
    assert qr.svg("abc").startswith("<svg") and "\n" in qr.terminal("abc")
    with pytest.raises(ValueError):
        qr.encode("x" * 400)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    cfg = Config(sandbox="local", projects_dir=str(tmp_path / "projects"), quality="economy", autonomy="milestones")
    return create_app(cfg, token="tok", session_factory=scripted_factory(SCRIPTS), devices=Devices(tmp_path / "d.json"))


def test_pairing_rights_and_revoke(app):
    owner = {"X-YW-Token": "tok"}
    c = TestClient(app)
    assert c.post("/api/pair/start").status_code == 401
    p = c.post("/api/pair/start", headers=owner).json()
    assert p["link"].endswith(f"/m/#pair={p['code']}") and p["svg"].startswith("<svg")
    phone = TestClient(app)
    assert phone.post("/api/pair/claim", json={"code": "WRNG-CODE"}).status_code == 403
    r = phone.post("/api/pair/claim", json={"code": p["code"].lower(), "name": "Android"})
    assert r.status_code == 200 and "yw_device" in r.cookies
    assert TestClient(app).post("/api/pair/claim", json={"code": p["code"]}).status_code == 403  # one use only
    assert phone.get("/api/me").json()["device"]["name"] == "Android"
    owner_client = TestClient(app)
    assert owner_client.post("/api/projects", json={"name": "uzak"}, headers=owner).status_code == 200
    assert [x["name"] for x in phone.get("/api/projects").json()] == ["uzak"]
    for method, path in (("post", "/api/keys"), ("get", "/api/setup"), ("get", "/api/devices"),
                         ("post", "/api/pair/start"), ("put", "/api/config")):
        kw = {} if method == "get" else {"json": {}}
        assert getattr(phone, method)(path, **kw).status_code == 401, path
    devs = c.get("/api/devices", headers=owner).json()
    assert len(devs) == 1 and "hash" not in devs[0]
    assert c.delete(f"/api/devices/{devs[0]['id']}", headers=owner).status_code == 200
    assert phone.get("/api/projects").status_code == 401
    assert "tok" not in str(p)  # the main token is never handed to the phone


def test_bruteforce_lock(tmp_path):
    d = Devices(tmp_path / "d.json")
    code = d.new_code()
    for _ in range(10):
        assert d.claim("AAAA-AAAA", "x") is None
    assert d.claim(code, "x") is None  # locked for a minute after 10 failures


def test_phone_runs_and_approves_in_browser(app, tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    while not server.started:
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    app.state.public_url = base
    c = TestClient(app)
    c.post("/api/projects", json={"name": "telefon"}, headers={"X-YW-Token": "tok"})
    link = c.post("/api/pair/start", headers={"X-YW-Token": "tok"}).json()["link"]
    try:
        with pw.sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 393, "height": 851}, is_mobile=True, has_touch=True,
                                locale="tr-TR",
                                user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126 "
                                           "Mobile Safari/537.36")
            page = ctx.new_page()
            page.goto(base + "/m/")
            page.wait_for_selector("#unpaired:not([hidden])")
            page.goto(link)
            page.wait_for_selector("#app:not([hidden])")
            assert "Android" in page.inner_text("#who")
            assert page.input_value("#project") == "telefon"
            page.fill("#goal", "hello")
            page.click("#start")
            deadline = time.time() + 40
            while time.time() < deadline:
                if page.locator("#feed li.done").count():
                    break
                btn = page.locator(".approval button.primary")
                if btn.count():
                    btn.first.click()
                time.sleep(0.2)
            assert page.locator("#feed li.done").first.inner_text() == "Bitti ✓"
            assert page.evaluate("document.documentElement.scrollWidth") <= 393
            page.screenshot(path=str(tmp_path / "phone.png"))
            b.close()
    finally:
        server.should_exit = True
        th.join(5)
