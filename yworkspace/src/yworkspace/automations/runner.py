"""Automations: defined once, run by yWorkspace when they are due.

Stored in the project (.yw/automations.json) with their history. Rules from the plan:
- they run while the computer is on; a missed run is done at the next start (catch_up="run") or asked
  (catch_up="ask") or skipped (catch_up="skip");
- steps that act outside the computer (send, publish, pay) wait for approval unless explicitly pre-approved;
- every automation has a budget and a run history.
"""

from __future__ import annotations

import fnmatch
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from ..tools.registry import DESTRUCTIVE, EXTERNAL
from .schedule import Cron

EVENTS = ("file_added", "file_changed", "tests_failed", "security_alert", "incident", "manual")


@dataclass
class Automation:
    name: str
    steps: list[dict]  # {"tool": name, "args": {...}} or {"prompt": "...", "role": "developer"}
    schedule: str = ""  # cron or friendly words
    event: str = ""  # one of EVENTS
    pattern: str = ""  # for file events: glob, e.g. "inbox/*.csv"
    catch_up: str = "run"  # run | ask | skip
    budget_usd: float = 1.0
    approved_external: list[str] = field(default_factory=list)  # tools allowed to act outside without asking
    enabled: bool = True
    id: str = ""
    created: float = 0.0
    last_run: float = 0.0
    snapshot: dict = field(default_factory=dict)  # file mtimes for file events
    history: list[dict] = field(default_factory=list)
    pending: dict = field(default_factory=dict)  # a run waiting for approval


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / ".yw" / "automations.json"

    def load(self) -> list[Automation]:
        if not self.path.exists():
            return []
        return [Automation(**a) for a in json.loads(self.path.read_text("utf-8"))]

    def save(self, items: list[Automation]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(a) for a in items], indent=2, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)

    def get(self, items: list[Automation], key: str) -> Automation | None:
        return next((a for a in items if a.id == key or a.name == key), None)


def validate(a: Automation, registry) -> list[str]:
    problems = []
    if not a.steps:
        problems.append("an automation needs at least one step")
    if not a.schedule and not a.event:
        problems.append("set a schedule (e.g. 'her gece', '0 9 * * 1') or an event")
    if a.schedule:
        try:
            Cron(a.schedule)
        except ValueError as e:
            problems.append(str(e))
    if a.event and a.event not in EVENTS:
        problems.append(f"event must be one of {', '.join(EVENTS)}")
    if a.event in ("file_added", "file_changed") and not a.pattern:
        problems.append("file events need a pattern, e.g. inbox/*.csv")
    if a.catch_up not in ("run", "ask", "skip"):
        problems.append("catch_up must be run, ask or skip")
    for i, s in enumerate(a.steps, 1):
        if "tool" in s:
            if registry.get(s["tool"]) is None:
                problems.append(f"step {i}: unknown tool {s['tool']}")
            elif s["tool"].startswith("automation_"):
                problems.append(f"step {i}: automations cannot manage automations")
        elif "prompt" not in s:
            problems.append(f"step {i}: needs a tool or a prompt")
    return problems


def _files(root: Path, pattern: str) -> dict[str, float]:
    return {p.relative_to(root).as_posix(): p.stat().st_mtime for p in root.glob(pattern) if p.is_file()
            and ".yw" not in p.relative_to(root).parts}


