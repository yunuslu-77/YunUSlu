"""Local web interface: FastAPI backend + a no-build HTML/JS frontend.

Listens on 127.0.0.1 by default. Every API call needs the session token (shown when the server starts and
stored in a cookie after the first visit), so other websites cannot drive yWorkspace.
"""

from __future__ import annotations

import json
import queue
import secrets
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ... import __version__
from ...config import Config, get_secret, set_secret
from ...engine.engine import Approver
from ...engine.loop import LoopEvent
from ...engine.state import ProjectState

STATIC = Path(__file__).parent / "static"


class Hub:
    """Fan-out of events to every open browser tab."""

    def __init__(self) -> None:
        self.subs: list[queue.Queue] = []
        self.backlog: list[dict] = []
        self.lock = threading.Lock()

    def publish(self, event: dict) -> None:
        event.setdefault("time", time.time())
        with self.lock:
            self.backlog = (self.backlog + [event])[-500:]
            for q in list(self.subs):
                q.put(event)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self.lock:
            for e in self.backlog[-200:]:
                q.put(e)
            self.subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.subs:
                self.subs.remove(q)


class WebApprover(Approver):
    def __init__(self, hub: Hub, timeout: float = 3600):
        self.hub = hub
        self.timeout = timeout
        self.pending: dict[str, dict] = {}

    def _ask(self, kind: str, text: str) -> dict:
        rid = uuid.uuid4().hex[:10]
        ev = threading.Event()
        self.pending[rid] = {"event": ev, "answer": None}
        self.hub.publish({"kind": "approval", "id": rid, "type": kind, "text": text})
        ev.wait(self.timeout)
        ans = self.pending.pop(rid, {}).get("answer") or {"ok": False, "feedback": "No answer in time."}
        self.hub.publish({"kind": "approval_done", "id": rid})
        return ans

    def approve(self, kind: str, summary: str) -> tuple[bool, str]:
        a = self._ask(kind, summary)
        return bool(a.get("ok")), a.get("feedback", "")

    def question(self, text: str) -> str | None:
        a = self._ask("question", text)
        return a.get("feedback") or None

    def answer(self, rid: str, ok: bool, feedback: str = "") -> bool:
        p = self.pending.get(rid)
        if not p:
            return False
        p["answer"] = {"ok": ok, "feedback": feedback}
        p["event"].set()
        return True


class Runner:
    def __init__(self, hub: Hub, approver: WebApprover, session_factory=None):
        self.hub = hub
        self.approver = approver
        self.thread: threading.Thread | None = None
        self.session = None
        self.project: str | None = None
        from ...app import build_session
        self.factory = session_factory or build_session

    def busy(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self, project: Path, goal: str, cfg: Config) -> None:
        if self.busy():
            raise HTTPException(409, "A run is already in progress.")

        def on_event(e: LoopEvent) -> None:
            self.hub.publish({"kind": e.kind, "text": e.text[:4000], "data": _jsonable(e.data),
                              "project": project.name})

        def work() -> None:
            try:
                self.session = self.factory(project, cfg, self.approver, on_event)
                self.hub.publish({"kind": "run_started", "project": project.name, "text": goal})
                report = self.session.engine.run(goal)
                self.hub.publish({"kind": "run_finished", "project": project.name, "text": report.text(),
                                  "data": {"finished": report.finished, "reason": report.reason}})
            except Exception as ex:  # surface every failure to the UI
                self.hub.publish({"kind": "error", "project": project.name, "text": f"{type(ex).__name__}: {ex}"})
            finally:
                if self.session:
                    self.session.close()

        self.project = project.name
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.session and self.session.engine:
            self.session.engine.stop()


def _jsonable(d: dict) -> dict:
    try:
        json.dumps(d)
        return d
    except TypeError:
        return {k: str(v) for k, v in d.items()}


