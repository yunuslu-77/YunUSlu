import time
from datetime import datetime

import pytest

from yworkspace.app import build_session
from yworkspace.automations import runner as rn
from yworkspace.automations.schedule import Cron
from yworkspace.config import Config
from yworkspace.tools.registry import EXTERNAL, Tool, obj


def test_cron():
    c = Cron("0 9 * * 1")  # Mondays 09:00
    assert c.next_after(datetime(2026, 10, 27, 12, 0)) == datetime(2026, 11, 2, 9, 0)
    assert c.last_before(datetime(2026, 10, 27, 12, 0)) == datetime(2026, 10, 26, 9, 0)
    assert Cron("her gece").expr == "0 2 * * *" and Cron("every 15 minutes").expr == "*/15 * * * *"
    assert Cron("*/15 * * * *").next_after(datetime(2026, 1, 1, 10, 7)) == datetime(2026, 1, 1, 10, 15)
    assert Cron("30 8 1,15 * *").next_after(datetime(2026, 1, 2)) == datetime(2026, 1, 15, 8, 30)
    assert Cron("0 0 * * 0").matches(datetime(2026, 11, 1))  # a Sunday
    with pytest.raises(ValueError):
        Cron("61 * * * *")
    with pytest.raises(ValueError):
        Cron("bazen")


def make(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    sess = build_session(tmp_path / "oto", Config(sandbox="local"), with_engine=True)
    sent = []

    def send_mail(to: str, body: str) -> str:
        sent.append((to, body))
        return f"sent to {to}"
    sess.registry.register(Tool("send_mail", "Send an e-mail.", obj({"to": {"type": "string"},
                                                                     "body": {"type": "string"}}, ["to", "body"]),
                                send_mail, EXTERNAL, "test"))
    return sess, sent


def test_chain_approval_and_history(tmp_path, monkeypatch):
    sess, sent = make(tmp_path, monkeypatch)
    call = sess.registry.call
    root = sess.workspace.root
    (root / "notlar.txt").write_text("satış: 42\n", encoding="utf-8")
    bad = call("automation_create", {"name": "x", "steps": [{"tool": "yok"}], "schedule": "bazen"})
    assert bad.is_error and "unknown tool yok" in bad.text and "5 cron fields" in bad.text
    r = call("automation_create", {"name": "haftalık rapor", "schedule": "weekly", "steps": [
        {"tool": "read", "args": {"path": "notlar.txt"}},
        {"tool": "send_mail", "args": {"to": "yunus@example.com", "body": "Rapor {date}:\n{prev}"}}]})
    assert not r.is_error and "wait for the user's approval" in r.text, r.text
    run = call("automation_run", {"key": "haftalık rapor"}).text
    assert "waiting_approval" in run and "WAITING FOR APPROVAL" in run and not sent
    assert "WAITING: approve" in call("automation_list", {}).text
    ok = call("automation_approve", {"key": "haftalık rapor"}).text
    assert "haftalık rapor: ok" in ok and len(sent) == 1
    assert "satış: 42" in sent[0][1] and sent[0][1].startswith("Rapor 20")
    hist = call("automation_history", {"key": "haftalık rapor"}).text
    assert "waiting_approval" in hist and " ok " in hist
    assert call("automation_set", {"key": "haftalık rapor", "delete": True}).text.startswith("Deleted")


def test_schedule_catch_up_and_file_events(tmp_path, monkeypatch):
    sess, _ = make(tmp_path, monkeypatch)
    root = sess.workspace.root
    store = rn.Store(root)
    created = datetime(2026, 10, 20, 12, 0).timestamp()
    items = []
    for name, catch in (("gece-run", "run"), ("gece-ask", "ask"), ("gece-skip", "skip")):
        a = rn.new(name, [{"tool": "list", "args": {}}], schedule="her gece", catch_up=catch)
        a.created = created
        items.append(a)
    inbox = rn.new("gelen", [{"tool": "read", "args": {"path": "{files}"}}], event="file_added",
                   pattern="inbox/*.csv")
    (root / "inbox").mkdir()
    (root / "inbox/eski.csv").write_text("a\n", encoding="utf-8")
    inbox.snapshot = rn._files(root, "inbox/*.csv")
    items.append(inbox)
    store.save(items)
    # The computer was off at 02:00; it is switched on at 10:00.
    r = rn.Runner(sess, now=lambda: datetime(2026, 10, 21, 10, 0))
    lines = r.tick()
    assert any(x.startswith("gece-run: ok (missed run of 2026-10-21 02:00)") for x in lines), lines
    got = {a.name: a for a in store.load()}
    assert got["gece-ask"].pending["ask"] == "catch_up" and got["gece-skip"].history[-1]["status"] == "skipped"
    assert not r.tick()  # nothing new
    (root / "inbox/yeni.csv").write_text("ürün,adet\nkahve,3\n", encoding="utf-8")
    time.sleep(0.01)
    lines = r.tick()
    assert lines == ["gelen: ok (file_added: inbox/yeni.csv)"], lines
    assert "kahve,3" in store.get(store.load(), "gelen").history[-1]["steps"][0]["output"]
    on_time = rn.Runner(sess, now=lambda: datetime(2026, 10, 22, 2, 0, 30))
    assert any(x.startswith("gece-run: ok (schedule)") for x in on_time.tick())


def test_prompt_step_guard_blocks_outside_actions(tmp_path, monkeypatch):
    sess, sent = make(tmp_path, monkeypatch)
    seen = []

    def fake_role(role, prompt, max_steps=None):
        seen.append(prompt)
        res = sess.registry.call("send_mail", {"to": "a@b.c", "body": "x"})
        return res.text
    monkeypatch.setattr(sess.engine, "run_role", fake_role)
    a = rn.new("özet", [{"tool": "list", "args": {}}, {"prompt": "Dosyaları özetle"}], schedule="daily")
    rec = rn.Runner(sess).run(a, "test")
    assert rec["status"] == "ok" and "needs_approval" in rec["steps"][1]["output"] and not sent
    assert "Output of the previous step" in seen[0]
    assert not sess.registry.before_call or all(h.__name__ != "guard" for h in sess.registry.before_call)
    files = rn.autostart_files(sess.workspace.root)
    assert any("systemd" in k for k in files) and any("schtasks" in v for v in files.values())
