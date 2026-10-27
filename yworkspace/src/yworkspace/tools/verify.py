"""Verification tools: tests/lint/build, git, HTTP requests and a development database."""

from __future__ import annotations

import ipaddress
import json
import sqlite3
import subprocess
import urllib.parse
from pathlib import Path

from ..core.errors import ToolError
from ..core.gitutil import git_env
from ..engine import checks as checks_mod
from ..extensions import register
from .registry import EXTERNAL, SAFE, WRITE, Tool, obj

S = {"type": "string"}


def _git(root: Path, *args: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", env=git_env(root))
    except FileNotFoundError as e:
        raise ToolError("no_git", "git is not installed on this computer.") from e
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        raise ToolError("git_failed", out[:3000] or f"git {args[0]} failed")
    return out or "(no output)"


def _is_local(url: str) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    if host in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback or ipaddress.ip_address(host).is_private
    except ValueError:
        return False


@register
def install(session) -> None:
    reg, root, sb = session.registry, session.workspace.root, session.sandbox
    exclude = root / ".git" / "info" / "exclude"
    if exclude.parent.is_dir():
        text = exclude.read_text("utf-8") if exclude.exists() else ""
        if ".yw/" not in text.split():
            exclude.write_text(text.rstrip("\n") + ("\n" if text else "") + ".yw/\n", "utf-8")

    def check(kind: str = "all") -> str:
        found = checks_mod.detect(root)
        chosen = [c for c in found if kind == "all" or c.kind == kind]
        if not chosen:
            return (f"No {kind} checks found. Detected: {', '.join(c.name for c in found) or 'none'}. "
                    "Add a test setup (e.g. pytest, or a 'test' script in package.json) or .yw/checks.json.")
        out = []
        for r in checks_mod.run_checks(sb, chosen):
            out.append(f"## {r.check.name} ({r.check.command}): {'PASSED' if r.passed else 'FAILED'}\n{r.output[-6000:]}")
        return "\n\n".join(out)

    reg.register(Tool("check", "Run the project's own checks. kind: test, lint, typecheck, build or all.",
                      obj({"kind": {"type": "string", "enum": ["all", "test", "lint", "typecheck", "build"]}}),
                      check, "exec", "verify"))

    def git_status() -> str:
        return _git(root, "status", "--short", "--branch")

    def git_diff(staged: bool = False, path: str | None = None) -> str:
        args = ["diff", "--stat", "--patch"] + (["--staged"] if staged else []) + (["--", path] if path else [])
        out = _git(root, *args)
        if out == "(no output)":
            out = "No changes to tracked files."
        if not staged:
            new = _git(root, "ls-files", "--others", "--exclude-standard")
            if new != "(no output)":
                out += "\n\nNew (untracked) files:\n" + new
        return out if len(out) < 15000 else out[:15000] + "\n…[diff truncated]"

    def git_commit(message: str) -> str:
        _git(root, "add", "-A")
        return _git(root, "-c", "user.name=yWorkspace", "-c", "user.email=yworkspace@localhost",
                    "commit", "-m", message)

    def git_log(limit: int = 15) -> str:
        return _git(root, "log", f"-{int(limit)}", "--oneline", "--decorate")

    def git_branch(name: str | None = None, switch: bool = True) -> str:
        if not name:
            return _git(root, "branch", "--all")
        return _git(root, "switch", "-c", name) if switch else _git(root, "branch", name)

    for t in [
        Tool("git_status", "Show git status.", obj({}), git_status, SAFE, "git"),
        Tool("git_diff", "Show uncommitted changes (or staged ones).", obj({"staged": {"type": "boolean"}, "path": S}),
             git_diff, SAFE, "git"),
        Tool("git_commit", "Commit all changes with a message.", obj({"message": S}, ["message"]), git_commit, WRITE,
             "git"),
        Tool("git_log", "Show recent commits.", obj({"limit": {"type": "integer"}}), git_log, SAFE, "git"),
        Tool("git_branch", "List branches, or create and switch to a new branch.", obj({"name": S, "switch":
             {"type": "boolean"}}), git_branch, WRITE, "git"),
    ]:
        reg.register(t)

    def http(url: str, method: str = "GET", body: str | None = None, headers: dict | None = None,
             timeout: int = 30) -> str:
        import httpx
        try:
            r = httpx.request(method.upper(), url, content=body.encode() if body else None, headers=headers or {},
                              timeout=timeout, follow_redirects=True)
        except httpx.HTTPError as e:
            raise ToolError("http_failed", f"{type(e).__name__}: {e}",
                            "Is the server running? Check with processes and logs.") from e
        text = r.text
        try:
            text = json.dumps(r.json(), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pass
        head = "\n".join(f"{k}: {v}" for k, v in list(r.headers.items())[:12])
        return f"HTTP {r.status_code}\n{head}\n\n{text[:12000]}"

    def http_tool(url: str, method: str = "GET", body: str | None = None, headers: dict | None = None) -> str:
        return http(url, method, body, headers)

    def http_local(url: str, method: str = "GET", body: str | None = None, headers: dict | None = None) -> str:
        if not _is_local(url):
            raise ToolError("not_local", f"{url} is not a local address.", "Use http_external for internet addresses.")
        return http(url, method, body, headers)

    reg.register(Tool("http_local", "Send an HTTP request to an app running on this computer or in the sandbox "
                                    "(localhost / 127.0.0.1 / private network). Use start_process's port map.",
                      obj({"url": S, "method": S, "body": S, "headers": {"type": "object"}}, ["url"]),
                      http_local, "exec", "verify"))
    reg.register(Tool("http_external", "Send an HTTP request to an internet address (asks the user first).",
                      obj({"url": S, "method": S, "body": S, "headers": {"type": "object"}}, ["url"]),
                      http_tool, EXTERNAL, "verify"))

    def db_query(sql: str, database: str = "dev.db") -> str:
        p = session.workspace.resolve(database)
        if not p.name.endswith((".db", ".sqlite", ".sqlite3")):
            raise ToolError("not_sqlite", "db_query works on SQLite development databases (.db/.sqlite).",
                            "For PostgreSQL/MySQL use run with psql or mysql inside the sandbox.")
        con = sqlite3.connect(p)
        try:
            cur = con.execute(sql)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchmany(200)
                lines = [" | ".join(cols)] + [" | ".join(str(v) for v in row) for row in rows]
                return "\n".join(lines) + ("" if len(rows) < 200 else "\n…(first 200 rows)")
            con.commit()
            return f"OK, {cur.rowcount} row(s) affected."
        except sqlite3.Error as e:
            raise ToolError("sql_error", str(e)) from e
        finally:
            con.close()

    reg.register(Tool("db_query", "Run SQL on the project's SQLite development database.",
                      obj({"sql": S, "database": S}, ["sql"]), db_query, WRITE, "verify", "sql"))
