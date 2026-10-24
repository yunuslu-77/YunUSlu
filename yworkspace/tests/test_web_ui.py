import threading
import time

import pytest
from fastapi.testclient import TestClient

from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.interfaces.web.server import create_app
from yworkspace.models.scripted import ScriptedProvider, say


def scripted_factory(scripts):
    def factory(project, cfg, approver, on_event):
        sess = build_session(project, cfg, approver, on_event)
        provs = {r: ScriptedProvider(list(s)) for r, s in scripts.items()}
        sess.engine.provider_for = lambda role: provs.setdefault(role, ScriptedProvider([]))
        sess.engine.profile_for = lambda role: None
        return sess
    return factory


SCRIPTS = {
    "analyst": [say("", ("plan_set_spec", {"spec": "# Goal\nhello"}))],
    "architect": [say("", ("plan_add_tasks", {"tasks": [{"title": "hello module"}]}))],
    "developer": [
        say("", ("create", {"path": "hello.py", "content": "def hi():\n    return 'merhaba'\n"}),
            ("create", {"path": "test_hello.py", "content": "from hello import hi\n\n\ndef test_hi():\n    assert hi() == 'merhaba'\n"})),
        say("", ("run", {"command": "python -m pytest -q"})),
        say("", ("plan_update", {"status": "done", "evidence": "1 passed"})), say("done")],
}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    cfg = Config(sandbox="local", projects_dir=str(tmp_path / "projects"), quality="economy", autonomy="milestones")
    return create_app(cfg, token="tok", session_factory=scripted_factory(SCRIPTS))


def test_api_auth_and_run(app):
    c = TestClient(app)
    assert c.get("/api/status").status_code == 401
    h = {"X-YW-Token": "tok"}
    assert c.post("/api/projects", json={"name": "Merhaba App"}, headers=h).json() == {"name": "Merhaba-App"}
    assert [p["name"] for p in c.get("/api/projects", headers=h).json()] == ["Merhaba-App"]
    assert c.get("/api/projects/..%2Fetc/state", headers=h).status_code in (400, 404)
    assert c.post("/api/keys", json={"name": "bad", "value": "x"}, headers=h).status_code == 400
    # run with approvals answered through the API
    c.post("/api/run", json={"project": "Merhaba-App", "goal": "hello", "autonomy": "milestones"}, headers=h)
    runner = app.state.runner
    deadline = time.time() + 30
    while runner.busy() and time.time() < deadline:
        for rid in list(runner.approver.pending):
            c.post("/api/approve", json={"id": rid, "ok": True}, headers=h)
        time.sleep(0.1)
    st = c.get("/api/projects/Merhaba-App/state", headers=h).json()
    assert st["phase"] == "done", st
    kinds = [e["kind"] for e in app.state.hub.backlog]
    assert "approval" in kinds and "run_finished" in kinds
    assert "hello.py" in c.get("/api/projects/Merhaba-App/files?path=.", headers=h).json()["listing"]


def test_ui_in_browser(app, tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    while not server.started:
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    TestClient(app).post("/api/projects", json={"name": "ui"}, headers={"X-YW-Token": "tok"})
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 390, "height": 844})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/?t=tok")
        page.wait_for_selector("#projectList li")
        page.click("#projectList li")
        page.fill("#goal", "merhaba modülü yaz")
        page.click("#runBtn")
        page.wait_for_selector(".approval", timeout=20000)
        assert "Proje tanımını onaylıyor musun?" in page.inner_text(".approval h4")
        page.click(".approval button.primary")
        page.wait_for_selector(".approval", timeout=20000)
        page.click(".approval button.primary")
        page.wait_for_selector("#feed li.done", timeout=30000)
        assert "Bitti" in page.inner_text("#feed li.done")
        page.wait_for_function("document.querySelector('#tasks').innerText.includes('hello module')")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "no horizontal scroll on phone"
        page.click("#langBtn")
        assert page.inner_text("#runBtn") == "Start"
        assert not errors, errors
        b.close()
    server.should_exit = True
