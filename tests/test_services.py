"""Zamanlayıcı, proaktif kontroller, panel, Telegram yardımcıları, ses, dosyalar, Google ayrıştırma."""
import base64
import json
import time

import pytest
from fastapi.testclient import TestClient

from bot import schedules as S
from bot.dashboard import create_app
from bot.scheduler import Scheduler
from bot.telegram_ui import split
from bot.tools import ToolContext
from bot.tools import computer, core
from bot.tools.google_ws import _body, _iso
from bot.tools.web import html_to_text


async def test_schedule_tools_and_runner(app, llm):
    ctx = ToolContext(app, 42)
    r = await core.create_schedule(ctx, "hafta içi 08:00", "Sabah brifingi hazırla")
    assert r["schedule_id"] and "1-5" in r["when"]
    r2 = await core.set_reminder(ctx, "+5dk", "Su iç")
    assert r2["schedule_id"]
    bad = await core.create_schedule(ctx, "bilmem ne", "x")
    assert "error" in bad
    assert len(await core.list_schedules(ctx)) == 2

    # zamanı gelmiş gibi yap
    app.db.execute("UPDATE schedules SET next_run=?", (time.time() - 1,))
    llm.push("☀️ Günaydın! Bugün 3 toplantın var.")
    await Scheduler(app).run_due()
    texts = [s[1] for s in app.notifier.sent if s[0] == "text"]
    assert "⏰ Hatırlatma: Su iç" in texts
    assert any("Günaydın" in t for t in texts)
    assert "[Zamanlanmış görev" in llm.calls[-1]["contents"][0].parts[0].text
    left = S.list_schedules(app.db)
    assert len(left) == 1 and left[0]["cron"] and left[0]["next_run"] > time.time()  # tekrarlayan kaldı


async def test_scheduler_periodic_logic(app):
    s = Scheduler(app)
    now = time.time()
    assert s._every("x", 60, now) is True
    assert s._every("x", 60, now + 10) is False
    assert s._every("x", 60, now + 61) is True
    assert s._every("y", 3600, now, initial_delay=600) is False
    assert s._every("y", 3600, now + 601) is True


async def test_budget_warning(app):
    app.budget.record("gemini-3.8-flash", 5_000_000, 0)  # 7.5 $
    s = Scheduler(app)
    await s.check_budget()
    await s.check_budget()
    warns = [t for k, t in [x[:2] for x in app.notifier.sent] if "%" in t]
    assert len(warns) == 2  # %50 ve %80 sadece bir kez


async def test_learning_proposes_skill(app, llm):
    for i in range(20):
        app.db.add_message(42, "user", f"haftalık satış raporunu çıkar {i}")
    llm.simple_answers.append(json.dumps({"skills": [{"name": "haftalik_rapor", "trigger": "rapor isteyince",
                                                      "steps": "1. Sheets'i oku 2. Özetle"}]}))
    await Scheduler(app).learn_skills()
    assert any(s[0] == "approval" and "haftalik_rapor" in s[2] for s in app.notifier.sent)


async def test_email_triage(app, llm, monkeypatch):
    import bot.scheduler as sch
    mails = [{"id": "a", "from": "Patron", "subject": "Acil toplantı", "snippet": "yarın 9", "unread": True},
             {"id": "b", "from": "Mağaza", "subject": "İndirim", "snippet": "%50", "unread": True}]

    async def fake_search(ctx, q, n):
        return mails
    monkeypatch.setattr(sch, "gmail_search", fake_search)
    monkeypatch.setattr(app.google, "connected", lambda: True)
    llm.simple_answers.append(json.dumps({"important": [{"index": 0, "why": "işle ilgili acil"}]}))
    await Scheduler(app).check_email()
    texts = [s[1] for s in app.notifier.sent if s[0] == "text"]
    assert len(texts) == 1 and "Acil toplantı" in texts[0] and "İndirim" not in texts[0]
    await Scheduler(app).check_email()  # aynı mailler tekrar bildirilmez
    assert len([s for s in app.notifier.sent if s[0] == "text"]) == 1


