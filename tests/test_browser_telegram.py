"""Gerçek Chromium ile tarayıcı araçları + Telegram arayüzü kurulumu."""
import http.server
import os
import threading
from types import SimpleNamespace

import pytest

from bot.tools import REGISTRY, ToolContext
from bot.tools import browser as B

PAGE = b"""<html><head><title>Test Dukkan</title></head><body>
<h1>Hos geldin</h1><a href="/urun">Urunler</a>
<form action="/ara"><input name="q" placeholder="Ara..."></form></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE if self.path == "/" else f"<html><title>Sayfa {self.path}</title><body>Icerik {self.path}</body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def site():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.mark.skipif(not os.path.exists("/opt/pw-browsers/chromium"), reason="Chromium yok")
async def test_browser_tools(app, site):
    ctx = ToolContext(app, 42)
    try:
        r = await B.browser_open(ctx, site)
        assert r["title"] == "Test Dukkan" and any(e["text"] == "Urunler" for e in r["elements"])
        r = await B.browser_click(ctx, "Urunler")
        assert r["url"].endswith("/urun") and "Icerik /urun" in r["text"]
        await B.browser_open(ctx, site)
        assert REGISTRY["browser_type"].needs_approval({"target": "q", "text": "x", "submit": True}) is False
        assert REGISTRY["browser_type"].needs_approval({"target": "#sifre", "text": "x", "submit": True}) is True
        assert REGISTRY["browser_type"].needs_approval({"target": "parola", "text": "x", "submit": True}) is True
        r = await B.browser_type(ctx, "q", "telefon", submit=True)
        assert "/ara?q=telefon" in r["url"]
        assert "bayt" in (await B.browser_look(ctx, "ne görüyorsun"))["answer"]
        await B.browser_screenshot(ctx)
        assert any(s[0] == "photo" for s in app.notifier.sent)
    finally:
        await app.browser.close()


def test_telegram_ui_builds(app):
    from bot.telegram_ui import TelegramNotifier, TelegramUI
    app.cfg.telegram_token = "123456:TEST-token"
    ui = TelegramUI(app)
    assert isinstance(app.notifier, TelegramNotifier)
    cmds = {c for h in ui.application.handlers[0] for c in getattr(h, "commands", [])}
    for c in ["start", "zamanla", "hatirlat", "telefon", "google", "maliyet", "brifing", "ajan", "ses"]:
        assert c in cmds


async def test_telegram_owner_guard(app):
    from bot.telegram_ui import TelegramUI
    app.cfg.telegram_token = "123456:TEST-token"
    ui = TelegramUI(app)
    replies = []

    async def reply_text(t, **k):
        replies.append(t)
    msg = SimpleNamespace(reply_text=reply_text, text="selam")
    stranger = SimpleNamespace(effective_user=SimpleNamespace(id=999), effective_message=msg, message=msg)
    assert await ui._guard(stranger) is False and "özel" in replies[-1]
    owner = SimpleNamespace(effective_user=SimpleNamespace(id=42), effective_message=msg, message=msg)
    assert await ui._guard(owner) is True
    app.cfg.owner_id = 0
    assert await ui._guard(stranger) is False and "999" in replies[-1]


async def test_telegram_schedule_command(app):
    from bot.telegram_ui import TelegramUI
    app.cfg.telegram_token = "123456:TEST-token"
    ui = TelegramUI(app)
    replies = []

    async def reply_text(t, **k):
        replies.append(t)
    msg = SimpleNamespace(reply_text=reply_text)
    upd = SimpleNamespace(effective_user=SimpleNamespace(id=42), effective_message=msg, message=msg,
                          effective_chat=SimpleNamespace(id=42))
    await ui.cmd_zamanla(upd, SimpleNamespace(args="hafta içi 08:00 | Sabah brifingi hazırla".split()))
    assert "kuruldu" in replies[-1]
    await ui.cmd_hatirlat(upd, SimpleNamespace(args="yanlış zaman | x".split()))
    assert "⚠️" in replies[-1]
    await ui.cmd_ses(upd, SimpleNamespace(args=["ac"]))
    assert app.db.get("voice_replies") is True


def test_main_config_check(cfg):
    from bot.main import check
    cfg.gemini_api_key = cfg.telegram_token = ""
    probs = check(cfg)
    assert any("GEMINI" in p for p in probs) and any("TELEGRAM" in p for p in probs)
    cfg.gemini_api_key, cfg.telegram_token = "k", "t"
    assert check(cfg) == []
