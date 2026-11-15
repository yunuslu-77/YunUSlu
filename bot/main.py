"""YAi'yi başlatır: Telegram + zamanlayıcı + panel/telefon sunucusu (tek süreç)."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

import uvicorn
from telegram import BotCommand

from .app import App
from .config import Config
from .dashboard import create_app
from .scheduler import Scheduler
from .telegram_ui import TelegramUI

COMMANDS = [("yardim", "Yardım ve örnekler"), ("brifing", "Şimdi brifing hazırla"), ("zamanla", "Görev zamanla"),
            ("hatirlat", "Hatırlatıcı kur"), ("zamanlar", "Zamanlayıcıları listele"), ("zamansil", "Zamanlayıcı sil"),
            ("hafiza", "Hafızayı göster"), ("ajanlar", "Uzman ajanlar"), ("ajan", "Ajan değiştir"),
            ("telefon", "Telefon durumu"), ("google", "Google hesabını bağla"), ("ses", "Sesli cevap aç/kapat"),
            ("bildirim", "Telefon bildirimlerini ilet"), ("onaylar", "Bekleyen onaylar"), ("maliyet", "API harcaması"),
            ("sayfalar", "Notlar/raporlar"), ("beceriler", "Öğrenilen beceriler"), ("sifirla", "Sohbeti temizle")]


def check(cfg: Config) -> list[str]:
    problems = []
    if not cfg.gemini_api_key:
        problems.append("GEMINI_API_KEY eksik")
    if not cfg.telegram_token:
        problems.append("TELEGRAM_TOKEN eksik")
    if not cfg.dashboard_token or len(cfg.dashboard_token) < 16:
        problems.append("DASHBOARD_TOKEN eksik veya kısa (en az 16 karakter)")
    if not cfg.phone_token or len(cfg.phone_token) < 16:
        problems.append("PHONE_TOKEN eksik veya kısa (en az 16 karakter)")
    return problems


async def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = Config.from_env()
    problems = check(cfg)
    if problems:
        print("❌ Ayar hatası:\n - " + "\n - ".join(problems) + "\n.env.example dosyasına bak.")
        sys.exit(1)
    if not cfg.owner_id:
        print("⚠️ TELEGRAM_OWNER_ID yok: bota /start yaz, sana ID'ni söyleyecek.")

    app = App(cfg)
    ui = TelegramUI(app)
    scheduler = Scheduler(app)
    server = uvicorn.Server(uvicorn.Config(create_app(app), host=cfg.dashboard_host, port=cfg.dashboard_port,
                                           log_level="warning", ws_ping_interval=30))

    tg = ui.application
    await tg.initialize()
    await tg.bot.set_my_commands([BotCommand(c, d) for c, d in COMMANDS])
    await tg.start()
    await tg.updater.start_polling(drop_pending_updates=False)
    scheduler.start()
    web = asyncio.create_task(server.serve())
    logging.info("✅ %s çalışıyor. Panel: http://<sunucu>:%s/?token=...", cfg.bot_name, cfg.dashboard_port)
    if cfg.owner_id:
        try:
            await app.notifier.send_text(f"🟢 {cfg.bot_name} yeniden başladı ve hazır.")
        except Exception:
            logging.exception("Başlangıç mesajı gönderilemedi")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()

    logging.info("Kapanıyor...")
    await scheduler.stop()
    server.should_exit = True
    await tg.updater.stop()
    await tg.stop()
    await tg.shutdown()
    await app.browser.close()
    await web


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