def create_app(cfg: Config | None = None, token: str | None = None, session_factory=None) -> FastAPI:
    cfg = cfg or Config.load()
    token = token or secrets.token_urlsafe(18)
    hub = Hub()
    approver = WebApprover(hub)
    runner = Runner(hub, approver, session_factory)
    app = FastAPI(title="yWorkspace", version=__version__, docs_url=None, redoc_url=None)
    app.state.token, app.state.hub, app.state.runner, app.state.cfg = token, hub, runner, cfg

    def auth(request: Request) -> None:
        given = request.headers.get("X-YW-Token") or request.cookies.get("yw_token") or request.query_params.get("t")
        if not given or not secrets.compare_digest(given, token):
            raise HTTPException(401, "Missing or wrong session token.")

    def projects_dir() -> Path:
        p = Path(cfg.projects_dir).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def project_path(name: str) -> Path:
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise HTTPException(400, "Bad project name.")
        p = projects_dir() / name
        if not p.is_dir():
            raise HTTPException(404, "No such project.")
        return p

    @app.get("/", response_class=HTMLResponse)
    def index(t: str | None = None):
        resp = FileResponse(STATIC / "index.html")
        if t and secrets.compare_digest(t, token):
            resp.set_cookie("yw_token", t, httponly=True, samesite="strict")
        return resp

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/api/status", dependencies=[Depends(auth)])
    def status():
        from ...setup.doctor import run_doctor
        return {"version": __version__, "busy": runner.busy(), "project": runner.project,
                "health": [asdict(h) for h in run_doctor(cfg)], "config": asdict(cfg)}

    @app.put("/api/config", dependencies=[Depends(auth)])
    def put_config(values: dict = Body(...)):
        for k, v in values.items():
            if k in Config.__dataclass_fields__:
                setattr(cfg, k, v)
        cfg.save()
        return asdict(cfg)

    @app.post("/api/keys", dependencies=[Depends(auth)])
    def put_key(name: str = Body(...), value: str = Body(...)):
        if not name.isupper() or not name.endswith(("_KEY", "_TOKEN")):
            raise HTTPException(400, "Key names look like DEEPSEEK_API_KEY.")
        return {"stored_in": set_secret(name, value)}

    @app.get("/api/models", dependencies=[Depends(auth)])
    def models():
        from ...models.profiles import PRESETS
        return [{**asdict(p), "has_key": p.local or bool(p.key_env and get_secret(p.key_env))} for p in PRESETS.values()]

    @app.get("/api/projects", dependencies=[Depends(auth)])
    def projects():
        out = []
        for p in sorted(projects_dir().iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                st = ProjectState.load(p)
                out.append({"name": p.name, "goal": st.goal, "summary": st.summary(), "phase": st.phase})
        return out

    @app.post("/api/projects", dependencies=[Depends(auth)])
    def new_project(name: str = Body(..., embed=True)):
        safe = "".join(c for c in name if c.isalnum() or c in "-_ ").strip().replace(" ", "-")
        if not safe:
            raise HTTPException(400, "Bad project name.")
        p = projects_dir() / safe
        p.mkdir(parents=True, exist_ok=True)
        import subprocess
        if not (p / ".git").exists():
            subprocess.run(["git", "init", "-q"], cwd=p, capture_output=True)
        return {"name": safe}

    @app.get("/api/projects/{name}/state", dependencies=[Depends(auth)])
    def project_state(name: str):
        p = project_path(name)
        st = ProjectState.load(p)
        journeys = p / ".yw" / "journeys.json"
        return {"goal": st.goal, "spec": st.spec, "phase": st.phase, "summary": st.summary(),
                "tasks": [asdict(t) for t in st.tasks], "progress": st.progress(60), "notes": st.notes(),
                "cost_usd": st.cost_usd, "tokens_in": st.tokens_in, "tokens_out": st.tokens_out,
                "journeys": json.loads(journeys.read_text("utf-8")) if journeys.exists() else []}

    @app.get("/api/projects/{name}/files", dependencies=[Depends(auth)])
    def files(name: str, path: str = Query(".")):
        from ...core.errors import ToolError
        from ...core.workspace import Workspace
        ws = Workspace(project_path(name))
        try:
            full = ws.resolve(path)
            if full.is_dir():
                return {"type": "dir", "listing": ws.list(path, depth=1)}
            return {"type": "file", "content": ws.read(path, limit=5000)}
        except ToolError as e:
            raise HTTPException(400, e.message) from e

    @app.get("/api/projects/{name}/history", dependencies=[Depends(auth)])
    def history(name: str, change_id: str | None = None):
        from ...core.workspace import Workspace
        ws = Workspace(project_path(name))
        return {"history": ws.history_text(50), "diff": ws.diff(change_id) if ws.history(1) else ""}

    @app.post("/api/run", dependencies=[Depends(auth)])
    def run(project: str = Body(...), goal: str = Body(...), autonomy: str | None = Body(None),
            quality: str | None = Body(None), model: str | None = Body(None)):
        run_cfg = Config(**asdict(cfg))
        for k, v in (("autonomy", autonomy), ("quality", quality), ("model", model)):
            if v:
                setattr(run_cfg, k, v)
        runner.start(project_path(project), goal, run_cfg)
        return {"started": True}

    @app.post("/api/stop", dependencies=[Depends(auth)])
    def stop():
        runner.stop()
        return {"stopping": True}

    @app.post("/api/approve", dependencies=[Depends(auth)])
    def approve(id: str = Body(...), ok: bool = Body(...), feedback: str = Body("")):
        if not approver.answer(id, ok, feedback):
            raise HTTPException(404, "No such pending approval.")
        return {"ok": True}

    @app.get("/api/events", dependencies=[Depends(auth)])
    def events():
        q = hub.subscribe()

        def stream():
            try:
                yield "retry: 2000\n\n"
                while True:
                    try:
                        e = q.get(timeout=15)
                        yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        yield ": keep-alive\n\n"
            finally:
                hub.unsubscribe(q)
        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/setup", dependencies=[Depends(auth)])
    def setup_status():
        from ...setup.wizard import Wizard
        w = Wizard(cfg)
        return {"system": w.ctx.info.describe(), "steps": w.status()}

    @app.post("/api/setup/{step_id}", dependencies=[Depends(auth)])
    def setup_step(step_id: str, answers: dict = Body(default={}), run: bool = Body(default=False)):
        from ...setup.wizard import STEPS, Wizard
        if step_id not in {s.id for s in STEPS}:
            raise HTTPException(404, "No such step.")
        w = Wizard(cfg)
        w.ctx.answers.update(answers or {})
        actions = w.plan(step_id)
        plan = [{"describe": a.describe, "command": a.command if isinstance(a.command, str) else
                 " ".join(a.command or []), "manual": a.manual, "admin": a.admin} for a in actions]
        if not run:
            return {"plan": plan}
        results = []
        for a in actions:
            if a.admin:
                results.append("ADMIN: run this in a terminal with administrator rights: " + plan[actions.index(a)]["command"])
                continue
            try:
                results.append(w.run_action(a))
            except Exception as e:
                results.append(f"FAILED: {e}")
                break
        return {"plan": plan, "results": results, "ok": next(s for s in STEPS if s.id == step_id).check(w.ctx).ok}

    @app.get("/api/pair", dependencies=[Depends(auth)])
    def pair(request: Request):
        """Data for pairing the Android remote (QR code contents)."""
        host = request.url.hostname
        return {"url": f"{request.url.scheme}://{host}:{request.url.port}", "token": token}

    return app


def serve(cfg: Config, host: str = "127.0.0.1", port: int = 8700, open_browser: bool = True) -> None:
    import uvicorn
    app = create_app(cfg)
    url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/?t={app.state.token}"
    print(f"yWorkspace: {url}")
    if open_browser:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
