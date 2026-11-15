"""Telegram arayüzü: sohbet, ses, foto, dosya, onay butonları ve komutlar."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler,
                          filters)

from . import schedules as S
from .timeparse import WhenError, describe, parse_when

log = logging.getLogger(__name__)
MAX_LEN = 4000

HELP = """🤖 {name} — 7/24 kişisel asistanın

Bana normal yazabilir, sesli mesaj, fotoğraf veya dosya gönderebilirsin. Örnekler:
• "Her sabah 8'de bana hava durumu, takvim ve önemli mailleri özetle"
• "Yarın 14:00'te Ahmet'i aramayı hatırlat"
• "Okunmamış maillerimi özetle", "Annemin son SMS'i ne?"
• "Telefonumu bul", "Fener aç", "7:30'a alarm kur"
• "Şu konuyu araştır ve rapor yaz"

⏰ Zamanlayıcı (elle)
/zamanla <ne zaman> | <görev>   → ör. /zamanla 08:00 | Sabah brifingi hazırla
/hatirlat <ne zaman> | <mesaj>  → ör. /hatirlat yarın 09:00 | Faturayı öde
/zamanlar  /zamansil <id>
Zaman: 08:00 · hafta içi 08:30 · pzt,cum 09:00 · +30dk · 2 saat sonra · yarın 09:00 · 2026-12-01 10:00 · cron

