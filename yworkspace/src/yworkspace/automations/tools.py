"""Automation tools for the AI and the web UI; `yw automations daemon` runs them on time."""

from __future__ import annotations

from datetime import datetime

from ..core.errors import ToolError
from ..extensions import register
from ..tools.registry import EXEC, SAFE, WRITE, Tool, obj
from . import runner as rn
from .schedule import Cron

S = {"type": "string"}


@register
def install(session) -> None:
    reg = session.registry
    store = rn.Store(session.workspace.root)

    def find(items, key):
        a = store.get(items, key)
        if a is None:
            raise ToolError("not_found", f"No automation {key!r}.", "Use automation_list.")
        return a

    def automation_create(name: str, steps: list[dict], schedule: str = "", event: str = "", pattern: str = "",
                          catch_up: str = "run", budget_usd: float = 1.0) -> str:
        items = store.load()
        if store.get(items, name):
            raise ToolError("exists", f"An automation named {name!r} already exists.")
        try:
            a = rn.new(name, steps, schedule=schedule, event=event, pattern=pattern, catch_up=catch_up,
                       budget_usd=budget_usd)
        except ValueError as e:
            raise ToolError("bad_name", str(e)) from e
        problems = rn.validate(a, reg)
        if problems:
            raise ToolError("invalid", "; ".join(problems))
        if a.event in ("file_added", "file_changed"):
            a.snapshot = rn._files(session.workspace.root, a.pattern)  # only files that arrive later count
        items.append(a)
        store.save(items)
        when = (f"schedule {Cron(schedule).expr}, next run {Cron(schedule).next_after(datetime.now()):%Y-%m-%d %H:%M}"
                if schedule else f"on {event} {pattern}".strip())
        external = [s["tool"] for s in steps if "tool" in s and reg.get(s["tool"]).risk in ("external", "destructive")]
        return (f"Created automation {a.id} '{name}' ({when}, {len(steps)} steps, budget ${budget_usd}). "
                + (f"Steps {', '.join(external)} will wait for the user's approval each time. " if external else "")
                + "It runs while yWorkspace is running (yw automations daemon, or the web UI).")

    def automation_list() -> str:
        items = store.load()
        if not items:
            return "No automations."
        rows = []
        for a in items:
            when = Cron(a.schedule).expr if a.schedule else f"{a.event} {a.pattern}".strip()
            last = a.history[-1] if a.history else None
            rows.append(f"{a.id} {'●' if a.enabled else '○'} {a.name} — {when}; last: "
                        + (f"{datetime.fromtimestamp(last['time']):%Y-%m-%d %H:%M} {last['status']}" if last else
                           "never") + (f"; WAITING: {a.pending.get('ask')} ({a.pending.get('reason')})"
                                       if a.pending else ""))
        return "\n".join(rows)

    def automation_run(key: str) -> str:
        items = store.load()
        a = find(items, key)
        rec = rn.Runner(session).run(a, "run by hand")
        store.save(items)
        return _render(a, rec)

    def automation_approve(key: str, approve: bool = True) -> str:
        items = store.load()
        a = find(items, key)
        if not a.pending:
            raise ToolError("nothing_pending", f"{a.name} is not waiting for anything.")
        if not approve:
            a.history.append({"time": a.pending.get("since"), "status": "rejected", "reason": a.pending.get("reason")})
            a.pending = {}
            store.save(items)
            return f"Rejected; {a.name} will run again at its next time."
        if a.pending.get("ask") == "catch_up":
            a.pending = {}
            rec = rn.Runner(session).run(a, "missed run, approved by the user")
        else:
            rec = rn.Runner(session).run(a, a.pending.get("reason", "approved"), approved=True)
        store.save(items)
        return _render(a, rec)

    def automation_history(key: str, last: int = 5) -> str:
        a = find(store.load(), key)
        out = []
        for h in a.history[-last:]:
            out.append(f"{datetime.fromtimestamp(h['time']):%Y-%m-%d %H:%M} {h['status']} — {h.get('reason', '')}"
                       + (f" (${h['cost_usd']})" if "cost_usd" in h else ""))
            for s in h.get("steps", []):
                out.append(f"   {s.get('step')}. {s.get('tool') or s.get('prompt', '')[:60]}: "
                           f"{'ok' if s.get('ok') else s.get('error') or ('waiting' if s.get('waiting') else 'failed')}")
        return "\n".join(out) or "Never ran."

    def automation_set(key: str, enabled: bool | None = None, delete: bool = False, schedule: str = "",
                       budget_usd: float | None = None) -> str:
        items = store.load()
        a = find(items, key)
        if delete:
            items.remove(a)
            store.save(items)
            return f"Deleted {a.name}."
        if enabled is not None:
            a.enabled = enabled
        if schedule:
            Cron(schedule)
            a.schedule = schedule
        if budget_usd is not None:
            a.budget_usd = budget_usd
        store.save(items)
        return f"Updated {a.name}."

    def automation_autostart() -> str:
        files = rn.autostart_files(session.workspace.root)
        return "To run automations whenever you log in, install one of these (the setup wizard can do it):\n\n" + \
            "\n\n".join(f"## {k}\n{v}" for k, v in files.items())

    tools = [
        Tool("automation_create", "Create a repeating job. schedule: cron ('0 9 * * 1') or words ('her gece', "
             "'weekly', 'every 15 minutes'); or event: file_added/file_changed (pattern), tests_failed, "
             "security_alert, incident. steps: [{tool, args}] or [{prompt, role}]; '{prev}' inserts the previous "
             "step's output, '{files}' the new files, '{date}' today. Outside actions wait for approval.",
             obj({"name": S, "steps": {"type": "array", "items": {"type": "object"}}, "schedule": S, "event": S,
                  "pattern": S, "catch_up": {"type": "string", "enum": ["run", "ask", "skip"]},
                  "budget_usd": {"type": "number"}}, ["name", "steps"]), automation_create, WRITE, "automation"),
        Tool("automation_list", "List automations, their schedule, last result and anything waiting for approval.",
             obj({}), automation_list, SAFE, "automation"),
        Tool("automation_run", "Run an automation now.", obj({"key": S}, ["key"]), automation_run, EXEC,
             "automation"),
        Tool("automation_approve", "Approve (or reject) the step an automation is waiting on - only when the user "
             "said so.", obj({"key": S, "approve": {"type": "boolean"}}, ["key"]), automation_approve, EXEC,
             "automation"),
        Tool("automation_history", "Run history of an automation.", obj({"key": S, "last": {"type": "integer"}},
                                                                        ["key"]), automation_history, SAFE,
             "automation"),
        Tool("automation_set", "Enable, disable, delete, reschedule or change the budget of an automation.",
             obj({"key": S, "enabled": {"type": "boolean"}, "delete": {"type": "boolean"}, "schedule": S,
                  "budget_usd": {"type": "number"}}, ["key"]), automation_set, WRITE, "automation"),
        Tool("automation_autostart", "Show how to start the automation runner at login (Linux, macOS, Windows).",
             obj({}), automation_autostart, SAFE, "automation"),
    ]
    for t in tools:
        reg.register(t)


def _render(a, rec: dict) -> str:
    lines = [f"{a.name}: {rec['status']}"]
    for s in rec["steps"]:
        name = s.get("tool") or "prompt"
        if s.get("waiting"):
            lines.append(f"  {s['step']}. {name}: WAITING FOR APPROVAL (automation_approve after the user agrees)")
        else:
            lines.append(f"  {s['step']}. {name}: {'ok' if s.get('ok') else 'FAILED'} {s.get('error', '')}\n"
                         f"     {s.get('output', '')[-400:]}")
    return "\n".join(lines)
