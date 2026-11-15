"""Telefon köprüsü sunucu tarafı.

Telefondaki Termux köprüsü sunucuya WebSocket ile bağlanır (bağlantıyı telefon başlatır).
Protokol (JSON):
  telefon → sunucu  {"type":"hello","token":"...","device":"..."}
  sunucu  → telefon {"type":"config", ...}
  sunucu  → telefon {"type":"cmd","id":"...","action":"battery","args":{}}
  telefon → sunucu  {"type":"result","id":"...","ok":true,"data":...,"file_b64":"..."}
  telefon → sunucu  {"type":"event","event":"battery_low","data":{...}}
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)


class PhoneOffline(Exception):
    pass


class PhoneHub:
    def __init__(self, token: str, config: dict | None = None,
                 on_event: Callable[[str, dict], Awaitable[None]] | None = None):
        self.token = token
        self.config = config or {}
        self.on_event = on_event
        self.ws = None
        self.device = ""
        self.connected_at = 0.0
        self.last_seen = 0.0
        self._pending: dict[str, asyncio.Future] = {}

    @property
    def online(self) -> bool:
        return self.ws is not None

    async def handle(self, ws) -> None:
        """ws: send_text / receive_text yöntemleri olan bağlantı (Starlette WebSocket)."""
        try:
            hello = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=15))
        except Exception:
            return
        if not self.token or hello.get("type") != "hello" or not hmac.compare_digest(
                str(hello.get("token", "")), self.token):
            await ws.send_text(json.dumps({"type": "error", "error": "yetkisiz"}))
            return
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.ws, self.device = ws, hello.get("device", "telefon")
        self.connected_at = self.last_seen = time.time()
        await ws.send_text(json.dumps({"type": "config", **self.config}))
        log.info("Telefon bağlandı: %s", self.device)
        try:
            while True:
                msg = json.loads(await ws.receive_text())
                self.last_seen = time.time()
                if msg.get("type") == "result":
                    fut = self._pending.pop(msg.get("id"), None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                elif msg.get("type") == "event" and self.on_event:
                    asyncio.create_task(self.on_event(msg.get("event", ""), msg.get("data") or {}))
        except Exception as e:
            log.info("Telefon bağlantısı koptu: %s", e)
        finally:
            if self.ws is ws:
                self.ws = None
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(PhoneOffline("Telefon bağlantısı koptu"))
                self._pending.clear()

    async def call(self, action: str, args: dict | None = None, timeout: float = 40) -> dict:
        if not self.ws:
            raise PhoneOffline("Telefon bağlı değil. Telefonda Termux köprüsünün çalıştığından emin ol.")
        cid = uuid.uuid4().hex[:12]
        fut = asyncio.get_running_loop().create_future()
        self._pending[cid] = fut
        await self.ws.send_text(json.dumps({"type": "cmd", "id": cid, "action": action, "args": args or {}}))
        try:
            msg = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._pending.pop(cid, None)
            raise PhoneOffline(f"Telefon {int(timeout)} sn içinde cevap vermedi")
        if not msg.get("ok"):
            return {"error": msg.get("error", "bilinmeyen hata")}
        out: dict[str, Any] = {"data": msg.get("data")}
        if msg.get("file_b64"):
            out["file"] = base64.b64decode(msg["file_b64"])
        return out

    def status(self) -> dict:
        return {"online": self.online, "device": self.device,
                "connected_at": self.connected_at, "last_seen": self.last_seen}
