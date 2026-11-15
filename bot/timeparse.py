"""Türkçe zaman ifadelerini zamanlayıcı biçimine çevirir.

Desteklenenler:
  08:00                     → her gün 08:00
  her gün 08:00             → her gün
  hafta içi 08:30           → pzt-cum
  hafta sonu 10:00          → cmt-paz
  pzt,çar,cum 07:15         → belirli günler
  her pazartesi 09:00
  0 8 * * *                 → cron
  +30dk / +2saat / +1gün    → bir kere, şu kadar sonra
  30 dakika sonra / 2 saat sonra
  yarın 09:00 / bugün 18:00
  2026-11-20 14:00 / 20.11.2026 14:00
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter

DAYS = {
    "pazartesi": 1, "pzt": 1, "salı": 2, "sali": 2, "sal": 2, "çarşamba": 3, "carsamba": 3, "çar": 3, "car": 3,
    "perşembe": 4, "persembe": 4, "per": 4, "cuma": 5, "cum": 5, "cumartesi": 6, "cmt": 6, "pazar": 0, "paz": 0,
}
UNITS = {"dk": 1, "dakika": 1, "m": 1, "dak": 1, "s": 60, "sa": 60, "saat": 60, "h": 60, "g": 1440, "gün": 1440,
         "gun": 1440, "d": 1440}


class WhenError(ValueError):
    pass


def _hm(s: str) -> tuple[int, int]:
    m = re.search(r"(\d{1,2})[:.](\d{2})", s)
    if not m:
        raise WhenError("Saat bulunamadı (örnek: 08:00)")
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise WhenError("Geçersiz saat")
    return h, mi


def parse_when(text: str, tz: ZoneInfo, now: datetime | None = None) -> dict:
    s = text.strip().lower()
    now = now or datetime.now(tz)

    if croniter.is_valid(s) and len(s.split()) == 5:
        return {"cron": s}

    m = re.fullmatch(r"\+?\s*(\d+)\s*([a-zçğışöü]+)(\s+sonra)?", s)
    if m and (s.startswith("+") or m.group(3)):
        unit = m.group(2)
        if unit not in UNITS:
            raise WhenError(f"Bilinmeyen birim: {unit}")
        return {"run_at": (now + timedelta(minutes=int(m.group(1)) * UNITS[unit])).timestamp()}

    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s) or re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        g = m.groups()
        y, mo, d = (int(g[0]), int(g[1]), int(g[2])) if len(g[0]) == 4 else (int(g[2]), int(g[1]), int(g[0]))
        rest = s[m.end():]
        h, mi = _hm(rest) if re.search(r"\d{1,2}[:.]\d{2}", rest) else (9, 0)
        dt = datetime(y, mo, d, h, mi, tzinfo=tz)
        if dt <= now:
            raise WhenError("Bu tarih geçmişte kaldı")
        return {"run_at": dt.timestamp()}

    if s.startswith(("yarın", "yarin", "bugün", "bugun")):
        h, mi = _hm(s)
        base = now + timedelta(days=1) if s.startswith("yar") else now
        dt = base.replace(hour=h, minute=mi, second=0, microsecond=0)
        if dt <= now:
            raise WhenError("Bu saat bugün için geçti")
        return {"run_at": dt.timestamp()}

    h, mi = _hm(s)
    if "hafta içi" in s or "hafta ici" in s:
        dow = "1-5"
    elif "hafta sonu" in s:
        dow = "0,6"
    else:
        found = []
        for word in re.findall(r"[a-zçğışöü]+", s):
            w = re.sub(r"(leri|ları|lari|si|sı|i|ı)$", "", word) if word not in DAYS else word
            if word in DAYS:
                found.append(DAYS[word])
            elif w in DAYS:
                found.append(DAYS[w])
        dow = ",".join(str(d) for d in sorted(set(found))) if found else "*"
    return {"cron": f"{mi} {h} * * {dow}"}


def next_run(cron: str, tz: ZoneInfo, after: datetime | None = None) -> float:
    base = after or datetime.now(tz)
    return croniter(cron, base).get_next(datetime).timestamp()


def describe(sched: dict, tz: ZoneInfo) -> str:
    if sched.get("cron"):
        return f"tekrar: `{sched['cron']}`"
    return "bir kez: " + datetime.fromtimestamp(sched["run_at"], tz).strftime("%d.%m.%Y %H:%M")
