"""Local relay server for the browser extension: the extension drives a web chat, yWorkspace runs the tools.

Only listens on 127.0.0.1 and requires a pairing token on every request.
"""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..protocol.session import TextSession
from ..tools.registry import Tool, ToolResult, obj


def gate_nudge(engine, max_nudges: int = 6):
    """Idle hook: when the AI says it is finished, check the done gates and push it on if they fail."""
    count = {"n": 0}

    def nudge(_session) -> str | None:
        if engine is None or count["n"] >= max_nudges:
            return None
        gates = engine.gates()
        failing = [g for g in gates if not g.passed]
        if not failing:
            return None
        count["n"] += 1
        body = "\n".join(f"- {g.name}: {g.detail[:800]}" for g in failing)
        return ("yWorkspace checked your work and it is NOT finished yet. These done gates fail:\n"
                f"{body}\n\nFix them now with tool blocks. Do not stop until they pass.")
    return nudge


def add_check_done_tool(registry, engine) -> None:
    def check_done() -> ToolResult:
        gates = engine.gates()
        ok = all(g.passed for g in gates)
        lines = [f"[{'x' if g.passed else ' '}] {g.name}" + ("" if g.passed else f": {g.detail[:1500]}")
                 for g in gates]
        verdict = "ALL DONE GATES PASS. You may finish." if ok else "NOT DONE. Fix the failing gates and check again."
        return ToolResult("check_done", verdict + "\n" + "\n".join(lines), not ok)

    registry.register(Tool("check_done", "Run yWorkspace's done gates: tests, open tasks, unfinished-code scan. "
                                         "Call it before you say you are finished.", obj({}), check_done, "safe",
                           "plan"))


class Relay:
    def __init__(self, session_factory, token: str | None = None):
        self.factory = session_factory  # (goal) -> TextSession
        self.token = token or secrets.token_urlsafe(16)
        self.session: TextSession | None = None
        self.lock = threading.Lock()

    def start(self, goal: str) -> dict:
        self.session = self.factory(goal)
        return {"messages": self.session.split(self.session.opening())}

    def reply(self, text: str) -> dict:
        if self.session is None:
            return {"error": "no session; call /start first"}
        res = self.session.handle(text)
        msgs = self.session.split(res.reply_to_ai) if res.reply_to_ai else []
        return {"messages": msgs, "done": res.done, "calls": res.calls, "errors": res.errors, "prose": res.prose}

    def make_server(self, host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
        relay = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _cors(self):
                self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-YW-Token")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

            def _send(self, code: int, body: dict):
                data = json.dumps(body, ensure_ascii=False).encode()
                self.send_response(code)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_OPTIONS(self):
                self.send_response(204)
                self._cors()
                self.end_headers()

            def _authed(self) -> bool:
                return secrets.compare_digest(self.headers.get("X-YW-Token", ""), relay.token)

            def do_GET(self):
                if not self._authed():
                    return self._send(401, {"error": "bad token"})
                if self.path == "/status":
                    s = relay.session
                    return self._send(200, {"ok": True, "active": s is not None, "turns": s.turns if s else 0})
                self._send(404, {"error": "not found"})

            def do_POST(self):
                if not self._authed():
                    return self._send(401, {"error": "bad token"})
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(n) or b"{}")
                except json.JSONDecodeError:
                    return self._send(400, {"error": "bad json"})
                with relay.lock:
                    if self.path == "/start":
                        return self._send(200, relay.start(body.get("goal", "")))
                    if self.path == "/reply":
                        return self._send(200, relay.reply(body.get("text", "")))
                self._send(404, {"error": "not found"})

        return ThreadingHTTPServer((host, port), Handler)


FENCE_NOTE = ("\n\nIMPORTANT for this chat: put ALL your tool blocks inside ONE fenced code block (```), so the chat "
              "window shows them exactly. Write any explanation outside the code block.")


def text_session_for(sess, goal: str, lang: str) -> TextSession:
    from ..engine.roles import ROLES, system_prompt
    role = system_prompt(ROLES["developer"], lang).replace(
        "You work on exactly ONE task (given below).", "Complete the task below, task by task.")
    ts = TextSession(sess.registry, role + FENCE_NOTE, goal, lang, idle_nudge=gate_nudge(sess.engine))
    if sess.engine is not None:
        sess.engine.state.goal = goal
        sess.engine.state.save()
    return ts
