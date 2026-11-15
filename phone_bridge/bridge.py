#!/usr/bin/env python3
"""YAi telefon köprüsü — Android'de Termux içinde çalışır.

Sunucuya WebSocket ile bağlanır, gelen komutları SADECE izin listesindeki Termux:API / ADB komutlarıyla
çalıştırır ve sonucu geri yollar. Ayrıca pil, bildirim ve SMS olaylarını sunucuya bildirir.

Ayarlar ~/yai/bridge.env dosyasından okunur:
  SERVER_URL=ws://100.x.y.z:8080/phone/ws     (Tailscale IP'si)
  PHONE_TOKEN=...                               (sunucudaki .env ile aynı)
  DEVICE_NAME=Telefonum
  FORWARD_SMS=1
  ADB_SERIAL=                                   (boşsa ilk ADB cihazı)
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

log = logging.getLogger("yai-bridge")
KEYCODES = {"back": 4, "home": 3, "recents": 187, "enter": 66, "power": 26, "volume_up": 24, "volume_down": 25,
            "delete": 67}
STREAMS = {"music", "ring", "alarm", "notification", "call", "system"}


def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k in ("SERVER_URL", "PHONE_TOKEN", "DEVICE_NAME", "ADB_SERIAL", "FORWARD_SMS")})
    return env


class CommandError(Exception):
    pass


async def sh(argv: list[str], timeout: float = 30, stdin: bytes | None = None) -> bytes:
    """Bir komutu kabuk OLMADAN çalıştırır (komut enjeksiyonuna karşı)."""
    try:
        proc = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE if stdin else None,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        raise CommandError(f"Komut bulunamadı: {argv[0]} (pkg install termux-api android-tools)")
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise CommandError(f"{argv[0]} zaman aşımı")
    if proc.returncode != 0:
        raise CommandError((err or out).decode("utf-8", "ignore")[:400] or f"{argv[0]} hata kodu {proc.returncode}")
    return out


def parse(out: bytes):
    text = out.decode("utf-8", "ignore").strip()
    if not text:
        return {"ok": True}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class Bridge:
    def __init__(self, env: dict, runner=sh):
        self.env = env
        self.run = runner
        self.notify_apps: list[str] = []
        self.battery_threshold = 15
        self._adb_serial = env.get("ADB_SERIAL") or ""

    # ------------------------------------------------------------------ ADB
    async def adb(self, *args: str, timeout: float = 20) -> bytes:
        if not self._adb_serial:
            out = (await self.run(["adb", "devices"], 10)).decode()
            devs = [l.split()[0] for l in out.splitlines()[1:] if l.strip().endswith("device")]
            if not devs:
                raise CommandError("ADB cihazı yok. Kablosuz hata ayıklamayı açıp 'adb pair' ve 'adb connect' yap (README).")
            self._adb_serial = devs[0]
        return await self.run(["adb", "-s", self._adb_serial, *args], timeout)

    async def type_text(self, text: str):
        if text.isascii():
            safe = "".join(f"\\{c}" if c in "\"'`$&|;<>()\\*?~#!{}[]" else c for c in text).replace(" ", "%s")
            await self.adb("shell", "input", "text", safe)
        else:  # Türkçe karakterler: panoya koy ve yapıştır
            await self.run(["termux-clipboard-set"], 10, stdin=text.encode())
            await self.adb("shell", "input", "keyevent", "279")
        return {"typed": len(text)}

    # ------------------------------------------------------------------ komutlar
    async def execute(self, action: str, a: dict) -> tuple[object, bytes | None]:
        r = self.run
        if action == "battery":
            return parse(await r(["termux-battery-status"])), None
        if action == "wifi":
            return parse(await r(["termux-wifi-connectioninfo"])), None
        if action == "notifications":
            return parse(await r(["termux-notification-list"])), None
        if action == "sms_list":
            return parse(await r(["termux-sms-list", "-l", str(int(a.get("limit", 10))), "-t", "inbox"])), None
        if action == "sms_send":
            await r(["termux-sms-send", "-n", str(a["number"]), str(a["text"])])
            return {"sent": True}, None
        if action == "call":
            await r(["termux-telephony-call", str(a["number"])])
            return {"calling": a["number"]}, None
        if action == "call_log":
            return parse(await r(["termux-call-log", "-l", str(int(a.get("limit", 10)))])), None
        if action == "contacts":
            return parse(await r(["termux-contact-list"], 40)), None
        if action == "location":
            try:
                return parse(await r(["termux-location", "-p", "network", "-r", "once"], 45)), None
            except CommandError:
                return parse(await r(["termux-location", "-p", "gps", "-r", "once"], 60)), None
        if action == "photo":
            cam = "1" if a.get("camera") == "front" else "0"
            path = Path(tempfile.gettempdir()) / "yai_photo.jpg"
            await r(["termux-camera-photo", "-c", cam, str(path)], 50)
            data = path.read_bytes()
            path.unlink(missing_ok=True)
            return {"bytes": len(data)}, data
        if action == "clipboard_get":
            return {"text": (await r(["termux-clipboard-get"])).decode("utf-8", "ignore")}, None
        if action == "clipboard_set":
            await r(["termux-clipboard-set"], 10, stdin=str(a["text"]).encode())
            return {"ok": True}, None
        if action == "torch":
            await r(["termux-torch", "on" if a.get("on") else "off"])
            return {"torch": bool(a.get("on"))}, None
        if action == "volume":
            stream = a.get("stream", "music")
            if stream not in STREAMS:
                raise CommandError("Geçersiz ses kanalı")
            await r(["termux-volume", stream, str(max(0, min(int(a.get("level", 7)), 15)))])
            return {"ok": True}, None
        if action == "speak":
            await r(["termux-tts-speak", str(a["text"])], 120)
            return {"spoken": True}, None
        if action == "vibrate":
            await r(["termux-vibrate", "-f", "-d", str(max(100, min(int(a.get("ms", 1000)), 5000)))])
            return {"ok": True}, None
        if action == "open_url":
            url = str(a["url"])
            if not url.split(":", 1)[0] in ("http", "https", "geo", "tel", "mailto", "market", "intent", "whatsapp"):
                raise CommandError("Bu tür bağlantı açılamaz")
            await r(["termux-open-url", url])
            return {"opened": url}, None
        if action == "list_apps":
            out = (await r(["pm", "list", "packages", "-3"])).decode()
            return sorted(l.replace("package:", "").strip() for l in out.splitlines() if l.strip()), None
        if action == "open_app":
            pkg = str(a["package"])
            if not all(c.isalnum() or c in "._" for c in pkg):
                raise CommandError("Geçersiz paket adı")
            try:
                comp = (await r(["cmd", "package", "resolve-activity", "--brief", pkg])).decode().strip().splitlines()[-1]
                await r(["am", "start", "-n", comp])
            except CommandError:
                await self.adb("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
            return {"opened": pkg}, None
        if action == "alarm":
            await r(["am", "start", "-a", "android.intent.action.SET_ALARM",
                     "--ei", "android.intent.extra.alarm.HOUR", str(int(a["hour"])),
                     "--ei", "android.intent.extra.alarm.MINUTES", str(int(a["minute"])),
                     "--es", "android.intent.extra.alarm.MESSAGE", str(a.get("label", "YAi")),
                     "--ez", "android.intent.extra.alarm.SKIP_UI", "true"])
            return {"alarm": f"{int(a['hour']):02d}:{int(a['minute']):02d}"}, None
        if action == "timer":
            await r(["am", "start", "-a", "android.intent.action.SET_TIMER",
                     "--ei", "android.intent.extra.alarm.LENGTH", str(int(a["seconds"])),
                     "--es", "android.intent.extra.alarm.MESSAGE", str(a.get("label", "YAi")),
                     "--ez", "android.intent.extra.alarm.SKIP_UI", "true"])
            return {"timer_seconds": int(a["seconds"])}, None
        if action == "notify":
            await r(["termux-notification", "-t", str(a["title"]), "-c", str(a["content"]), "--group", "yai"])
            return {"ok": True}, None
        if action == "tasker":
            await r(["am", "broadcast", "-a", "yai.TASKER", "--es", "task", str(a["task"]),
                     "--es", "par", str(a.get("param", ""))])
            return {"sent_to_tasker": a["task"]}, None
        # ---------------- Seviye 3: ADB ----------------
        if action == "adb_status":
            try:
                await self.adb("shell", "echo", "ok", timeout=10)
                return {"adb": "hazır", "serial": self._adb_serial}, None
            except CommandError as e:
                return {"adb": "hazır değil", "error": str(e)}, None
        if action == "adb_screenshot":
            data = await self.adb("exec-out", "screencap", "-p", timeout=30)
            return {"bytes": len(data)}, data
        if action == "adb_tap":
            await self.adb("shell", "input", "tap", str(int(a["x"])), str(int(a["y"])))
            return {"tapped": [a["x"], a["y"]]}, None
        if action == "adb_swipe":
            await self.adb("shell", "input", "swipe", *(str(int(a[k])) for k in ("x1", "y1", "x2", "y2")),
                           str(int(a.get("ms", 300))))
            return {"swiped": True}, None
        if action == "adb_text":
            return await self.type_text(str(a["text"])), None
        if action == "adb_key":
            code = KEYCODES.get(a.get("key", ""))
            if code is None:
                raise CommandError("Bilinmeyen tuş")
            await self.adb("shell", "input", "keyevent", str(code))
            return {"pressed": a["key"]}, None
        raise CommandError(f"İzin verilmeyen komut: {action}")

    async def handle_cmd(self, msg: dict) -> dict:
        try:
            data, file = await self.execute(msg.get("action", ""), msg.get("args") or {})
            out = {"type": "result", "id": msg.get("id"), "ok": True, "data": data}
            if file:
                out["file_b64"] = base64.b64encode(file).decode()
            return out
        except (CommandError, KeyError, ValueError) as e:
            return {"type": "result", "id": msg.get("id"), "ok": False, "error": str(e)}

    # ------------------------------------------------------------------ olay izleyiciler
    async def watch_battery(self, send):
        alerted = False
        while True:
            try:
                b = parse(await self.run(["termux-battery-status"]))
                pct, status = int(b.get("percentage", 100)), b.get("status", "")
                if pct <= self.battery_threshold and status != "CHARGING" and not alerted:
                    alerted = True
                    await send({"type": "event", "event": "battery_low", "data": b})
                elif pct > self.battery_threshold + 5 or status == "CHARGING":
                    alerted = False
            except Exception as e:
                log.debug("pil: %s", e)
            await asyncio.sleep(300)

    async def watch_notifications(self, send):
        seen: set[str] = set()
        first = True
        while True:
            try:
                items = parse(await self.run(["termux-notification-list"]))
                for n in items if isinstance(items, list) else []:
                    key = f"{n.get('packageName')}|{n.get('id')}|{n.get('when')}|{n.get('title')}"
                    if key in seen:
                        continue
                    seen.add(key)
                    if not first and any(app in str(n.get("packageName", "")) for app in self.notify_apps):
                        await send({"type": "event", "event": "notification", "data": n})
                first = False
                if len(seen) > 2000:
                    seen = set(list(seen)[-500:])
            except Exception as e:
                log.debug("bildirim: %s", e)
            await asyncio.sleep(60)

    async def watch_sms(self, send):
        if self.env.get("FORWARD_SMS", "1") not in ("1", "true", "evet"):
            return
        last_id = None
        while True:
            try:
                msgs = parse(await self.run(["termux-sms-list", "-l", "5", "-t", "inbox"]))
                ids = [m.get("_id", 0) for m in msgs] if isinstance(msgs, list) else []
                if last_id is None:
                    last_id = max(ids, default=0)
                else:
                    for m in sorted(msgs, key=lambda x: x.get("_id", 0)):
                        if m.get("_id", 0) > last_id:
                            await send({"type": "event", "event": "sms", "data": m})
                    last_id = max([last_id, *ids])
            except Exception as e:
                log.debug("sms: %s", e)
            await asyncio.sleep(60)

    # ------------------------------------------------------------------ bağlantı
    async def session(self, ws):
        await ws.send(json.dumps({"type": "hello", "token": self.env["PHONE_TOKEN"],
                                  "device": self.env.get("DEVICE_NAME", "Android")}))
        lock = asyncio.Lock()

        async def send(obj):
            async with lock:
                await ws.send(json.dumps(obj))

        watchers = []
        try:
            async for raw in ws:
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "error":
                    raise PermissionError(msg.get("error"))
                if t == "config":
                    self.notify_apps = msg.get("notify_apps", [])
                    self.battery_threshold = int(msg.get("battery_threshold", 15))
                    if not watchers:
                        watchers = [asyncio.create_task(w(send)) for w in
                                    (self.watch_battery, self.watch_notifications, self.watch_sms)]
                    log.info("✅ Sunucuya bağlandı")
                elif t == "cmd":
                    async def go(m=msg):
                        await send(await self.handle_cmd(m))
                    asyncio.create_task(go())
        finally:
            for w in watchers:
                w.cancel()

    async def forever(self):
        import websockets
        delay = 2
        while True:
            try:
                async with websockets.connect(self.env["SERVER_URL"], max_size=32 * 1024 * 1024,
                                              ping_interval=30, ping_timeout=30) as ws:
                    delay = 2
                    await self.session(ws)
            except PermissionError as e:
                log.error("Sunucu reddetti: %s (PHONE_TOKEN doğru mu?)", e)
                delay = 60
            except Exception as e:
                log.warning("Bağlantı yok (%s), %s sn sonra tekrar...", e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    env = load_env(Path(os.environ.get("YAI_ENV", Path.home() / "yai" / "bridge.env")))
    if not env.get("SERVER_URL") or not env.get("PHONE_TOKEN"):
        print("❌ ~/yai/bridge.env içinde SERVER_URL ve PHONE_TOKEN olmalı")
        sys.exit(1)
    asyncio.run(Bridge(env).forever())


if __name__ == "__main__":
    main()
