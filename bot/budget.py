"""Maliyet takibi ve harcama limitleri (aylık 10 $ kredi için)."""
from __future__ import annotations

import time
from datetime import datetime

from .config import Config
from .db import DB

# USD / 1M token (girdi, çıktı). Kaynak: Google AI Studio fiyat sayfası, Kasım 2026.
# Fiyatlar değişebilir; .env içinden PRICE_<model> ile değil, burada güncelleyin.
PRICES: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    # 1 Ocak 2027'de 1.50 / 7.50'ye çıkıyor; temkinli olmak için yeni fiyat kullanılıyor.
    "gemini-3.8-flash": (1.50, 7.50),
    "gemini-3.6-flash": (1.50, 7.50),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-3.1-pro-preview": (2.00, 12.00),
    "gemini-3.8-flash-lite-tts": (1.00, 12.00),
    "gemini-3.8-flash-tts": (1.00, 18.00),
}
DEFAULT_PRICE = (2.00, 12.00)  # bilinmeyen model: pahalı varsay
SEARCH_COST = 0.014  # aylık 5000 ücretsizden sonra arama başına


class BudgetExceeded(Exception):
    pass


def price_of(model: str) -> tuple[float, float]:
    for key, p in PRICES.items():
        if model.startswith(key):
            return p
    return DEFAULT_PRICE


class Budget:
    def __init__(self, cfg: Config, db: DB):
        self.cfg = cfg
        self.db = db

    def _now(self) -> datetime:
        return datetime.now(self.cfg.tz)

    def record(self, model: str, input_tokens: int, output_tokens: int, purpose: str = "",
               cached_tokens: int = 0) -> float:
        """Önbellekten gelen girdi tokenleri ~%90 indirimlidir (Gemini örtük önbellek)."""
        pin, pout = price_of(model)
        cached = min(cached_tokens, input_tokens)
        cost = ((input_tokens - cached) * pin + cached * pin * 0.1 + output_tokens * pout) / 1_000_000
        now = self._now()
        self.db.execute(
            "INSERT INTO usage(ts,day,month,model,input_tokens,output_tokens,cost,purpose) VALUES(?,?,?,?,?,?,?,?)",
            (time.time(), now.strftime("%Y-%m-%d"), now.strftime("%Y-%m"), model,
             input_tokens, output_tokens, cost, purpose))
        return cost

    def record_search(self) -> None:
        now = self._now()
        month = now.strftime("%Y-%m")
        count = self.db.get(f"searches:{month}", 0) + 1
        self.db.set(f"searches:{month}", count)
        cost = SEARCH_COST if count > 5000 else 0.0
        if cost:
            self.db.execute(
                "INSERT INTO usage(ts,day,month,model,input_tokens,output_tokens,cost,purpose) VALUES(?,?,?,?,?,?,?,?)",
                (time.time(), now.strftime("%Y-%m-%d"), month, "google_search", 0, 0, cost, "arama"))

    def spent_today(self) -> float:
        r = self.db.one("SELECT COALESCE(SUM(cost),0) c FROM usage WHERE day=?", (self._now().strftime("%Y-%m-%d"),))
        return r["c"]

    def spent_month(self) -> float:
        r = self.db.one("SELECT COALESCE(SUM(cost),0) c FROM usage WHERE month=?", (self._now().strftime("%Y-%m"),))
        return r["c"]

    def choose_model(self, tier: str) -> str:
        """Limit durumuna göre model seç. Aylık limit aşıldıysa hata verir."""
        if self.spent_month() >= self.cfg.monthly_limit_usd:
            raise BudgetExceeded(
                f"Aylık bütçe limiti ({self.cfg.monthly_limit_usd:.2f} $) doldu. "
                "MONTHLY_LIMIT_USD değerini artırabilir veya ay başını bekleyebilirsin.")
        if tier == "smart" and self.spent_today() < self.cfg.daily_limit_usd:
            return self.cfg.model_smart
        return self.cfg.model_fast

    def report(self) -> str:
        rows = self.db.all(
            "SELECT model, SUM(input_tokens) i, SUM(output_tokens) o, SUM(cost) c FROM usage WHERE month=? GROUP BY model",
            (self._now().strftime("%Y-%m"),))
        lines = [f"Bugün: {self.spent_today():.4f} $ (günlük limit {self.cfg.daily_limit_usd:.2f} $)",
                 f"Bu ay: {self.spent_month():.4f} $ (aylık limit {self.cfg.monthly_limit_usd:.2f} $)"]
        for r in rows:
            lines.append(f"• {r['model']}: {r['i']:,} girdi / {r['o']:,} çıktı token → {r['c']:.4f} $")
        return "\n".join(lines)