async def test_calendar_reminder(app, monkeypatch):
    import bot.scheduler as sch
    from datetime import datetime, timedelta
    start = (datetime.now(app.cfg.tz) + timedelta(minutes=10)).isoformat()

    async def fake_list(ctx, days):
        return [{"id": "e1", "title": "Diş hekimi", "start": start, "location": "Kadıköy"}]
    monkeypatch.setattr(sch, "calendar_list", fake_list)
    monkeypatch.setattr(app.google, "connected", lambda: True)
    await Scheduler(app).check_calendar()
    await Scheduler(app).check_calendar()
    texts = [s[1] for s in app.notifier.sent if s[0] == "text"]
    assert len(texts) == 1 and "Diş hekimi" in texts[0]


def test_dashboard(app):
    client = TestClient(create_app(app))
    assert client.get("/").status_code == 401
    assert client.get("/?token=yanlis").status_code == 401
    r = client.get("/?token=" + app.cfg.dashboard_token)
    assert r.status_code == 200 and "YAi Panel" in r.text
    # çerez ile devam
    assert client.post("/schedule/add", data={"when": "08:00", "task": "Brifing", "kind": "prompt"}).status_code == 200
    assert S.list_schedules(app.db)[0]["payload"] == "Brifing"
    client.post("/toggle/voice_replies")
    assert app.db.get("voice_replies") is True
    mid = app.db.add_memory("Kahveyi sade içer")
    assert "Kahveyi" in client.get("/").text
    client.post(f"/memory/delete/{mid}")
    assert app.db.memories() == []
    st = client.get("/api/status").json()
    assert st["phone"]["online"] is False


def test_dashboard_phone_ws(app):
    client = TestClient(create_app(app))
    with client.websocket_connect("/phone/ws") as ws:
        ws.send_text(json.dumps({"type": "hello", "token": app.cfg.phone_token, "device": "Pixel"}))
        cfg = json.loads(ws.receive_text())
        assert cfg["type"] == "config" and "notify_apps" in cfg
        assert app.phone.device == "Pixel"


def test_split():
    parts = split(("satır\n" * 2000))
    assert len(parts) >= 3 and all(len(p) <= 4000 for p in parts)


async def test_voice_conversion(app):
    from bot.voice import clean_for_speech, synthesize
    ogg = await synthesize(app.llm, "Merhaba **dünya** https://x.com")
    assert ogg and ogg[:4] == b"OggS"
    assert "bağlantı" in clean_for_speech("bak https://a.b/c") and "*" not in clean_for_speech("**x**")


async def test_computer_files(app):
    ctx = ToolContext(app, 42)
    await computer.write_file(ctx, "notlar/a.txt", "selam")
    assert (await computer.read_file(ctx, "notlar/a.txt"))["text"] == "selam"
    assert (await computer.list_files(ctx, "notlar"))[0]["name"] == "a.txt"
    with pytest.raises(ValueError):
        await computer.read_file(ctx, "../../etc/passwd")
    r = await computer.run_shell(ctx, "echo $((6*7))")
    assert r["output"].strip() == "42"
    await computer.send_file(ctx, "notlar/a.txt")
    assert ("document", "a.txt") in app.notifier.sent


async def test_pages_and_skills(app):
    ctx = ToolContext(app, 42)
    pid = (await core.create_page(ctx, "Rapor", "İlk"))["page_id"]
    await core.update_page(ctx, pid, "İkinci", append=True)
    assert (await core.read_page(ctx, pid))["content"] == "İlk\n\nİkinci"
    await core.save_skill(ctx, "rapor", "rapor isteyince", "1. yaz")
    assert (await core.use_skill(ctx, "rapor"))["steps"] == "1. yaz"
    assert (await core.list_skills(ctx))[0]["uses"] == 1


def test_google_parsing(app):
    data = base64.urlsafe_b64encode("Merhaba dünya".encode()).decode().rstrip("=")
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<p>html</p>").decode()}},
        {"mimeType": "text/plain", "body": {"data": data}}]}
    assert _body(payload) == "Merhaba dünya"
    assert _iso("2026-11-20", app.cfg.tz) == {"date": "2026-11-20"}
    assert _iso("2026-11-20 14:00", app.cfg.tz)["dateTime"].startswith("2026-11-20T14:00:00+03:00")


def test_html_to_text():
    r = html_to_text("<html><title>T</title><script>x()</script><body><p>Bir</p><p>İki</p></body></html>")
    assert r["title"] == "T" and r["text"] == "T\nBir\nİki" or "Bir\nİki" in r["text"]


async def test_google_not_connected(app):
    result = await app.agent.execute_tool(ToolContext(app, 42), "gmail_search", {"query": "is:unread"})
    assert "Google hesabı bağlı değil" in result["error"]
