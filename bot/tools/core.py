"""Temel araçlar: zaman, hafıza, sayfalar, zamanlayıcı, beceriler, ajanlar, ayarlar."""
from __future__ import annotations

import time
from datetime import datetime

from .. import schedules as S
from ..timeparse import WhenError, describe, parse_when
from .registry import P, ToolContext, all_groups, tool

DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


@tool("get_datetime", "Şu anki tarih, saat ve günü verir.", "core")
async def get_datetime(ctx: ToolContext):
    now = datetime.now(ctx.app.cfg.tz)
    return {"datetime": now.strftime("%Y-%m-%d %H:%M"), "day": DAYS_TR[now.weekday()], "timezone": ctx.app.cfg.timezone}


# ---------------- hafıza ----------------
@tool("remember", "Kullanıcı hakkında kalıcı bir bilgiyi hafızaya kaydeder (tercih, kişi, adres, alışkanlık...).",
      "core", {"fact": P(str, "Hatırlanacak bilgi, tek cümle")})
async def remember(ctx: ToolContext, fact: str):
    return {"saved_id": ctx.app.db.add_memory(fact)}


@tool("list_memories", "Kalıcı hafızadaki tüm bilgileri listeler.", "core")
async def list_memories(ctx: ToolContext):
    return ctx.app.db.memories()


@tool("forget", "Hafızadan bir bilgiyi siler.", "core", {"memory_id": P(int, "Silinecek hafıza id")})
async def forget(ctx: ToolContext, memory_id: int):
    return {"deleted": ctx.app.db.delete_memory(int(memory_id))}


# ---------------- sayfalar (notlar / raporlar) ----------------
@tool("create_page", "Yeni bir not/rapor sayfası oluşturur (panelde de görünür).", "pages",
      {"title": P(str, "Başlık"), "content": P(str, "İçerik (Markdown)")})
async def create_page(ctx: ToolContext, title: str, content: str):
    now = time.time()
    pid = ctx.app.db.execute("INSERT INTO pages(title,content,created,updated) VALUES(?,?,?,?)",
                             (title, content, now, now)).lastrowid
    return {"page_id": pid}


@tool("update_page", "Bir sayfanın içeriğini değiştirir veya sonuna ekler.", "pages",
      {"page_id": P(int, "Sayfa id"), "content": P(str, "Yeni içerik"),
       "append": P(bool, "True ise sona ekle, False ise üzerine yaz", required=False)})
async def update_page(ctx: ToolContext, page_id: int, content: str, append: bool = False):
    db = ctx.app.db
    page = db.one("SELECT * FROM pages WHERE id=?", (int(page_id),))
    if not page:
        return {"error": "Sayfa bulunamadı"}
    new = (page["content"] + "\n\n" + content) if append else content
    db.execute("UPDATE pages SET content=?, updated=? WHERE id=?", (new, time.time(), int(page_id)))
    return {"ok": True}


@tool("read_page", "Bir sayfanın içeriğini okur.", "pages", {"page_id": P(int, "Sayfa id")})
async def read_page(ctx: ToolContext, page_id: int):
    return ctx.app.db.one("SELECT * FROM pages WHERE id=?", (int(page_id),)) or {"error": "Sayfa bulunamadı"}


@tool("list_pages", "Tüm sayfaları listeler.", "pages")
async def list_pages(ctx: ToolContext):
    return ctx.app.db.all("SELECT id,title,updated FROM pages ORDER BY updated DESC LIMIT 50")


@tool("delete_page", "Bir sayfayı siler.", "pages", {"page_id": P(int, "Sayfa id")}, approval=True,
      summary=lambda a: f"🗑️ {a['page_id']} numaralı sayfayı sil")
async def delete_page(ctx: ToolContext, page_id: int):
    return {"deleted": ctx.app.db.execute("DELETE FROM pages WHERE id=?", (int(page_id),)).rowcount > 0}


# ---------------- zamanlayıcı ----------------
WHEN_HELP = ("Zaman ifadesi: '08:00' (her gün), 'hafta içi 08:30', 'pzt,cum 09:00', 'her pazartesi 10:00', "
             "cron '0 8 * * *', '+30dk', '2 saat sonra', 'yarın 09:00', '2026-11-20 14:00'")


@tool("create_schedule",
      "Zamanlanmış görev kurar. Tekrarlayan işler (sabah brifingi, haftalık özet) veya ileri tarihli görevler için. "
      "Görev zamanı gelince ajan 'task' talimatını çalıştırır ve sonucu kullanıcıya yollar. " + WHEN_HELP,
      "schedule",
      {"when": P(str, "Zaman ifadesi"), "task": P(str, "Zamanı gelince yapılacak iş (ajana talimat)"),
       "agent": P(str, "Görevi yapacak ajan (varsayılan: asistan)", required=False)})
async def create_schedule(ctx: ToolContext, when: str, task: str, agent: str = "asistan"):
    try:
        w = parse_when(when, ctx.app.cfg.tz)
    except WhenError as e:
        return {"error": str(e), "help": WHEN_HELP}
    sid = S.add_schedule(ctx.app.db, ctx.app.cfg.tz, "prompt", task, w.get("cron"), w.get("run_at"), agent or "asistan")
    return {"schedule_id": sid, "when": describe(w, ctx.app.cfg.tz)}


@tool("set_reminder", "Basit hatırlatıcı kurar: zamanı gelince sadece mesajı yollar (yapay zekâ çalıştırmaz, ücretsiz). "
      + WHEN_HELP, "schedule", {"when": P(str, "Zaman ifadesi"), "message": P(str, "Hatırlatma metni")})
