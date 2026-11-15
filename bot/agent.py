"""Ajan çekirdeği: Gemini ile araç çağırma döngüsü, onay sistemi, ajanlar arası devir."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from .agents import AgentDef
from .budget import BudgetExceeded
from .llm import model_content, tool_results_content, user_content
from .tools import REGISTRY, ToolContext, tools_for_groups

log = logging.getLogger(__name__)
MAX_RESULT_CHARS = 12000
DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _clip(result: Any) -> Any:
    """Araç sonucunu JSON'a uygun ve sınırlı boyutta hale getirir."""
    s = json.dumps(result, ensure_ascii=False, default=str)
    if len(s) <= MAX_RESULT_CHARS:
        return json.loads(s)
    return {"truncated": True, "data": s[:MAX_RESULT_CHARS]}


class Agent:
    def __init__(self, app):
        self.app = app

    # ------------------------------------------------------------------ prompt
    def system_prompt(self, a: AgentDef) -> str:
        app = self.app
        now = datetime.now(app.cfg.tz)
        mem = "\n".join(f"- (#{m['id']}) {m['fact']}" for m in app.db.memories()) or "- (henüz yok)"
        skills = app.db.all("SELECT name, trigger FROM skills")
        skills_txt = "\n".join(f"- {s['name']}: {s['trigger']}" for s in skills) or "- (henüz yok)"
        agents_txt = "\n".join(f"- {d.name}: {d.role}" for d in app.agents.all().values() if d.name != a.name)
        status = [f"Telefon: {'bağlı (' + app.phone.device + ')' if app.phone.online else 'bağlı değil'}",
                  f"Google hesabı: {'bağlı' if app.google.connected() else 'bağlı değil (/google ile bağlanır)'}"]
        return f"""Sen {app.cfg.bot_name}'sın: kullanıcının 7/24 çalışan kişisel yapay zekâ ajanısın.
Şu anki ajan rolün: {a.name} — {a.role}.
{a.instructions}

KURALLAR
- Her zaman Türkçe, samimi ve kısa cevap ver. Cevaplar Telegram'da okunacak: sade metin ve emoji kullan, tablo kullanma.
- Bir işi yapabileceğin bir araç varsa, sormadan aracı kullan. Bilgi uydurma; emin değilsen ara veya sor.
- Bazı araçlar (e-posta/SMS gönderme, arama yapma, silme, terminal, fotoğraf, ekran kontrolü) kullanıcı onayı ister.
  Böyle bir araç 'onay_bekleniyor' dönerse kullanıcıya onay butonuna basmasını söyle; tekrar çağırma.
- Para gönderme, satın alma, şifre girme işlemlerini ASLA kendi başına tamamlama.
- Kullanıcı "her sabah/her gün/her pazartesi..." gibi tekrar eden bir iş isterse create_schedule kullan.
  Sadece hatırlatma isterse set_reminder kullan (ücretsizdir).
- Kullanıcı kendisiyle ilgili kalıcı bir bilgi verirse (isim, tercih, aile, iş, adres) remember ile kaydet.
- Bir beceri kullanıcının isteğine uyuyorsa use_skill ile adımlarını al ve uygula.
- Zamanlanmış görev olarak çalışıyorsan sonucu doğrudan kullanıcıya yazılacak bir mesaj olarak hazırla.

KULLANICI HAKKINDA BİLDİKLERİN
{mem}

BECERİLER
{skills_txt}

DİĞER UZMAN AJANLAR (delegate_to_agent ile)
{agents_txt}

ŞU AN
{now:%Y-%m-%d %H:%M} ({DAYS_TR[now.weekday()]}), saat dilimi {app.cfg.timezone}
Durum: {' | '.join(status)}
"""

    # ------------------------------------------------------------------ giriş noktaları
    async def handle_user(self, chat_id: int, parts: list, history_text: str) -> str:
        """Kullanıcı mesajını işler. parts: metin ve/veya (bytes, mime)."""
        app = self.app
        a = app.agents.get(app.db.get(f"active_agent:{chat_id}", "asistan"))
        contents = []
        for m in app.db.recent_messages(chat_id, app.cfg.history_limit):
            contents.append(user_content([m["text"]]) if m["role"] == "user" else model_content(m["text"]))
        contents.append(user_content(parts))
        app.db.add_message(chat_id, "user", history_text)
        text = await self._loop(ToolContext(app, chat_id, a.name), contents, a)
        app.db.add_message(chat_id, "model", text)
        return text

    async def run_task(self, chat_id: int, task: str, agent: str = "asistan", depth: int = 0,
                       save_history: bool = False) -> str:
        """Geçmişsiz tek görev (zamanlanmış görev veya ajan devri)."""
        a = self.app.agents.get(agent)
        text = await self._loop(ToolContext(self.app, chat_id, a.name, depth=depth), [user_content([task])], a)
        if save_history:
            self.app.db.add_message(chat_id, "user", task)
            self.app.db.add_message(chat_id, "model", text)
        return text

    # ------------------------------------------------------------------ döngü
    async def _loop(self, ctx: ToolContext, contents: list, a: AgentDef) -> str:
        tools = [t.declaration() for t in tools_for_groups(a.groups)]
        system = self.system_prompt(a)
        try:
            for _ in range(self.app.cfg.max_tool_steps):
                res = await self.app.llm.generate(a.tier, contents, system, tools)
                if not res.calls:
                    return res.text or "👍"
                contents.append(res.content)
                results = []
                for call in res.calls:
                    log.info("Araç: %s %s", call.name, call.args)
                    results.append((call.name, _clip(await self.execute_tool(ctx, call.name, call.args))))
                contents.append(tool_results_content(results))
            return "⚠️ Bu iş çok fazla adım sürdü, durdum. Daha küçük parçalara bölebilir misin?"
        except BudgetExceeded as e:
            return f"💸 {e}"

    async def execute_tool(self, ctx: ToolContext, name: str, args: dict) -> Any:
        tool = REGISTRY.get(name)
        if not tool:
            return {"error": f"Bilinmeyen araç: {name}"}
        if not ctx.approved and tool.needs_approval(args):
            return await self._request_approval(ctx, tool, args)
        try:
            result = await tool.func(ctx, **args)
            self.app.db.audit(name, args, result, True)
            return result
        except TypeError as e:
            return {"error": f"Geçersiz parametre: {e}"}
        except Exception as e:  # aracın hatası modele bildirilir
            log.exception("Araç hatası: %s", name)
            self.app.db.audit(name, args, str(e), False)
            return {"error": f"{type(e).__name__}: {e}"}

    # ------------------------------------------------------------------ onay sistemi
    async def _request_approval(self, ctx: ToolContext, tool, args: dict) -> dict:
        db = self.app.db
        args_json = json.dumps(args, ensure_ascii=False, sort_keys=True)
        existing = db.one("SELECT id FROM approvals WHERE status='pending' AND tool=? AND args=?", (tool.name, args_json))
        if existing:
            return {"status": "onay_bekleniyor", "approval_id": existing["id"]}
        summary = tool.describe(args)
        aid = db.execute("INSERT INTO approvals(chat_id,tool,args,summary,agent,created) VALUES(?,?,?,?,?,?)",
                         (ctx.chat_id, tool.name, args_json, summary, ctx.agent, time.time())).lastrowid
        await self.app.notifier.ask_approval(aid, summary)
        return {"status": "onay_bekleniyor", "approval_id": aid,
                "note": "Kullanıcıya onay butonu gönderildi. Onaylanınca işlem otomatik yapılacak."}

    async def resolve_approval(self, approval_id: int, approve: bool) -> str:
        db = self.app.db
        row = db.one("SELECT * FROM approvals WHERE id=?", (approval_id,))
        if not row:
            return "Bu onay bulunamadı."
        if row["status"] != "pending":
            return f"Bu işlem zaten {'onaylandı' if row['status'] == 'approved' else 'iptal edildi'}."
        if not approve:
            db.execute("UPDATE approvals SET status='denied', decided=? WHERE id=?", (time.time(), approval_id))
            db.add_message(row["chat_id"], "model", f"[Sistem] #{approval_id} işlemi kullanıcı tarafından iptal edildi: {row['summary']}")
            return "❌ İptal edildi."
        db.execute("UPDATE approvals SET status='approved', decided=? WHERE id=?", (time.time(), approval_id))
        ctx = ToolContext(self.app, row["chat_id"], row["agent"] or "asistan", approved=True)
        result = await self.execute_tool(ctx, row["tool"], json.loads(row["args"]))
        db.execute("UPDATE approvals SET result=? WHERE id=?",
                   (json.dumps(result, ensure_ascii=False, default=str)[:4000], approval_id))
        follow = (f"[Sistem] Kullanıcı #{approval_id} numaralı işlemi ONAYLADI ve işlem yapıldı.\n"
                  f"İşlem: {row['summary']}\nSonuç: {json.dumps(_clip(result), ensure_ascii=False)[:4000]}\n"
                  "Kullanıcıya sonucu kısaca bildir. Görevin devamı varsa devam et.")
        return await self.handle_user(row["chat_id"], [follow], follow)
