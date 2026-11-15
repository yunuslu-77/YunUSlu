"""Web panel + telefon WebSocket uç noktası (FastAPI)."""
from __future__ import annotations

import hmac
from datetime import datetime
from html import escape

from fastapi import FastAPI, Form, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import schedules as S

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2129;--muted:#667085;--accent:#4f46e5;--ok:#16a34a;--bad:#dc2626;--line:#e5e7eb}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b22;--text:#e6e8ec;--muted:#9aa3b2;--line:#2a2f3a;--accent:#818cf8}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--text)}
header{padding:16px;display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
h1{font-size:20px;margin:0}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;padding:0 16px 32px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;overflow:hidden}
h2{font-size:15px;margin:0 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.row{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;padding:8px 0;border-top:1px solid var(--line)}
.row:first-of-type{border-top:0}.muted{color:var(--muted);font-size:13px}pre{white-space:pre-wrap;margin:4px 0;font:13px/1.4 ui-monospace,monospace}
button{border:0;border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit;background:var(--line);color:var(--text)}
.ok{background:var(--ok);color:#fff}.bad{background:var(--bad);color:#fff}.pill{padding:2px 8px;border-radius:99px;font-size:12px}
.on{background:#16a34a22;color:var(--ok)}.off{background:#dc262622;color:var(--bad)}form{display:inline;margin:0}
.big{font-size:26px;font-weight:700}a{color:var(--accent)}
"""


def create_app(app) -> FastAPI:
    api = FastAPI(title="YAi Panel", docs_url=None, redoc_url=None)
    tz = app.cfg.tz

    def authed(request: Request) -> bool:
        tok = app.cfg.dashboard_token
        if not tok:
            return False
        given = request.query_params.get("token") or request.cookies.get("yai_token") or ""
        return hmac.compare_digest(given, tok)

    def fmt(ts) -> str:
        return datetime.fromtimestamp(ts, tz).strftime("%d.%m %H:%M") if ts else "-"

    @api.websocket("/phone/ws")
    async def phone_ws(ws: WebSocket):
        await ws.accept()
        await app.phone.handle(ws)

    @api.get("/api/status")
    async def status(request: Request):
        if not authed(request):
            return JSONResponse({"error": "yetkisiz"}, 401)
        return {"phone": app.phone.status(), "google": app.google.connected(),
                "spent_today": app.budget.spent_today(), "spent_month": app.budget.spent_month()}

    @api.get("/health")
    async def health():
        return {"ok": True}

    def guard(request: Request):
        if not authed(request):
            return HTMLResponse("<h3>Yetkisiz. Adrese ?token=DASHBOARD_TOKEN ekle.</h3>", 401)
        return None

    @api.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        if (r := guard(request)):
            return r
        db = app.db
        pending = db.all("SELECT * FROM approvals WHERE status='pending' ORDER BY id DESC")
        scheds = S.list_schedules(db)
        mems = db.memories()
        pages = db.all("SELECT id,title,updated FROM pages ORDER BY updated DESC LIMIT 20")
        skills = db.all("SELECT name,trigger,uses FROM skills")
        audit = db.all("SELECT * FROM audit ORDER BY id DESC LIMIT 25")
        days = db.all("SELECT day, SUM(cost) c FROM usage GROUP BY day ORDER BY day DESC LIMIT 14")
        ph = app.phone.status()

        def toggle(key, label, default):
            v = db.get(key, default)
            return (f'<div class="row"><span>{label}</span><form method="post" action="/toggle/{key}">'
                    f'<button class="pill {"on" if v else "off"}">{"açık" if v else "kapalı"}</button></form></div>')

        h = [f"<!doctype html><html lang=tr><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
             f"<title>{escape(app.cfg.bot_name)} Panel</title><style>{CSS}</style></head><body>",
             f"<header><h1>🤖 {escape(app.cfg.bot_name)} Panel</h1><span class=muted>{datetime.now(tz):%d.%m.%Y %H:%M}</span></header><main>"]
        h.append(f"<section><h2>Maliyet</h2><div class=big>{app.budget.spent_month():.3f} $</div>"
                 f"<div class=muted>bu ay / limit {app.cfg.monthly_limit_usd:.2f} $ · bugün {app.budget.spent_today():.4f} $</div>"
                 + "".join(f'<div class="row"><span>{d["day"]}</span><span>{d["c"]:.4f} $</span></div>' for d in days) + "</section>")
        h.append("<section><h2>Durum ve Ayarlar</h2>"
                 f'<div class="row"><span>📱 Telefon</span><span class="pill {"on" if ph["online"] else "off"}">'
                 f'{escape(ph["device"]) + " bağlı" if ph["online"] else "bağlı değil"}</span></div>'
                 f'<div class="row"><span>🔗 Google</span><span class="pill {"on" if app.google.connected() else "off"}">'
                 f'{"bağlı" if app.google.connected() else "bağlı değil"}</span></div>'
                 + toggle("phone_enabled", "Telefon erişimi", True)
                 + toggle("phone_forward_notifications", "Telefon bildirimlerini ilet", True)
                 + toggle("proactive_email", "Önemli e-posta uyarısı", True)
                 + toggle("proactive_calendar", "Toplantı hatırlatma", True)
                 + toggle("voice_replies", "Sesli cevap", False) + "</section>")
        h.append("<section><h2>Bekleyen Onaylar</h2>" + ("".join(
            f'<div class="row"><pre>#{p["id"]} {escape(p["summary"])}</pre><span>'
            f'<form method=post action="/approve/{p["id"]}/1"><button class=ok>Onayla</button></form> '
            f'<form method=post action="/approve/{p["id"]}/0"><button class=bad>İptal</button></form></span></div>'
            for p in pending) or "<div class=muted>Yok</div>") + "</section>")
        h.append("<section><h2>Zamanlayıcılar</h2>" + ("".join(
            f'<div class="row"><pre>{escape(S.format_schedule(s, tz))}</pre><form method=post action="/schedule/delete/{s["id"]}">'
            f'<button>Sil</button></form></div>' for s in scheds) or "<div class=muted>Yok</div>") +
            '<form method=post action="/schedule/add" style="display:block;margin-top:10px">'
            '<input name=when placeholder="08:00 / hafta içi 09:00 / +30dk" style="width:100%;padding:6px;margin:4px 0">'
            '<input name=task placeholder="Görev / hatırlatma metni" style="width:100%;padding:6px;margin:4px 0">'
            '<select name=kind style="padding:6px"><option value=prompt>Ajan görevi</option><option value=message>Hatırlatma</option></select> '
            '<button class=ok>Ekle</button></form></section>')
        h.append("<section><h2>Hafıza</h2>" + ("".join(
            f'<div class="row"><span>{escape(m["fact"])}</span><form method=post action="/memory/delete/{m["id"]}">'
            f'<button>Sil</button></form></div>' for m in mems) or "<div class=muted>Boş</div>") + "</section>")
        h.append("<section><h2>Sayfalar</h2>" + ("".join(
            f'<div class="row"><a href="/page/{p["id"]}">{escape(p["title"])}</a><span class=muted>{fmt(p["updated"])}</span></div>'
            for p in pages) or "<div class=muted>Yok</div>") + "</section>")
        h.append("<section><h2>Ajanlar ve Beceriler</h2>" + "".join(
            f'<div class="row"><span>🤝 {escape(n)}</span><span class=muted>{escape(a.role)}</span></div>'
            for n, a in app.agents.all().items()) + "".join(
            f'<div class="row"><span>🧠 {escape(s["name"])}</span><span class=muted>{s["uses"]} kez</span></div>'
            for s in skills) + "</section>")
        h.append("<section><h2>Son İşlemler</h2>" + ("".join(
            f'<div class="row"><span>{"✅" if a["ok"] else "⚠️"} {escape(a["tool"])}<br><span class=muted>'
            f'{escape(a["args"][:120])}</span></span><span class=muted>{fmt(a["ts"])}</span></div>'
            for a in audit) or "<div class=muted>Yok</div>") + "</section>")
        h.append("</main></body></html>")
        resp = HTMLResponse("".join(h))
        if request.query_params.get("token"):
            resp.set_cookie("yai_token", app.cfg.dashboard_token, httponly=True, samesite="strict", max_age=90 * 86400)
        return resp

    @api.get("/page/{pid}", response_class=HTMLResponse)
    async def page(pid: int, request: Request):
        if (r := guard(request)):
            return r
        p = app.db.one("SELECT * FROM pages WHERE id=?", (pid,))
        if not p:
            return HTMLResponse("Bulunamadı", 404)
        return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                            f"<style>{CSS}</style><main style='display:block;padding:16px'><p><a href='/'>← Panel</a></p>"
                            f"<section><h1>{escape(p['title'])}</h1><pre>{escape(p['content'])}</pre></section></main>")

    def back():
        return RedirectResponse("/", status_code=303)

    @api.post("/approve/{aid}/{ok}")
    async def approve(aid: int, ok: int, request: Request):
        if (r := guard(request)):
            return r
        text = await app.agent.resolve_approval(aid, ok == 1)
        await app.deliver(text)
        return back()

    @api.post("/schedule/delete/{sid}")
    async def sched_delete(sid: int, request: Request):
        if (r := guard(request)):
            return r
        S.delete_schedule(app.db, sid)
        return back()

    @api.post("/schedule/add")
    async def sched_add(request: Request, when: str = Form(...), task: str = Form(...), kind: str = Form("prompt")):
        if (r := guard(request)):
            return r
        from .timeparse import WhenError, parse_when
        try:
            w = parse_when(when, tz)
        except WhenError as e:
            return HTMLResponse(f"Hata: {escape(str(e))} <a href='/'>geri</a>", 400)
        S.add_schedule(app.db, tz, "message" if kind == "message" else "prompt", task, w.get("cron"), w.get("run_at"))
        return back()

    @api.post("/memory/delete/{mid}")
    async def mem_delete(mid: int, request: Request):
        if (r := guard(request)):
            return r
        app.db.delete_memory(mid)
        return back()

    @api.post("/toggle/{key}")
    async def toggle(key: str, request: Request):
        if (r := guard(request)):
            return r
        defaults = {"phone_enabled": True, "phone_forward_notifications": True, "proactive_email": True,
                    "proactive_calendar": True, "voice_replies": False}
        if key in defaults:
            app.db.set(key, not app.db.get(key, defaults[key]))
        return back()

    return api
