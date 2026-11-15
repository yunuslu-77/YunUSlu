"""Arka plan döngüsü: zamanlanmış görevler + proaktif kontroller + otomatik öğrenme."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

from . import schedules as S
from .budget import BudgetExceeded
from .tools import ToolContext
from .tools.google_ws import NotConnected, calendar_list, gmail_search

log = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, app, tick: float = 30):
        self.app = app
        self.tick = tick
        self._task: asyncio.Task | None = None

    def start(self):
        self._task = asyncio.create_task(self.loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    @property
    def chat_id(self) -> int:
        return self.app.cfg.owner_id

    async def loop(self):
        while True:
            try:
                await self.run_once()
            except Exception:
                log.exception("Zamanlayıcı hatası")
            await asyncio.sleep(self.tick)

    async def run_once(self):
        await self.run_due()
        now = time.time()
        if self._every("email", self.app.cfg.proactive_email_minutes * 60, now):
            await self.check_email()
        if self._every("calendar", 5 * 60, now):
            await self.check_calendar()
        if self._every("budget", 60 * 60, now):
            await self.check_budget()
        if self.app.cfg.learning_enabled and self._every("learn", 7 * 24 * 3600, now, initial_delay=24 * 3600):
            await self.learn_skills()

    def _every(self, name: str, interval: float, now: float, initial_delay: float = 0) -> bool:
        key = f"last_check:{name}"
        last = self.app.db.get(key)
        if last is None:
            self.app.db.set(key, now if initial_delay == 0 else now - interval + initial_delay)
            return initial_delay == 0
        if now - last >= interval:
            self.app.db.set(key, now)
            return True
        return False

    # ------------------------------------------------------------------ görevler
    async def run_due(self):
        for s in S.due_schedules(self.app.db):
            S.mark_ran(self.app.db, s, self.app.cfg.tz)
            try:
                if s["kind"] == "message":
                    await self.app.deliver(f"⏰ Hatırlatma: {s['payload']}")
                else:
                    task = f"[Zamanlanmış görev #{s['id']}] {s['payload']}"
                    text = await self.app.agent.run_task(self.chat_id, task, s["agent"] or "asistan", save_history=True)
                    await self.app.deliver(text)
            except Exception as e:
                log.exception("Görev #%s başarısız", s["id"])
                await self.app.notifier.send_text(f"⚠️ Zamanlanmış görev #{s['id']} çalışamadı: {e}")

    # ------------------------------------------------------------------ proaktif e-posta
    async def check_email(self):
        app = self.app
        if not app.db.get("proactive_email", True) or not app.google.connected():
            return
        ctx = ToolContext(app, self.chat_id)
        try:
            mails = await gmail_search(ctx, "is:unread newer_than:1d -category:promotions -category:social -category:updates", 15)
        except NotConnected:
            return
        seen = set(app.db.get("seen_emails", []))
        new = [m for m in mails if m["id"] not in seen]
        if not new:
            return
        app.db.set("seen_emails", (list(seen) + [m["id"] for m in new])[-500:])
        listing = "\n".join(f"{i}. Kimden: {m['from']} | Konu: {m['subject']} | {m['snippet'][:200]}" for i, m in enumerate(new))
        memories = "\n".join(m["fact"] for m in app.db.memories())
        try:
            raw = await app.llm.simple(
                "Aşağıdaki yeni e-postalardan kullanıcının HEMEN bilmesi gerekenleri seç (kişisel mesajlar, iş, fatura son "
                "tarihi, güvenlik uyarısı, randevu). Reklam/bülten önemli değildir.\n"
                f"Kullanıcı hakkında: {memories or '-'}\n\nE-postalar:\n{listing}\n\n"
                'JSON dön: {"important":[{"index":0,"why":"kısa neden"}]}', json_mode=True, purpose="e-posta takibi")
            picks = json.loads(raw).get("important", [])
        except (BudgetExceeded, json.JSONDecodeError, AttributeError):
            return
        lines = []
        for p in picks[:5]:
            i = p.get("index")
            if isinstance(i, int) and 0 <= i < len(new):
                m = new[i]
                lines.append(f"• {m['from']}\n  «{m['subject']}» — {p.get('why', '')}")
        if lines:
            await app.deliver("📬 Önemli yeni e-posta:\n" + "\n".join(lines) + "\n\nİstersen özetleyebilir veya cevap yazabilirim.")

    # ------------------------------------------------------------------ proaktif takvim
    async def check_calendar(self):
        app = self.app
        if not app.db.get("proactive_calendar", True) or not app.google.connected():
            return
        try:
            events = await calendar_list(ToolContext(app, self.chat_id), 1)
        except NotConnected:
            return
        notified = set(app.db.get("notified_events", []))
        now = datetime.now(app.cfg.tz)
        lead = timedelta(minutes=app.cfg.proactive_calendar_minutes)
        for e in events:
            if "T" not in e["start"] or e["id"] in notified:
                continue
            start = datetime.fromisoformat(e["start"])
            if now <= start <= now + lead:
                notified.add(e["id"])
                where = f"\n📍 {e['location']}" if e.get("location") else ""
                await app.deliver(f"📅 {int((start - now).total_seconds() // 60)} dk sonra: {e['title']} ({start:%H:%M}){where}")
        app.db.set("notified_events", list(notified)[-300:])

    # ------------------------------------------------------------------ bütçe uyarısı
    async def check_budget(self):
        app = self.app
        month = datetime.now(app.cfg.tz).strftime("%Y-%m")
        spent, limit = app.budget.spent_month(), app.cfg.monthly_limit_usd
        for pct in (50, 80, 95):
            key = f"budget_warn:{month}:{pct}"
            if spent >= limit * pct / 100 and not app.db.get(key):
                app.db.set(key, True)
                await app.notifier.send_text(f"💸 Bu ayki API harcaması limitin %{pct}'ine ulaştı: {spent:.2f} $ / {limit:.2f} $")

    # ------------------------------------------------------------------ otomatik öğrenme
    async def learn_skills(self):
        app = self.app
        msgs = app.db.all("SELECT text FROM messages WHERE role='user' AND text NOT LIKE '[%' ORDER BY id DESC LIMIT 150")
        if len(msgs) < 15:
            return
        existing = [s["name"] for s in app.db.all("SELECT name FROM skills")]
        try:
            raw = await app.llm.simple(
                "Kullanıcının son mesajları aşağıda. Tekrar eden, beceriye dönüştürülebilecek en fazla 2 iş kalıbı bul. "
                f"Var olan beceriler: {existing}. Gerçekten tekrar etmeyen şeyleri önerme.\n\n"
                + "\n".join(f"- {m['text'][:200]}" for m in msgs) +
                '\n\nJSON dön: {"skills":[{"name":"kısa_ad","trigger":"ne zaman","steps":"1. ... 2. ..."}]}',
                json_mode=True, purpose="öğrenme")
            skills = json.loads(raw).get("skills", [])
        except (BudgetExceeded, json.JSONDecodeError, AttributeError):
            return
        ctx = ToolContext(app, self.chat_id)
        for s in skills[:2]:
            if s.get("name") and s.get("steps"):
                await app.notifier.send_text("🧠 Sık yaptığın bir iş fark ettim, beceri olarak kaydedeyim mi?")
                await app.agent.execute_tool(ctx, "save_skill",
                                             {"name": s["name"], "trigger": s.get("trigger", ""), "steps": s["steps"]})