🧠 /hafiza  /unut <id>  /beceriler  /sayfalar  /sifirla
🤝 /ajanlar  /ajan <ad>
🔗 /google (hesap bağla)  /telefon [ac|kapat]  /bildirim [ac|kapat]
🔊 /ses [ac|kapat]   💸 /maliyet   ✅ /onaylar   ☀️ /brifing
"""

BRIEFING = ("Sabah brifingi hazırla: bugünün tarihi, hava durumu (hafızadaki şehir; yoksa İstanbul), bugünkü takvim "
            "etkinlikleri, son 24 saatteki önemli okunmamış e-postalar ve telefon bağlıysa pil durumu. Kısa ve maddeli yaz.")


def split(text: str) -> list[str]:
    parts = []
    while len(text) > MAX_LEN:
        cut = text.rfind("\n", 0, MAX_LEN)
        cut = cut if cut > 1000 else MAX_LEN
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    parts.append(text)
    return [p for p in parts if p.strip()]


class TelegramNotifier:
    def __init__(self, application: Application, chat_id: int):
        self.application = application
        self.chat_id = chat_id

    @property
    def bot(self):
        return self.application.bot

    async def send_text(self, text: str, buttons=None):
        if not self.chat_id:
            log.warning("TELEGRAM_OWNER_ID yok, mesaj gönderilemedi: %s", text[:80])
            return
        chunks = split(text) or ["👍"]
        for i, chunk in enumerate(chunks):
            await self.bot.send_message(self.chat_id, chunk,
                                        reply_markup=buttons if i == len(chunks) - 1 else None,
                                        disable_web_page_preview=True)

    async def send_photo(self, data: bytes, caption: str = ""):
        await self.bot.send_photo(self.chat_id, data, caption=caption[:1000])

    async def send_document(self, data: bytes, filename: str):
        await self.bot.send_document(self.chat_id, data, filename=filename)

    async def send_voice(self, data: bytes):
        await self.bot.send_voice(self.chat_id, data)

    async def ask_approval(self, approval_id: int, summary: str):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Onayla", callback_data=f"ap:{approval_id}:1"),
                                    InlineKeyboardButton("❌ İptal", callback_data=f"ap:{approval_id}:0")]])
        await self.send_text(f"🔐 Onay gerekiyor (#{approval_id})\n\n{summary}", buttons=kb)


class TelegramUI:
    def __init__(self, app):
        self.app = app
        self.application = (Application.builder().token(app.cfg.telegram_token)
                            .concurrent_updates(True).build())
        app.notifier = TelegramNotifier(self.application, app.cfg.owner_id)
        self._register()

    # ------------------------------------------------------------------ yardımcılar
    def _owner(self, update: Update) -> bool:
        return bool(self.app.cfg.owner_id) and update.effective_user and update.effective_user.id == self.app.cfg.owner_id

    async def _guard(self, update: Update) -> bool:
        if self._owner(update):
            return True
        if update.effective_message:
            uid = update.effective_user.id if update.effective_user else "?"
            if not self.app.cfg.owner_id:
                await update.effective_message.reply_text(
                    f"👋 Kurulum: Kullanıcı ID'n {uid}. Bunu .env dosyasında TELEGRAM_OWNER_ID={uid} olarak yaz ve botu yeniden başlat.")
            else:
                await update.effective_message.reply_text("⛔ Bu bot özeldir.")
        return False

    @contextlib.asynccontextmanager
    async def _typing(self, chat_id: int):
        async def loop():
            while True:
                with contextlib.suppress(Exception):
                    await self.application.bot.send_chat_action(chat_id, ChatAction.TYPING)
                await asyncio.sleep(4)
        t = asyncio.create_task(loop())
        try:
            yield
        finally:
            t.cancel()

    async def _process(self, update: Update, parts: list, history_text: str):
        chat_id = update.effective_chat.id
        async with self._typing(chat_id):
            try:
                text = await self.app.agent.handle_user(chat_id, parts, history_text)
            except Exception as e:
                log.exception("İşlem hatası")
                text = f"⚠️ Bir hata oluştu: {type(e).__name__}: {e}"
        await self.app.deliver(text)

    # ------------------------------------------------------------------ mesajlar
    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update):
            return
        text = update.message.text or ""
        if text.startswith("http://localhost") and self.app.google.waiting:
            try:
                await asyncio.to_thread(self.app.google.finish, text)
                await update.message.reply_text("✅ Google hesabın bağlandı! Artık Gmail, Takvim ve Drive'ı kullanabilirim.")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Google bağlantısı başarısız: {e}\n/google ile tekrar dene.")
            return
        await self._process(update, [text], text)

    async def on_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update):
            return
        media = update.message.voice or update.message.audio
        f = await media.get_file()
        data = bytes(await f.download_as_bytearray())
        mime = media.mime_type or "audio/ogg"
        prompt = "Kullanıcı sesli mesaj gönderdi. Sesi dinle ve isteğini yerine getir (sesi yazıya dökmene gerek yok)."
        await self._process(update, [prompt, (data, mime)], "[Sesli mesaj]")

    async def on_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update):
            return
        f = await update.message.photo[-1].get_file()
        data = bytes(await f.download_as_bytearray())
        caption = update.message.caption or "Bu fotoğrafa bak ve ne gördüğünü anlat."
        await self._process(update, [caption, (data, "image/jpeg")], f"[Fotoğraf] {caption}")

    async def on_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update):
            return
        doc = update.message.document
        f = await doc.get_file()
        data = bytes(await f.download_as_bytearray())
        name = (doc.file_name or "dosya").replace("/", "_")
        dest = self.app.cfg.workspace / "gelen" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        caption = update.message.caption or "Bu dosyaya bak."
        parts = [f"Kullanıcı bir dosya gönderdi, çalışma klasörüne 'gelen/{name}' olarak kaydedildi. {caption}"]
        mime = doc.mime_type or ""
        if len(data) < 15_000_000 and (mime == "application/pdf" or mime.startswith(("image/", "text/", "audio/"))):
            parts.append((data, mime))
        await self._process(update, parts, f"[Dosya: {name}] {caption}")

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        if not self._owner(update):
            await q.answer("⛔")
            return
        await q.answer()
        try:
            _, aid, ok = q.data.split(":")
        except ValueError:
            return
        approve = ok == "1"
        with contextlib.suppress(Exception):
            await q.edit_message_text(q.message.text + ("\n\n✅ Onaylandı" if approve else "\n\n❌ İptal edildi"))
        async with self._typing(q.message.chat_id):
            try:
                text = await self.app.agent.resolve_approval(int(aid), approve)
            except Exception as e:
                text = f"⚠️ İşlem sırasında hata: {e}"
        await self.app.deliver(text)

    # ------------------------------------------------------------------ komutlar
    async def cmd_start(self, update: Update, context):
        if await self._guard(update):
            await update.message.reply_text(HELP.format(name=self.app.cfg.bot_name))

    async def _schedule_cmd(self, update: Update, context, kind: str):
        if not await self._guard(update):
            return
        raw = " ".join(context.args)
        if "|" not in raw:
            ex = "/zamanla 08:00 | Sabah brifingi hazırla" if kind == "prompt" else "/hatirlat yarın 09:00 | Faturayı öde"
            await update.message.reply_text(f"Kullanım: {ex}")
            return
        when, payload = (x.strip() for x in raw.split("|", 1))
        try:
            w = parse_when(when, self.app.cfg.tz)
        except WhenError as e:
            await update.message.reply_text(f"⚠️ {e}")
            return
        sid = S.add_schedule(self.app.db, self.app.cfg.tz, kind, payload, w.get("cron"), w.get("run_at"))
        await update.message.reply_text(f"✅ #{sid} kuruldu — {describe(w, self.app.cfg.tz)}\n{payload}")

    async def cmd_zamanla(self, update, context):
        await self._schedule_cmd(update, context, "prompt")

    async def cmd_hatirlat(self, update, context):
        await self._schedule_cmd(update, context, "message")

    async def cmd_zamanlar(self, update, context):
        if await self._guard(update):
            items = S.list_schedules(self.app.db)
            await self.app.notifier.send_text(
                "\n".join(S.format_schedule(s, self.app.cfg.tz) for s in items) or "Kurulu zamanlayıcı yok.")

    async def cmd_zamansil(self, update, context):
        if await self._guard(update):
            ok = context.args and context.args[0].isdigit() and S.delete_schedule(self.app.db, int(context.args[0]))
            await update.message.reply_text("🗑️ Silindi." if ok else "Kullanım: /zamansil <id>")

    async def cmd_hafiza(self, update, context):
        if await self._guard(update):
            mem = self.app.db.memories()
            await self.app.notifier.send_text("\n".join(f"#{m['id']} {m['fact']}" for m in mem) or "Hafıza boş.")

    async def cmd_unut(self, update, context):
        if await self._guard(update):
            ok = context.args and context.args[0].isdigit() and self.app.db.delete_memory(int(context.args[0]))
            await update.message.reply_text("🧹 Unutuldu." if ok else "Kullanım: /unut <id>")

    async def cmd_ajanlar(self, update, context):
        if await self._guard(update):
            active = self.app.db.get(f"active_agent:{update.effective_chat.id}", "asistan")
            lines = [f"{'👉' if n == active else '•'} {n}: {a.role}" for n, a in self.app.agents.all().items()]
            await update.message.reply_text("\n".join(lines) + "\n\nDeğiştirmek için: /ajan <ad>")

    async def cmd_ajan(self, update, context):
        if not await self._guard(update):
            return
        name = (context.args or ["asistan"])[0]
        if name not in self.app.agents.all():
            await update.message.reply_text("Böyle bir ajan yok. /ajanlar")
            return
        self.app.db.set(f"active_agent:{update.effective_chat.id}", name)
        await update.message.reply_text(f"🤝 Artık {name} ile konuşuyorsun.")

    async def cmd_maliyet(self, update, context):
        if await self._guard(update):
            await update.message.reply_text("💸 " + self.app.budget.report())

    async def _toggle(self, update, context, key: str, label: str, default: bool = False):
        arg = (context.args or [""])[0].lower()
        if arg in ("ac", "aç", "on"):
            self.app.db.set(key, True)
        elif arg in ("kapat", "off"):
            self.app.db.set(key, False)
        return f"{label}: {'açık ✅' if self.app.db.get(key, default) else 'kapalı ⛔'}"

    async def cmd_ses(self, update, context):
        if await self._guard(update):
            await update.message.reply_text(await self._toggle(update, context, "voice_replies", "🔊 Sesli cevap"))

    async def cmd_bildirim(self, update, context):
        if await self._guard(update):
            await update.message.reply_text(
                await self._toggle(update, context, "phone_forward_notifications", "📱 Telefon bildirimi iletme", True))

    async def cmd_telefon(self, update, context):
        if not await self._guard(update):
            return
        msg = await self._toggle(update, context, "phone_enabled", "📱 Telefon erişimi", True)
        st = self.app.phone.status()
        if st["online"]:
            seen = datetime.fromtimestamp(st["last_seen"], self.app.cfg.tz).strftime("%H:%M:%S")
            msg += f"\nBağlı: {st['device']} (son sinyal {seen})"
        else:
            msg += "\nTelefon şu an bağlı değil. Termux'ta köprüyü başlat: ~/yai/start.sh"
        await update.message.reply_text(msg)

    async def cmd_google(self, update, context):
        if not await self._guard(update):
            return
        if self.app.google.connected() and (context.args or [""])[0] != "yeniden":
            await update.message.reply_text("✅ Google hesabın zaten bağlı. Yeniden bağlamak için: /google yeniden")
            return
        try:
            url = self.app.google.start()
        except FileNotFoundError as e:
            await update.message.reply_text(f"⚠️ {e}")
            return
        await update.message.reply_text(
            "🔗 1) Bu bağlantıyı aç ve Google hesabınla izin ver:\n\n" + url +
            "\n\n2) Sonunda 'bu siteye ulaşılamıyor' sayfası açılacak (normal).\n"
            "3) Adres çubuğundaki http://localhost... ile başlayan adresin TAMAMINI kopyalayıp bana gönder.",
            disable_web_page_preview=True)

    async def cmd_onaylar(self, update, context):
        if not await self._guard(update):
            return
        rows = self.app.db.all("SELECT id, summary FROM approvals WHERE status='pending' ORDER BY id")
        if not rows:
            await update.message.reply_text("Bekleyen onay yok.")
        for r in rows:
            await self.app.notifier.ask_approval(r["id"], r["summary"])

    async def cmd_sayfalar(self, update, context):
        if await self._guard(update):
            rows = self.app.db.all("SELECT id,title FROM pages ORDER BY updated DESC LIMIT 30")
            await update.message.reply_text("\n".join(f"#{r['id']} {r['title']}" for r in rows) or "Sayfa yok.")

    async def cmd_beceriler(self, update, context):
        if await self._guard(update):
            rows = self.app.db.all("SELECT name,trigger,uses FROM skills")
            await update.message.reply_text(
                "\n".join(f"🧠 {r['name']} ({r['uses']} kez): {r['trigger']}" for r in rows) or "Henüz beceri yok.")

    async def cmd_sifirla(self, update, context):
        if await self._guard(update):
            self.app.db.clear_messages(update.effective_chat.id)
            await update.message.reply_text("🧽 Sohbet geçmişi temizlendi (kalıcı hafıza duruyor).")

    async def cmd_brifing(self, update, context):
        if await self._guard(update):
            await self._process(update, [BRIEFING], "[Brifing istendi]")

    def _register(self):
        a = self.application
        for name, fn in [("start", self.cmd_start), ("yardim", self.cmd_start), ("help", self.cmd_start),
                         ("zamanla", self.cmd_zamanla), ("hatirlat", self.cmd_hatirlat),
                         ("zamanlar", self.cmd_zamanlar), ("zamansil", self.cmd_zamansil),
                         ("hafiza", self.cmd_hafiza), ("unut", self.cmd_unut), ("ajanlar", self.cmd_ajanlar),
                         ("ajan", self.cmd_ajan), ("maliyet", self.cmd_maliyet), ("ses", self.cmd_ses),
                         ("bildirim", self.cmd_bildirim), ("telefon", self.cmd_telefon), ("google", self.cmd_google),
                         ("onaylar", self.cmd_onaylar), ("sayfalar", self.cmd_sayfalar),
                         ("beceriler", self.cmd_beceriler), ("sifirla", self.cmd_sifirla), ("brifing", self.cmd_brifing)]:
            a.add_handler(CommandHandler(name, fn))
        a.add_handler(CallbackQueryHandler(self.on_callback, pattern=r"^ap:"))
        a.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.on_voice))
        a.add_handler(MessageHandler(filters.PHOTO, self.on_photo))
        a.add_handler(MessageHandler(filters.Document.ALL, self.on_document))
        a.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))
