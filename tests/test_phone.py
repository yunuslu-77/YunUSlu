"""Telefon köprüsü uçtan uca: sunucu PhoneHub ↔ telefondaki Bridge (sahte Termux komutlarıyla)."""
import asyncio
import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phone_bridge"))
from bridge import Bridge, CommandError  # noqa: E402

from bot.tools import ToolContext  # noqa: E402
from bot.tools import phone as phone_tools  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1080, 2400) + b"\x00" * 20


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.battery = {"percentage": 80, "status": "DISCHARGING"}

    async def __call__(self, argv, timeout=30, stdin=None):
        self.calls.append((argv, stdin))
        cmd = argv[0]
        if cmd == "termux-battery-status":
            return json.dumps(self.battery).encode()
        if cmd == "termux-sms-list":
            return json.dumps([{"_id": 5, "number": "+905551112233", "sender": "Anne", "body": "Akşam gel"}]).encode()
        if cmd == "termux-notification-list":
            return b"[]"
        if cmd == "termux-contact-list":
            return json.dumps([{"name": "Ahmet Yılmaz", "number": "05551234567"}]).encode()
        if cmd == "termux-location":
            return json.dumps({"latitude": 41.0, "longitude": 29.0}).encode()
        if cmd == "termux-camera-photo":
            Path(argv[-1]).write_bytes(b"\xff\xd8JPEG")
            return b""
        if cmd == "adb" and argv[1] == "devices":
            return b"List of devices attached\nlocalhost:5555\tdevice\n"
        if cmd == "adb" and "screencap" in argv:
            return PNG
        if cmd == "pm":
            return b"package:com.whatsapp\npackage:com.spotify.music\n"
        if cmd == "cmd":
            return b"priority=0\ncom.whatsapp/.Main\n"
        if cmd == "termux-clipboard-get":
            return "panodaki metin".encode()
        return b""


class Pipe:
    """İki uçlu bellek içi WebSocket."""

    def __init__(self):
        self.a, self.b = asyncio.Queue(), asyncio.Queue()

    class End:
        def __init__(self, inbox, outbox):
            self.inbox, self.outbox = inbox, outbox
            self.closed = False

        # Starlette tarzı (sunucu)
        async def send_text(self, s):
            await self.outbox.put(s)

        async def receive_text(self):
            s = await self.inbox.get()
            if s is None:
                raise ConnectionError("kapandı")
            return s

        async def close(self):
            await self.outbox.put(None)

        # websockets tarzı (istemci)
        async def send(self, s):
            await self.outbox.put(s)

        def __aiter__(self):
            return self

        async def __anext__(self):
            s = await self.inbox.get()
            if s is None:
                raise StopAsyncIteration
            return s

    def ends(self):
        return Pipe.End(self.a, self.b), Pipe.End(self.b, self.a)


@pytest.fixture
async def connected(app):
    runner = FakeRunner()
    bridge = Bridge({"PHONE_TOKEN": app.cfg.phone_token, "DEVICE_NAME": "Test Telefonu", "FORWARD_SMS": "1"}, runner)
    server_end, client_end = Pipe().ends()
    hub_task = asyncio.create_task(app.phone.handle(server_end))
    bridge_task = asyncio.create_task(bridge.session(client_end))
    for _ in range(50):
        if app.phone.online:
            break
        await asyncio.sleep(0.01)
    assert app.phone.online and app.phone.device == "Test Telefonu"
    yield runner, bridge
    hub_task.cancel()
    bridge_task.cancel()


async def test_level1_commands(app, connected):
    runner, _ = connected
    ctx = ToolContext(app, 42)
    st = await phone_tools.phone_status(ctx)
    assert st["online"] and st["battery"]["percentage"] == 80
    sms = await phone_tools.phone_sms_list(ctx, 5, "Anne")
    assert sms[0]["body"] == "Akşam gel"
    sms = await phone_tools.phone_sms_list(ctx, 5, "0555 111 22 33")
    assert len(sms) == 1
    assert (await phone_tools.phone_contacts(ctx, "ahmet"))[0]["number"] == "05551234567"
    loc = await phone_tools.phone_location(ctx)
    assert loc["maps_link"].endswith("41.0,29.0")
    assert (await phone_tools.phone_clipboard_get(ctx))["text"] == "panodaki metin"
    await phone_tools.phone_set_alarm(ctx, 7, 30, "Uyan")
    alarm = [c for c, _ in runner.calls if "android.intent.action.SET_ALARM" in c][0]
    assert alarm[alarm.index("android.intent.extra.alarm.HOUR") + 1] == "7"
    await phone_tools.phone_open_app(ctx, "com.whatsapp")
    assert ["am", "start", "-n", "com.whatsapp/.Main"] in [c for c, _ in runner.calls]
    assert "com.spotify.music" in await phone_tools.phone_list_apps(ctx, "spotify")
    await phone_tools.phone_tasker(ctx, "WifiKapat")
    assert any("yai.TASKER" in c for c, _ in runner.calls)
    await phone_tools.phone_sms_send(ctx, "+90555", "Geliyorum")
    assert ["termux-sms-send", "-n", "+90555", "Geliyorum"] in [c for c, _ in runner.calls]


