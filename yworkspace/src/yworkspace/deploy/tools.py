"""Deploy tools: list targets, prepare (write files + show the plan), run (always asks), verify."""

from __future__ import annotations

import subprocess
import time

from ..core.errors import ToolError
from ..extensions import register
from ..tools.registry import EXTERNAL, SAFE, WRITE, Tool, obj
from .targets import all_targets

S = {"type": "string"}


def run_host(cmd: str, cwd, timeout: int = 1800) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr)[-8000:]


@register
def install(session) -> None:
    reg, ws = session.registry, session.workspace
    runner = {"fn": run_host}  # replaceable in tests

    def target(name: str):
        t = all_targets().get(name)
        if t is None:
            raise ToolError("no_target", f"Unknown deploy target {name}.", f"Use one of: {', '.join(all_targets())}")
        return t

    def deploy_targets() -> str:
        return "\n".join(f"- {t.name}: {t.description}" for t in all_targets().values())

    def deploy_prepare(name: str, options: dict | None = None) -> str:
        plan = target(name).plan(ws.root, options or {})
        for path, content in plan.files.items():
            full = ws.root / path
            if full.exists():
                ws.read(path)
            ws.create(path, content, overwrite=full.exists())
        return plan.text() + ("\n\nReady to deploy." if not plan.missing else
                              "\n\nFix the MISSING items before deploying.")

    def deploy_run(name: str, options: dict | None = None) -> str:
        plan = target(name).plan(ws.root, options or {})
        if plan.missing:
            raise ToolError("not_ready", "Deployment prerequisites are missing:\n" + "\n".join(plan.missing),
                            "Call deploy_prepare and fix the missing items first.")
        out = []
        for cmd in plan.commands:
            code, text = runner["fn"](cmd, ws.root)
            out.append(f"$ {cmd}\n{text}")
            if code != 0:
                raise ToolError("deploy_failed", "\n".join(out)[-6000:], "Read the error, fix it, and try again.")
        result = "\n".join(out)
        if plan.url:
            result += "\n\n" + deploy_verify(plan.url)
        return result

    def deploy_verify(url: str, expect: str = "", attempts: int = 10) -> str:
        import httpx
        last = ""
        for i in range(attempts):
            try:
                r = httpx.get(url, timeout=15, follow_redirects=True)
                if r.status_code < 400 and (not expect or expect in r.text):
                    return f"VERIFIED: {url} answered HTTP {r.status_code}."
                last = f"HTTP {r.status_code}"
            except httpx.HTTPError as e:
                last = str(e)
            time.sleep(min(30, 3 * (i + 1)))
        raise ToolError("verify_failed", f"{url} is not healthy: {last}", "Check the server logs.")

    reg.register(Tool("deploy_targets", "List the places a project can be deployed to.", obj({}), deploy_targets,
                      SAFE, "deploy"))
    reg.register(Tool("deploy_prepare", "Write the deployment files for a target and show the plan, prerequisites "
                      "and anything missing. options: target-specific (vps: host, user, domain, app_port, remote_dir).",
                      obj({"name": S, "options": {"type": "object"}}, ["name"]), deploy_prepare, WRITE, "deploy"))
    reg.register(Tool("deploy_run", "Deploy now (always asks the user first), then verify the live URL.",
                      obj({"name": S, "options": {"type": "object"}}, ["name"]), deploy_run, EXTERNAL, "deploy"))
    reg.register(Tool("deploy_verify", "Check that a live URL answers successfully.",
                      obj({"url": S, "expect": S}, ["url"]), deploy_verify, EXTERNAL, "deploy"))
    session.deploy_runner = runner
