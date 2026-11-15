"""Uygulama kabı: tüm servisleri birbirine bağlar."""
from __future__ import annotations

import logging

from .agent import Agent
from .agents import AgentStore
from .budget import Budget
from .config import Config
from .db import DB
from .google_auth import GoogleAuth
from .llm import LLM
from .phone_gateway import PhoneHub
from .tools.browser import BrowserManager
from .voice import synthesize

log = logging.getLogger(__name__)


class NullNotifier:
    """Telegram yokken (testler) mesajları biriktirir."""

    def __init__(self):
        self.sent: list[tuple] = []

    async def send_text(self, text: str, buttons=None):
        self.sent.append(("text", text))

    async def send_photo(self, data: bytes, caption: str = ""):
        self.sent.append(("photo", caption))

    async def send_document(self, data: bytes, filename: str):
        self.sent.append(("document", filename))

    async def send_voice(self, data: bytes):
        self.sent.append(("voice", len(data)))

    async def ask_approval(self, approval_id: int, summary: str):
        self.sent.append(("approval", approval_id, summary))


class App:
    def __init__(self, cfg: Config, notifier=None, llm=None):
        self.cfg = cfg
        self.db = DB(cfg.db_path)
        self.budget = Budget(cfg, self.db)
        self.llm = llm or LLM(cfg, self.budget)
        self.agents = AgentStore(self.db)
        self.google = GoogleAuth(cfg.google_client_file, cfg.google_token_file)
        self.phone = PhoneHub(cfg.phone_token, config={
            "notify_apps": cfg.phone_notify_apps, "battery_threshold": cfg.phone_battery_threshold},
            on_event=self.on_phone_event)
        self.browser = BrowserManager(cfg.browser_executable)
        self.notifier = notifier or NullNotifier()
        self.agent = Agent(self)

    async def deliver(self, text: str) -> None:
        """Kullanıcıya mesaj yollar; sesli mod açıksa ses kaydı da ekler."""
        await self.notifier.send_text(text)
        if self.db.get("voice_replies", False):
            audio = await synthesize(self.llm, text)
            if audio:
                await self.notifier.send_voice(audio)

    async def on_phone_event(self, event: str, data: dict) -> None:
        if not self.db.get("phone_enabled", True):
            return
        if event == "battery_low":
            await self.notifier.send_text(f"🔋 Telefonunun şarjı azaldı: %{data.get('percentage')}. Şarja takmayı unutma!")
        elif event == "notification":
            if self.db.get("phone_forward_notifications", True):
                await self.notifier.send_text(
                    f"📱 {data.get('app_label') or data.get('packageName')}: {data.get('title', '')}\n{data.get('content', '')}")
        elif event == "sms":
            await self.notifier.send_text(f"💬 Yeni SMS — {data.get('sender') or data.get('number')}:\n{data.get('body', '')}")
        elif event == "hello":
            log.info("Telefon olayı: hello %s", data)