async def test_photo_sent_to_user(app, connected):
    r = await phone_tools.phone_photo(ToolContext(app, 42), "front", "ne var?")
    assert r["sent"] and "bayt" in r["answer"]
    assert ("photo", "📷 Telefondan") in app.notifier.sent


async def test_screen_control_requires_session(app, connected):
    runner, _ = connected
    ctx = ToolContext(app, 42)
    assert "oturum" in (await phone_tools.phone_tap(ctx, 10, 20))["error"]
    await phone_tools.phone_screen_control(ctx, 5, "test")
    look = await phone_tools.phone_screen_look(ctx, "WhatsApp nerede?")
    assert (look["width"], look["height"]) == (1080, 2400)
    await phone_tools.phone_tap(ctx, 100, 200)
    assert ["adb", "-s", "localhost:5555", "shell", "input", "tap", "100", "200"] in [c for c, _ in runner.calls]
    await phone_tools.phone_type_text(ctx, "merhaba dünya")  # Türkçe → pano + yapıştır
    assert (["termux-clipboard-set"], "merhaba dünya".encode()) in runner.calls
    await phone_tools.phone_type_text(ctx, "hello world")
    assert any(c[-1] == "hello%sworld" for c, _ in runner.calls)
    await phone_tools.phone_key(ctx, "back")
    assert any(c[-2:] == ["keyevent", "4"] for c, _ in runner.calls)


async def test_phone_disabled(app, connected):
    app.db.set("phone_enabled", False)
    assert "kapalı" in (await phone_tools.phone_torch(ToolContext(app, 42), True))["error"]


async def test_events_forwarded(app, connected):
    runner, bridge = connected
    await app.on_phone_event("battery_low", {"percentage": 9})
    await app.on_phone_event("sms", {"sender": "Anne", "body": "Neredesin"})
    await app.on_phone_event("notification", {"packageName": "com.whatsapp", "title": "Ali", "content": "Selam"})
    texts = [s[1] for s in app.notifier.sent if s[0] == "text"]
    assert any("%9" in t for t in texts) and any("Neredesin" in t for t in texts) and any("Ali" in t for t in texts)
    assert bridge.notify_apps == app.cfg.phone_notify_apps


async def test_bridge_battery_watcher():
    runner = FakeRunner()
    runner.battery = {"percentage": 10, "status": "DISCHARGING"}
    b = Bridge({}, runner)
    sent = []

    async def send(m):
        sent.append(m)
    t = asyncio.create_task(b.watch_battery(send))
    await asyncio.sleep(0.05)
    t.cancel()
    assert sent[0]["event"] == "battery_low"


async def test_offline_and_bad_token(app):
    r = await phone_tools.phone_torch(ToolContext(app, 42), True)
    assert "bağlı değil" in r["error"]
    server_end, client_end = Pipe().ends()
    task = asyncio.create_task(app.phone.handle(server_end))
    await client_end.send(json.dumps({"type": "hello", "token": "yanlis"}))
    reply = json.loads(await client_end.inbox.get())
    assert reply["error"] == "yetkisiz" and not app.phone.online
    await task


async def test_bridge_rejects_unknown():
    b = Bridge({}, FakeRunner())
    with pytest.raises(CommandError):
        await b.execute("rm_rf", {})
    with pytest.raises(CommandError):
        await b.execute("open_url", {"url": "file:///sdcard/x"})
    with pytest.raises(CommandError):
        await b.execute("open_app", {"package": "com.x; reboot"})
    r = await b.handle_cmd({"id": "1", "action": "rm_rf"})
    assert r["ok"] is False and "İzin verilmeyen" in r["error"]
