"""Cron expressions (5 fields) and friendly schedules, in pure Python, plus missed-run detection."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

FRIENDLY = {
    "hourly": "0 * * * *", "daily": "0 9 * * *", "nightly": "0 2 * * *", "weekly": "0 9 * * 1",
    "monthly": "0 9 1 * *", "weekdays": "0 9 * * 1-5",
    "her saat": "0 * * * *", "her gün": "0 9 * * *", "her gece": "0 2 * * *", "her hafta": "0 9 * * 1",
    "her ay": "0 9 1 * *", "hafta içi": "0 9 * * 1-5", "her pazartesi": "0 9 * * 1", "her sabah": "0 8 * * *",
}
DAY_NAMES = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
MONTH_NAMES = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                           "nov", "dec"], 1)}


def _field(text: str, lo: int, hi: int, names: dict | None = None) -> set[int]:
    out: set[int] = set()
    for part in text.lower().split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/")
            step = int(s)
        if names:
            for k, v in names.items():
                part = part.replace(k, str(v))
        if part in ("*", ""):
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-"))
        else:
            a = b = int(part)
            if step != 1:
                b = hi
        if a < lo or b > hi or a > b:
            raise ValueError(f"{text}: out of range {lo}-{hi}")
        out.update(range(a, b + 1, step))
    return out


class Cron:
    def __init__(self, expr: str):
        expr = FRIENDLY.get(expr.strip().lower(), expr.strip())
        m = re.fullmatch(r"(?i)(?:every|her)\s+(\d+)\s*(m|min|minutes|dakika|h|hours|saat)", expr)
        if m:
            n = int(m.group(1))
            expr = f"*/{n} * * * *" if m.group(2)[0] in "md" else f"0 */{n} * * *"
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError("A schedule needs 5 cron fields (minute hour day month weekday) or a word like daily, "
                             "weekly, 'her gece', 'every 15 minutes'.")
        self.expr = expr
        self.minute = _field(parts[0], 0, 59)
        self.hour = _field(parts[1], 0, 23)
        self.dom = _field(parts[2], 1, 31)
        self.month = _field(parts[3], 1, 12, MONTH_NAMES)
        dow = _field(parts[4].replace("7", "0"), 0, 6, DAY_NAMES)
        self.dow = dow
        self.dom_any, self.dow_any = parts[2] == "*", parts[4] == "*"

    def matches(self, t: datetime) -> bool:
        if t.minute not in self.minute or t.hour not in self.hour or t.month not in self.month:
            return False
        dom_ok = t.day in self.dom
        dow_ok = (t.isoweekday() % 7) in self.dow
        if self.dom_any or self.dow_any:
            return dom_ok and dow_ok
        return dom_ok or dow_ok  # cron's rule: either day field may match

    def next_after(self, t: datetime) -> datetime:
        t = t.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(60 * 24 * 370):
            if self.matches(t):
                return t
            if t.hour not in self.hour or t.month not in self.month:
                t = t.replace(minute=0) + timedelta(hours=1)
            else:
                t += timedelta(minutes=1)
        raise ValueError(f"{self.expr} never runs")

    def last_before(self, t: datetime, limit_days: int = 400) -> datetime | None:
        t = t.replace(second=0, microsecond=0)
        end = t - timedelta(days=limit_days)
        while t > end:
            if self.matches(t):
                return t
            if t.hour not in self.hour or t.month not in self.month:
                t = t.replace(minute=59) - timedelta(hours=1)
            else:
                t -= timedelta(minutes=1)
        return None


def describe(expr: str) -> str:
    c = Cron(expr)
    nxt = c.next_after(datetime.now())
    return f"{c.expr} (next: {nxt:%Y-%m-%d %H:%M})"
