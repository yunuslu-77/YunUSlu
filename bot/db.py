"""SQLite veritabanı: hafıza, geçmiş, zamanlayıcılar, onaylar, maliyet, kayıtlar."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY, chat_id INTEGER, role TEXT, text TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY, fact TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY, title TEXT, content TEXT, created REAL, updated REAL
);
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY, kind TEXT, payload TEXT, cron TEXT, run_at REAL,
    next_run REAL, agent TEXT, enabled INTEGER DEFAULT 1, created REAL, last_run REAL
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY, chat_id INTEGER, tool TEXT, args TEXT, summary TEXT,
    agent TEXT, status TEXT DEFAULT 'pending', result TEXT, created REAL, decided REAL
);
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY, name TEXT UNIQUE, trigger TEXT, steps TEXT, uses INTEGER DEFAULT 0, created REAL
);
CREATE TABLE IF NOT EXISTS agents (
    name TEXT PRIMARY KEY, role TEXT, instructions TEXT, groups TEXT, tier TEXT, created REAL
);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY, ts REAL, day TEXT, month TEXT, model TEXT,
    input_tokens INTEGER, output_tokens INTEGER, cost REAL, purpose TEXT
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY, ts REAL, tool TEXT, args TEXT, result TEXT, ok INTEGER
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY, value TEXT
);
"""


class DB:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # --- düşük seviye -------------------------------------------------
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            r = self.conn.execute(sql, params).fetchone()
            return dict(r) if r else None

    # --- kv ayarlar -----------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        r = self.one("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(r["value"]) if r else default

    def set(self, key: str, value: Any) -> None:
        self.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, json.dumps(value)))

    # --- mesaj geçmişi --------------------------------------------------
    def add_message(self, chat_id: int, role: str, text: str) -> None:
        self.execute("INSERT INTO messages(chat_id,role,text,ts) VALUES(?,?,?,?)",
                     (chat_id, role, text, time.time()))

    def recent_messages(self, chat_id: int, limit: int) -> list[dict]:
        rows = self.all("SELECT role,text,ts FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
                        (chat_id, limit))
        return list(reversed(rows))

    def clear_messages(self, chat_id: int) -> None:
        self.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))

    # --- hafıza ---------------------------------------------------------
    def add_memory(self, fact: str) -> int:
        return self.execute("INSERT INTO memories(fact,ts) VALUES(?,?)", (fact, time.time())).lastrowid

    def memories(self) -> list[dict]:
        return self.all("SELECT id,fact FROM memories ORDER BY id")

    def delete_memory(self, mid: int) -> bool:
        return self.execute("DELETE FROM memories WHERE id=?", (mid,)).rowcount > 0

    # --- denetim kaydı --------------------------------------------------
    def audit(self, tool: str, args: Any, result: Any, ok: bool) -> None:
        self.execute("INSERT INTO audit(ts,tool,args,result,ok) VALUES(?,?,?,?,?)",
                     (time.time(), tool, json.dumps(args, ensure_ascii=False, default=str)[:2000],
                      json.dumps(result, ensure_ascii=False, default=str)[:2000], int(ok)))
