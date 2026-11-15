"""YAi Android uygulamasının kullandığı /api uç noktaları + öğrenme/ekran araçları."""
import base64
import json

from fastapi.testclient import TestClient

from bot import schedules as S
from bot.dashboard import create_app
from bot.telegram_ui import setup_code
from bot.tools import REGISTRY, ToolContext
from bot.tools import phone as phone_tools


def client(app):
    c = TestClient(create_app(app))
    c.headers["Authorization"] = "Bearer " + app.cfg.dashboard_token
    return c


def test_auth_required(app):
    c = TestClient(create_app(app))
    assert c.get("/api/status").status_code == 401
    assert c.get("/api/status", headers={"Authorization": "Bearer yanlis"}).status_code == 401
    assert client(app).get("/api/status").json()["bot_name"] == "YAi"


def test_chat_and_history(app, llm):
    llm.push("Merhaba, nasıl yardım edebilirim?")
    c = client(app)
    assert c.post("/api/chat", json={"text": "selam"}).json()["reply"].startswith("Merhaba")
    h = c.get("/api/history").json()
    assert [m["role"] for m in h] == ["user", "model"]
    assert c.post("/api/chat", json={"text": "  "}).status_code == 400


def test_approvals_via_api(app, llm):
    llm.push([("gmail_send", {"to": "a@b.com", "subject": "S", "body": "B"})], "Onay bekliyorum")
    c = client(app)
    c.post("/api/chat", json={"text": "mail at"})
    pend = c.get("/api/approvals").json()
    assert len(pend) == 1 and "a@b.com" in pend[0]["summary"]
    assert "İptal" in c.post(f"/api/approvals/{pend[0]['id']}", json={"approve": False}).json()["reply"]
    assert c.get("/api/approvals").json() == []


def test_schedules_memories_settings(app):
    c = client(app)
    r = c.post("/api/schedules", json={"when": "hafta içi 08:00", "task": "Brifing", "kind": "prompt"}).json()
    assert r["id"] and "1-5" in r["when"]
    assert c.post("/api/schedules", json={"when": "saçma", "task": "x"}).status_code == 400
    assert c.get("/api/schedules").json()[0]["payload"] == "Brifing"
    c.delete(f"/api/schedules/{r['id']}")
    assert S.list_schedules(app.db) == []
    mid = c.post("/api/memories", json={"fact": "Kedisi var"}).json()["id"]
    assert c.get("/api/memories").json()[0]["fact"] == "Kedisi var"
    c.delete(f"/api/memories/{mid}")
    assert c.post("/api/settings", json={"voice_replies": True, "hack": True}).json()["voice_replies"] is True
    assert app.db.get("hack") is None
    assert any(a["name"] == "operator" for a in c.get("/api/agents").json())
    assert c.post("/api/agents/active", json={"name": "yazar"}).json()["active"] == "yazar"
    assert "month" in c.get("/api/costs").json()


def test_setup_code_roundtrip(app):
    code = setup_code("http://100.1.2.3:8080/", "tok", "ptok")
    raw = base64.urlsafe_b64decode(code[5:] + "==")
    assert code.startswith("YAI1:") and json.loads(raw) == {"u": "http://100.1.2.3:8080", "t": "tok", "p": "ptok"}


async def test_learning_tools(app, monkeypatch):
    calls = []

    async def fake_call(action, args=None, timeout=40):
        calls.append((action, args))
        if action == "learned_apps":
            return {"data": [{"package": "com.whatsapp", "screens": 5}]}
        if action == "app_guide":
            return {"data": {"package": args["package"], "screens": [], "navigation": []}}
        return {"data": {"nodes": [{"text": "Ara", "click": True, "x": 10, "y": 20}]}}
    monkeypatch.setattr(app.phone, "call", fake_call)
    ctx = ToolContext(app, 42)
    assert (await phone_tools.phone_learned_apps(ctx))[0]["package"] == "com.whatsapp"
    assert (await phone_tools.phone_app_guide(ctx, "com.whatsapp"))["package"] == "com.whatsapp"
    # ekran okuma ve tıklama onaylı oturum ister
    assert "oturum" in (await phone_tools.phone_screen_read(ctx))["error"]
    assert "oturum" in (await phone_tools.phone_click_text(ctx, "Ara"))["error"]
    app.db.set("screen_until", 9e12)
    assert (await phone_tools.phone_screen_read(ctx))["nodes"][0]["text"] == "Ara"
    await phone_tools.phone_click_text(ctx, "Ara")
    assert ("click_text", {"text": "Ara"}) in calls
    assert REGISTRY["phone_screen_control"].needs_approval({"minutes": 5, "reason": "x"})
