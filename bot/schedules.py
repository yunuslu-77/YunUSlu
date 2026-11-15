"""Zamanlanmış görevlerin kaydı (sesle, yazıyla veya /zamanla komutuyla kurulur)."""
from __future__ import annotations

import time
from datetime import datetime

from .db import DB
from .timeparse import describe, next_run


def add_schedule(db: DB, tz, kind: str, payload: str, cron: str | None = None, run_at: float | None = None,
                 agent: str = "asistan") -> int:
    """kind: 'prompt' (ajan çalıştırır) veya 'message' (sadece hatırlatma mesajı yollar)."""
    if not cron and not run_at:
        raise ValueError("cron veya run_at gerekli")
    nr = next_run(cron, tz) if cron else run_at
    return db.execute(
        "INSERT INTO schedules(kind,payload,cron,run_at,next_run,agent,enabled,created) VALUES(?,?,?,?,?,?,1,?)",
        (kind, payload, cron, run_at, nr, agent, time.time())).lastrowid


def list_schedules(db: DB) -> list[dict]:
    return db.all("SELECT * FROM schedules WHERE enabled=1 ORDER BY next_run")


def delete_schedule(db: DB, sid: int) -> bool:
    return db.execute("UPDATE schedules SET enabled=0 WHERE id=? AND enabled=1", (sid,)).rowcount > 0


def due_schedules(db: DB, now: float | None = None) -> list[dict]:
    return db.all("SELECT * FROM schedules WHERE enabled=1 AND next_run<=?", (now or time.time(),))


def mark_ran(db: DB, s: dict, tz) -> None:
    now = time.time()
    if s["cron"]:
        db.execute("UPDATE schedules SET last_run=?, next_run=? WHERE id=?",
                   (now, next_run(s["cron"], tz, datetime.now(tz)), s["id"]))
    else:
        db.execute("UPDATE schedules SET last_run=?, enabled=0 WHERE id=?", (now, s["id"]))


def format_schedule(s: dict, tz) -> str:
    nxt = datetime.fromtimestamp(s["next_run"], tz).strftime("%d.%m %H:%M")
    kind = "⏰ hatırlatma" if s["kind"] == "message" else f"🤖 görev ({s['agent']})"
    return f"#{s['id']} {kind} — {describe(s, tz)} — sıradaki: {nxt}\n   {s['payload'][:150]}"
