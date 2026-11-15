"""Uzman ajanlar ("Dot"lar). Varsayılanlar + kullanıcının oluşturdukları."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from .db import DB


@dataclass
class AgentDef:
    name: str
    role: str
    instructions: str
    groups: list[str]
    tier: str = "fast"   # fast = ucuz model, smart = akıllı model
    builtin: bool = True


DEFAULTS = {
    "asistan": AgentDef(
        "asistan", "Ana kişisel asistan",
        "Kullanıcının her işine yardım eden ana asistansın. Basit işleri kendin yap; uzun araştırma, "
        "web sitesinde işlem, dosya/terminal işi veya telefon ekranını kontrol gerekiyorsa uygun uzmana devret.",
        ["core", "pages", "schedule", "skills", "agents", "web", "google", "phone"]),
    "arastirmaci": AgentDef(
        "arastirmaci", "Derin araştırma uzmanı",
        "Konuyu birden çok kaynaktan araştır, karşılaştır, kaynakları belirt. Uzun sonuçları sayfa olarak kaydet.",
        ["core", "pages", "web", "browser"], "smart"),
    "operator": AgentDef(
        "operator", "Bilgisayar, tarayıcı ve telefon ekranı operatörü",
        "Kendi tarayıcın, dosyaların, terminalin ve telefonun ekranı üzerinden adım adım iş yaparsın. "
        "Telefon ekranında: önce phone_screen_control ile oturum aç, sonra phone_screen_look ile bak, "
        "koordinatlara dokun, her adımdan sonra tekrar bak. Ödeme/satın alma gibi adımlarda dur ve kullanıcıya sor.",
        ["core", "pages", "web", "browser", "computer", "phone", "phone_screen"], "smart"),
    "yazar": AgentDef(
        "yazar", "Yazı ve belge uzmanı",
        "E-posta, rapor, mesaj, sunum metni yazarsın. Kullanıcının üslubuna uy. Belgeleri Google Docs'a veya sayfaya kaydet.",
        ["core", "pages", "google"]),
}


class AgentStore:
    def __init__(self, db: DB):
        self.db = db

    def all(self) -> dict[str, AgentDef]:
        out = dict(DEFAULTS)
        for r in self.db.all("SELECT * FROM agents"):
            out[r["name"]] = AgentDef(r["name"], r["role"], r["instructions"], json.loads(r["groups"]),
                                      r["tier"], builtin=False)
        return out

    def get(self, name: str) -> AgentDef:
        return self.all().get(name) or DEFAULTS["asistan"]

    def save(self, name: str, role: str, instructions: str, groups: list[str], tier: str = "fast") -> None:
        if "core" not in groups:
            groups = ["core", *groups]
        self.db.execute("INSERT OR REPLACE INTO agents(name,role,instructions,groups,tier,created) VALUES(?,?,?,?,?,?)",
                        (name, role, instructions, json.dumps(groups), tier, time.time()))

    def delete(self, name: str) -> bool:
        return self.db.execute("DELETE FROM agents WHERE name=?", (name,)).rowcount > 0