async def set_reminder(ctx: ToolContext, when: str, message: str):
    try:
        w = parse_when(when, ctx.app.cfg.tz)
    except WhenError as e:
        return {"error": str(e), "help": WHEN_HELP}
    sid = S.add_schedule(ctx.app.db, ctx.app.cfg.tz, "message", message, w.get("cron"), w.get("run_at"))
    return {"schedule_id": sid, "when": describe(w, ctx.app.cfg.tz)}


@tool("list_schedules", "Kurulu zamanlanmış görev ve hatırlatıcıları listeler.", "schedule")
async def list_schedules(ctx: ToolContext):
    return [S.format_schedule(s, ctx.app.cfg.tz) for s in S.list_schedules(ctx.app.db)]


@tool("delete_schedule", "Zamanlanmış görevi/hatırlatıcıyı siler.", "schedule", {"schedule_id": P(int, "Görev id")})
async def delete_schedule(ctx: ToolContext, schedule_id: int):
    return {"deleted": S.delete_schedule(ctx.app.db, int(schedule_id))}


# ---------------- beceriler (otomatik öğrenme) ----------------
@tool("save_skill", "Tekrar eden bir işi beceri olarak kaydeder. Kullanıcı aynı şeyi isteyince bu adımlar izlenir.",
      "skills", {"name": P(str, "Kısa beceri adı"), "trigger": P(str, "Ne zaman kullanılır (ör. 'kullanıcı haftalık rapor isteyince')"),
                 "steps": P(str, "Adım adım yapılacaklar")}, approval=True,
      summary=lambda a: f"🧠 Yeni beceri kaydet: «{a['name']}»\nNe zaman: {a['trigger']}\nAdımlar:\n{a['steps']}")
async def save_skill(ctx: ToolContext, name: str, trigger: str, steps: str):
    ctx.app.db.execute("INSERT OR REPLACE INTO skills(name,trigger,steps,created) VALUES(?,?,?,?)",
                       (name, trigger, steps, time.time()))
    return {"saved": name}


@tool("list_skills", "Kayıtlı becerileri listeler.", "skills")
async def list_skills(ctx: ToolContext):
    return ctx.app.db.all("SELECT id,name,trigger,uses FROM skills")


@tool("delete_skill", "Bir beceriyi siler.", "skills", {"name": P(str, "Beceri adı")})
async def delete_skill(ctx: ToolContext, name: str):
    return {"deleted": ctx.app.db.execute("DELETE FROM skills WHERE name=?", (name,)).rowcount > 0}


@tool("use_skill", "Bir beceriyi kullandığını kaydeder ve adımlarını getirir.", "skills", {"name": P(str, "Beceri adı")})
async def use_skill(ctx: ToolContext, name: str):
    row = ctx.app.db.one("SELECT * FROM skills WHERE name=?", (name,))
    if not row:
        return {"error": "Beceri yok"}
    ctx.app.db.execute("UPDATE skills SET uses=uses+1 WHERE name=?", (name,))
    return row


# ---------------- ajanlar ----------------
@tool("list_agents", "Mevcut uzman ajanları listeler.", "agents")
async def list_agents(ctx: ToolContext):
    return [{"name": a.name, "role": a.role, "groups": a.groups} for a in ctx.app.agents.all().values()]


@tool("create_agent", "Yeni bir uzman ajan oluşturur (kendi adı, rolü, talimatları ve araç grupları olur). "
      "Araç grupları: " + ", ".join(["core", "pages", "schedule", "skills", "agents", "web", "google", "computer",
                                     "browser", "phone", "phone_screen"]),
      "agents", {"name": P(str, "Ajan adı (küçük harf, boşluksuz)"), "role": P(str, "Kısa rol tanımı"),
                 "instructions": P(str, "Ajanın nasıl davranacağı"),
                 "groups": P("array", "Kullanabileceği araç grupları"),
                 "smart": P(bool, "Daha akıllı (pahalı) model kullansın mı", required=False)})
async def create_agent(ctx: ToolContext, name: str, role: str, instructions: str, groups: list, smart: bool = False):
    valid = [g for g in groups if g in all_groups() and g != "agents"]
    ctx.app.agents.save(name.strip().lower().replace(" ", "_"), role, instructions, valid, "smart" if smart else "fast")
    return {"created": name, "groups": valid}


@tool("delete_agent", "Kullanıcının oluşturduğu bir ajanı siler.", "agents", {"name": P(str, "Ajan adı")})
async def delete_agent(ctx: ToolContext, name: str):
    return {"deleted": ctx.app.agents.delete(name)}


@tool("delegate_to_agent", "Bir işi uzman ajana devreder ve sonucunu alır. Uzun araştırma, tarayıcı/bilgisayar işleri, "
      "telefon ekranı kontrolü gibi işler için kullan.", "agents",
      {"agent": P(str, "Ajan adı"), "task": P(str, "Ajana verilecek ayrıntılı görev")})
async def delegate_to_agent(ctx: ToolContext, agent: str, task: str):
    if ctx.depth >= 2:
        return {"error": "Çok fazla iç içe devir"}
    if agent not in ctx.app.agents.all():
        return {"error": f"Böyle bir ajan yok: {agent}"}
    text = await ctx.app.agent.run_task(ctx.chat_id, task, agent=agent, depth=ctx.depth + 1)
    return {"agent": agent, "result": text}


# ---------------- ayarlar ----------------
@tool("set_voice_replies", "Sesli cevap modunu açar/kapatır (cevaplar ses kaydı olarak da gelir).", "core",
      {"enabled": P(bool, "Açık mı")})
async def set_voice_replies(ctx: ToolContext, enabled: bool):
    ctx.app.db.set("voice_replies", bool(enabled))
    return {"voice_replies": bool(enabled)}
