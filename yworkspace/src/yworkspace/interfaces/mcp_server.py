"""MCP server (stdio and Streamable HTTP), dependency-free.

Lets MCP clients (Claude Desktop, Cursor, VS Code, Gemini CLI, ChatGPT ...) use yWorkspace's tools,
done gates and skills. The client is the agent; yWorkspace provides the environment.
"""

from __future__ import annotations

import json
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .. import __version__
from ..tools.registry import EXTERNAL, ToolRegistry

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

GUIDE = """yWorkspace gives you a real project folder and an isolated Linux sandbox.
Work like a senior engineer who finishes the job: plan with plan_add_tasks, implement one task at a time,
run tests with `run`, mark tasks done with evidence via plan_update, and call check_done before you say you are
finished. check_done runs the project's tests and scans for unfinished code; only stop when it passes."""


class McpServer:
    def __init__(self, registry: ToolRegistry, prompts: dict[str, tuple[str, str]] | None = None,
                 allow_external: bool = False, name: str = "yworkspace"):
        self.registry = registry if allow_external else registry.subset(
            names=[t.name for t in registry.all() if t.risk != EXTERNAL])
        self.prompts = prompts or {}
        self.name = name
        self._lock = threading.Lock()

    # ------------------------------------------------------------ JSON-RPC
    def handle(self, msg: dict) -> dict | None:
        method = msg.get("method")
        mid = msg.get("id")
        params = msg.get("params") or {}
        if mid is None:  # notification
            return None
        try:
            result = self._dispatch(method, params)
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Invalid params: {e}"}}
        except LookupError as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": str(e)}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _dispatch(self, method: str, params: dict) -> Any:
        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            caps: dict[str, Any] = {"tools": {"listChanged": False}}
            if self.prompts:
                caps["prompts"] = {"listChanged": False}
            return {"protocolVersion": version, "capabilities": caps,
                    "serverInfo": {"name": self.name, "title": "yWorkspace", "version": __version__},
                    "instructions": GUIDE}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": self.registry.to_mcp()}
        if method == "tools/call":
            name = params["name"]
            with self._lock:  # tools share one workspace state
                res = self.registry.call(name, params.get("arguments") or {})
            content: list[dict] = [{"type": "text", "text": res.text}]
            content += [{"type": "image", "data": b, "mimeType": "image/png"} for b in res.images]
            return {"content": content, "isError": res.is_error}
        if method == "prompts/list":
            return {"prompts": [{"name": k, "description": v[0]} for k, v in self.prompts.items()]}
        if method == "prompts/get":
            desc, text = self.prompts[params["name"]]
            return {"description": desc, "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
        if method in ("resources/list", "resources/templates/list"):
            return {"resources": []} if method == "resources/list" else {"resourceTemplates": []}
        raise LookupError(f"Method not found: {method}")

    # ------------------------------------------------------------ stdio
    def serve_stdio(self, inp=None, out=None) -> None:
        inp = inp or sys.stdin
        out = out or sys.stdout
        for line in inp:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
                out.write(json.dumps(resp) + "\n")
                out.flush()
                continue
            batch = msg if isinstance(msg, list) else [msg]
            replies = [r for r in (self.handle(m) for m in batch) if r is not None]
            for r in replies:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()

    # ------------------------------------------------------------ HTTP
    def make_http_server(self, host: str = "127.0.0.1", port: int = 8765, token: str | None = None,
                         path: str = "/mcp") -> tuple[ThreadingHTTPServer, str]:
        token = token if token is not None else secrets.token_urlsafe(24)
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _auth(self) -> bool:
                if not token:
                    return True
                return self.headers.get("Authorization", "") == f"Bearer {token}"

            def _send(self, code: int, body: Any = None, extra: dict | None = None) -> None:
                data = b"" if body is None else json.dumps(body, ensure_ascii=False).encode()
                self.send_response(code)
                if body is not None:
                    self.send_header("Content-Type", "application/json")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                if self.path.split("?")[0] != path:
                    return self._send(404, {"error": "not found"})
                if not self._auth():
                    return self._send(401, {"error": "unauthorized"}, {"WWW-Authenticate": "Bearer"})
                origin = self.headers.get("Origin")
                if origin and not origin.startswith(("http://127.0.0.1", "http://localhost", "https://")):
                    return self._send(403, {"error": "origin not allowed"})
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    msg = json.loads(self.rfile.read(n) or b"null")
                except json.JSONDecodeError:
                    return self._send(400, {"jsonrpc": "2.0", "id": None,
                                            "error": {"code": -32700, "message": "Parse error"}})
                batch = msg if isinstance(msg, list) else [msg]
                replies = [r for r in (server.handle(m) for m in batch) if r is not None]
                if not replies:
                    return self._send(202)
                headers = {}
                if any(m.get("method") == "initialize" for m in batch if isinstance(m, dict)):
                    headers["Mcp-Session-Id"] = secrets.token_hex(16)
                return self._send(200, replies if isinstance(msg, list) else replies[0], headers)

            def do_GET(self):
                self._send(405, {"error": "this server does not open SSE streams"}, {"Allow": "POST"})

            def do_DELETE(self):
                self._send(200, {})

        httpd = ThreadingHTTPServer((host, port), Handler)
        return httpd, token


def default_prompts(lang: str = "tr") -> dict[str, tuple[str, str]]:
    from ..engine.roles import ROLES, system_prompt
    out = {"deep-work": ("Work until the job is truly done (yWorkspace method)", GUIDE)}
    for key in ("analyst", "architect", "developer", "reviewer", "debugger", "tester"):
        role = ROLES[key]
        out[f"role-{key}"] = (f"yWorkspace role: {role.title_tr}", system_prompt(role, lang))
    from ..skills import load_all
    for s in load_all():
        out[f"skill-{s.name}"] = (s.title_tr if lang == "tr" else s.title_en, s.text(lang))
    return out