class Runner:
    def __init__(self, session, now=None):
        self.session = session
        self.root = session.workspace.root
        self.store = Store(self.root)
        self.now = now or datetime.now

    # ------------------------------------------------------------------ what is due
    def due(self, items: list[Automation], events: list[dict] | None = None) -> list[tuple[Automation, str, dict]]:
        out = []
        now = self.now()
        for a in items:
            if not a.enabled or a.pending:
                continue
            if a.schedule:
                cron = Cron(a.schedule)
                last_slot = cron.last_before(now)
                ran = datetime.fromtimestamp(a.last_run) if a.last_run else datetime.fromtimestamp(a.created)
                if last_slot and last_slot > ran:
                    late = (now - last_slot).total_seconds() > 120
                    if not late:
                        out.append((a, "schedule", {}))
                    elif a.catch_up == "run":
                        out.append((a, f"missed run of {last_slot:%Y-%m-%d %H:%M}", {}))
                    elif a.catch_up == "ask":
                        a.pending = {"reason": f"missed run of {last_slot:%Y-%m-%d %H:%M}", "ask": "catch_up",
                                     "since": self.now().timestamp()}
                    else:
                        a.last_run = self.now().timestamp()
                        a.history.append({"time": self.now().timestamp(), "status": "skipped",
                                          "reason": f"missed {last_slot:%Y-%m-%d %H:%M}"})
            if a.event in ("file_added", "file_changed"):
                current = _files(self.root, a.pattern)
                if a.snapshot or a.history:
                    new = [f for f in current if f not in a.snapshot]
                    changed = [f for f in current if f in a.snapshot and current[f] > a.snapshot[f]]
                    hits = new if a.event == "file_added" else new + changed
                    if hits:
                        out.append((a, f"{a.event}: {', '.join(sorted(hits)[:5])}", {"files": sorted(hits)}))
                a.snapshot = current
            for ev in events or []:
                if ev.get("type") == a.event and a.event not in ("file_added", "file_changed"):
                    out.append((a, a.event, ev))
        return out

    # ------------------------------------------------------------------ running
    def run(self, a: Automation, reason: str, context: dict | None = None, approved: bool = False) -> dict:
        reg = self.session.registry
        eng = self.session.engine
        record = {"time": self.now().timestamp(), "reason": reason, "steps": [], "status": "ok"}
        prev = ""
        start_cost = eng.state.cost_usd if eng else 0.0
        ctx = {"files": ", ".join((context or {}).get("files", [])), "date": f"{self.now():%Y-%m-%d}",
               **{k: str(v) for k, v in (context or {}).items() if k != "files"}}
        start = a.pending.get("step", 0) if approved and a.pending else 0
        if approved and a.pending.get("prev"):
            prev = a.pending["prev"]
        a.pending = {}
        hook_installed = None
        allowed_now: set[str] = set()  # the one outside step the user just approved
        if eng is not None:
            def guard(tool, args):
                if tool.risk in (EXTERNAL, DESTRUCTIVE) and tool.name not in a.approved_external and \
                        tool.name not in allowed_now:
                    return (f"ERROR [needs_approval]: {tool.name} acts outside this computer; inside an automation "
                            "it needs the user's approval. Prepare everything and stop; the user will approve.")
                return None
            reg.before_call.append(guard)
            hook_installed = guard
        try:
            for i, step in enumerate(a.steps[start:], start):
                if eng and eng.state.cost_usd - start_cost > a.budget_usd:
                    record["status"] = "budget"
                    record["steps"].append({"step": i + 1, "error": f"budget ${a.budget_usd} reached"})
                    break
                if "tool" in step:
                    tool = reg.get(step["tool"])
                    if tool is None:
                        record["status"] = "failed"
                        record["steps"].append({"step": i + 1, "tool": step["tool"], "error": "tool not available"})
                        break
                    if tool.risk in (EXTERNAL, DESTRUCTIVE) and step["tool"] not in a.approved_external and \
                            not (approved and i == start):
                        a.pending = {"step": i, "prev": prev, "ask": "approve", "tool": step["tool"],
                                     "args": step.get("args", {}), "reason": reason, "since": self.now().timestamp()}
                        record["status"] = "waiting_approval"
                        record["steps"].append({"step": i + 1, "tool": step["tool"], "waiting": True})
                        break
                    args = _fill(step.get("args", {}), prev, ctx)
                    if approved and i == start:
                        allowed_now.add(step["tool"])
                    res = reg.call(step["tool"], args)
                    allowed_now.clear()
                    prev = res.text
                    record["steps"].append({"step": i + 1, "tool": step["tool"], "ok": not res.is_error,
                                            "output": res.text[-1500:]})
                    if res.is_error:
                        record["status"] = "failed"
                        break
                else:
                    if eng is None:
                        record["status"] = "failed"
                        record["steps"].append({"step": i + 1, "error": "prompt steps need a model (yw setup)"})
                        break
                    prompt = _fill(step["prompt"], prev, ctx)
                    out = eng.run_role(step.get("role", "developer"), prompt + (
                        f"\n\nOutput of the previous step:\n{prev[-6000:]}" if prev and "{prev}" not in step["prompt"]
                        else ""), max_steps=step.get("max_steps", 40))
                    prev = out or ""
                    record["steps"].append({"step": i + 1, "prompt": step["prompt"][:200], "ok": True,
                                            "output": prev[-1500:]})
        finally:
            if hook_installed is not None:
                reg.before_call.remove(hook_installed)
        if eng:
            record["cost_usd"] = round(eng.state.cost_usd - start_cost, 4)
        a.last_run = self.now().timestamp()
        a.history = (a.history + [record])[-50:]
        return record

    def tick(self, events: list[dict] | None = None) -> list[str]:
        items = self.store.load()
        lines = []
        for a, reason, ctx in self.due(items, events):
            rec = self.run(a, reason, ctx)
            lines.append(f"{a.name}: {rec['status']} ({reason})")
        self.store.save(items)
        return lines


def _fill(value, prev: str, ctx: dict):
    if isinstance(value, str):
        out = value.replace("{prev}", prev)
        for k, v in ctx.items():
            out = out.replace("{" + k + "}", v)
        return out
    if isinstance(value, dict):
        return {k: _fill(v, prev, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, prev, ctx) for v in value]
    return value


def new(name: str, steps: list[dict], **kw) -> Automation:
    if not re.fullmatch(r"[\w .-]{1,60}", name):
        raise ValueError("name: up to 60 letters, digits, spaces, . _ -")
    return Automation(name=name, steps=steps, id=uuid.uuid4().hex[:8], created=time.time(), **kw)


def autostart_files(project: Path, yw: str = "yw") -> dict[str, str]:
    """OS service definitions so automations run whenever the user is logged in."""
    project = Path(project).resolve()
    cmd = f'{yw} automations daemon --project "{project}"'
    return {
        "linux (~/.config/systemd/user/yworkspace-automations.service)":
            "[Unit]\nDescription=yWorkspace automations\n\n[Service]\nExecStart=" + cmd +
            "\nRestart=on-failure\n\n[Install]\nWantedBy=default.target\n",
        "macos (~/Library/LaunchAgents/com.yunuslu.yworkspace.automations.plist)":
            '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>\n'
            "<key>Label</key><string>com.yunuslu.yworkspace.automations</string>\n"
            f"<key>ProgramArguments</key><array><string>{yw}</string><string>automations</string>"
            f"<string>daemon</string><string>--project</string><string>{project}</string></array>\n"
            "<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>\n</dict></plist>\n",
        "windows (run in PowerShell)":
            f'schtasks /Create /SC ONLOGON /TN "yWorkspace Automations" /TR "{cmd}" /RL LIMITED /F\n',
    }


def match_glob(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern)
