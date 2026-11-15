"""Android uygulaması (YAi APK) için JSON API. Yetki: 'Authorization: Bearer <DASHBOARD_TOKEN>'."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from . import schedules as S
from .timeparse import WhenError, describe, parse_when

SETTINGS = {
    "phone_enabled": True, "phone_forward_notifications": True, "proactive_email": True,
    "proactive_calendar": True, "voice_replies": False, "learning_mode": True,
}


def create_router(app, authed) -> APIRouter:
    r = APIRouter(prefix="/api")
    tz = app.cfg.tz

    def deny():
        return JSONResponse({"error": "yetkisiz"}, 401)

    async def body(request: Request) -> dict:
        try:
            return await request.json()
        except Exception:
            return {}

    @r.get("/status")
    async def status(request: Request):
        if not authed(request):
            return deny()
        pending = app.db.one("SELECT COUNT(*) n FROM approvals WHERE status='pending'")["n"]
        return {"bot_name": app.cfg.bot_name, "phone": app.phone.status(), "google": app.google.connected(),
                "spent_today": app.budget.spent_today(), "spent_month": app.budget.spent_month(),
                "monthly_limit": app.cfg.monthly_limit_usd, "daily_limit": app.cfg.daily_limit_usd,
                "pending_approvals": pending, "schedules": len(S.list_schedules(app.db)),
                "memories": len(app.db.memories()), "server_time": time.time()}

    # ---------------- sohbet ----------------
    @r.post("/chat")
    async def chat(request: Request):
        if not authed(request):
            return deny()
        text = str((await body(request)).get("text", "")).strip()
        if not text:
            return JSONResponse({"error": "boş mesaj"}, 400)
        reply = await app.agent.handle_user(app.cfg.owner_id, [text], text)
        return {"reply": reply}

    @r.get("/history")
    async def history(request: Request, limit: int = 50):
        if not authed(request):
            return deny()
        return app.db.recent_messages(app.cfg.owner_id, min(limit, 200))

    # ---------------- onaylar ----------------
    @r.get("/approvals")
    async def approvals(request: Request):
        if not authed(request):
            return deny()
        return app.db.all("SELECT id,tool,summary,created FROM approvals WHERE status='pending' ORDER BY id DESC")

    @r.post("/approvals/{aid}")
    async def decide(aid: int, request: Request):
        if not authed(request):
            return deny()
        approve = bool((await body(request)).get("approve"))
        reply = await app.agent.resolve_approval(aid, approve)
        await app.notifier.send_text(reply)
        return {"reply": reply}

    # ---------------- zamanlayıcılar ----------------
    @r.get("/schedules")
    async def schedules(request: Request):
        if not authed(request):
            return deny()
        return [{"id": s["id"], "kind": s["kind"], "payload": s["payload"], "agent": s["agent"],
                 "when": describe(s, tz), "next_run": s["next_run"]} for s in S.list_schedules(app.db)]

    @r.post("/schedules")
    async def add_schedule(request: Request):
        if not authed(request):
            return deny()
        b = await body(request)
        try:
            w = parse_when(str(b.get("when", "")), tz)
        except WhenError as e:
            return JSONResponse({"error": str(e)}, 400)
        kind = "message" if b.get("kind") == "message" else "prompt"
        task = str(b.get("task", "")).strip()
        if not task:
            return JSONResponse({"error": "görev metni boş"}, 400)
        sid = S.add_schedule(app.db, tz, kind, task, w.get("cron"), w.get("run_at"), b.get("agent") or "asistan")
        return {"id": sid, "when": describe(w, tz)}

    @r.delete("/schedules/{sid}")
    async def del_schedule(sid: int, request: Request):
        if not authed(request):
            return deny()
        return {"deleted": S.delete_schedule(app.db, sid)}

    # ---------------- hafıza, ajanlar, beceriler, sayfalar ----------------
    @r.get("/memories")
    async def memories(request: Request):
        return app.db.memories() if authed(request) else deny()

    @r.post("/memories")
    async def add_memory(request: Request):
        if not authed(request):
            return deny()
        fact = str((await body(request)).get("fact", "")).strip()
        return {"id": app.db.add_memory(fact)} if fact else JSONResponse({"error": "boş"}, 400)

    @r.delete("/memories/{mid}")
    async def del_memory(mid: int, request: Request):
        return {"deleted": app.db.delete_memory(mid)} if authed(request) else deny()

    @r.get("/agents")
    async def agents(request: Request):
        if not authed(request):
            return deny()
        active = app.db.get(f"active_agent:{app.cfg.owner_id}", "asistan")
        return [{"name": a.name, "role": a.role, "tier": a.tier, "builtin": a.builtin, "active": a.name == active}
                for a in app.agents.all().values()]

    @r.post("/agents/active")
    async def set_agent(request: Request):
        if not authed(request):
            return deny()
        name = str((await body(request)).get("name", "asistan"))
        if name not in app.agents.all():
            return JSONResponse({"error": "ajan yok"}, 404)
        app.db.set(f"active_agent:{app.cfg.owner_id}", name)
        return {"active": name}

    @r.get("/skills")
    async def skills(request: Request):
        return app.db.all("SELECT id,name,trigger,steps,uses FROM skills") if authed(request) else deny()

    @r.delete("/skills/{name}")
    async def del_skill(name: str, request: Request):
        if not authed(request):
            return deny()
        return {"deleted": app.db.execute("DELETE FROM skills WHERE name=?", (name,)).rowcount > 0}

    @r.get("/pages")
    async def pages(request: Request):
        return app.db.all("SELECT id,title,updated FROM pages ORDER BY updated DESC LIMIT 100") if authed(request) else deny()

    @r.get("/pages/{pid}")
    async def page(pid: int, request: Request):
        if not authed(request):
            return deny()
        return app.db.one("SELECT * FROM pages WHERE id=?", (pid,)) or JSONResponse({"error": "yok"}, 404)

    # ---------------- ayarlar ve maliyet ----------------
    @r.get("/settings")
    async def settings(request: Request):
        if not authed(request):
            return deny()
        return {k: app.db.get(k, d) for k, d in SETTINGS.items()}

    @r.post("/settings")
    async def set_settings(request: Request):
        if not authed(request):
            return deny()
        for k, v in (await body(request)).items():
            if k in SETTINGS:
                app.db.set(k, bool(v))
        return {k: app.db.get(k, d) for k, d in SETTINGS.items()}

    @r.get("/costs")
    async def costs(request: Request):
        if not authed(request):
            return deny()
        days = app.db.all("SELECT day, SUM(cost) cost FROM usage GROUP BY day ORDER BY day DESC LIMIT 30")
        models = app.db.all("SELECT model, SUM(cost) cost FROM usage WHERE month=? GROUP BY model",
                            (time.strftime("%Y-%m"),))
        return {"today": app.budget.spent_today(), "month": app.budget.spent_month(),
                "monthly_limit": app.cfg.monthly_limit_usd, "days": days, "models": models}

    @r.get("/audit")
    async def audit(request: Request):
        return app.db.all("SELECT * FROM audit ORDER BY id DESC LIMIT 50") if authed(request) else deny()

    return r
