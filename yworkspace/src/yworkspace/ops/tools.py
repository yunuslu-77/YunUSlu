"""Maintenance & monitoring tools, and the automatic fix loop for production incidents."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..core.errors import ToolError
from ..extensions import register
from ..tools.registry import SAFE, WRITE, Tool, obj
from .monitor import Monitor

AGENT_DIR = Path(__file__).parent / "agent"


def fix_incident(session, incident_id: str, deploy: bool = True) -> str:
    """Root-cause, fix, test and (with approval) deploy a production incident."""
    mon = Monitor(session.workspace.root)
    inc = next((i for i in mon.incidents() if i.id == incident_id), None)
    if inc is None:
        raise ToolError("not_found", f"No incident {incident_id}.")
    eng = session.engine
    if eng is None:
        raise ToolError("no_engine", "The fix loop needs the Deep Work Engine (configure a model).")
    mon.set_status(inc.id, "fixing")
    st = eng.state
    st.add_task(f"Fix production incident {inc.id}: {inc.summary[:80]}",
                description=f"Kind: {inc.kind}\nSeen {inc.count} times.\nEvidence:\n{inc.evidence[:4000]}\n\n"
                            "1. Reproduce it locally (write a failing test first).\n2. Find the root cause.\n"
                            "3. Fix it and keep the new test.\n4. Run all checks.",
                acceptance=["A test reproduces the incident and now passes", "All checks pass"],
                verify="the new regression test", hard=True)
    st.save()
    report = eng.run(st.goal or f"Fix incident {inc.id}")
    lines = [report.text()]
    if report.finished:
        mon.set_status(inc.id, "fixed")
        if deploy and session.registry.get("deploy_run") and (mon.config().get("deploy_target")):
            res = session.registry.call("deploy_run", {"name": mon.config()["deploy_target"],
                                                       "options": mon.config().get("deploy_options", {})})
            lines.append("Deploy: " + res.text[:3000])
            if not res.is_error:
                after = mon.run_checks()
                lines.append("After deploy: " + after.text())
    else:
        mon.set_status(inc.id, "open")
    return "\n\n".join(lines)


@register
def install(session) -> None:
    reg, root = session.registry, session.workspace.root
    mon = Monitor(root)

    def monitor_setup(config: dict) -> str:
        allowed = {"urls", "ssl_hosts", "logs_cmd", "disk_cmd", "backup_dir", "backup_cmd", "backup_max_age_hours",
                   "restore_test_cmd", "agent_cmd", "deploy_target", "deploy_options", "ssl_warn_days",
                   "disk_warn_percent", "insecure_tls"}
        unknown = set(config) - allowed
        if unknown:
            raise ToolError("bad_config", f"Unknown keys: {', '.join(sorted(unknown))}", f"Allowed: {sorted(allowed)}")
        merged = {**mon.config(), **config}
        mon.save_config(merged)
        return "Monitoring configured:\n" + json.dumps(merged, indent=2)

    def monitor_run() -> str:
        if not mon.config():
            raise ToolError("not_configured", "Monitoring is not configured.", "Call monitor_setup first.")
        return mon.run_checks().text()

    def incidents(status: str = "open") -> str:
        items = [i for i in mon.incidents() if status == "all" or i.status == status]
        if not items:
            return f"No {status} incidents."
        return "\n\n".join(f"{i.id} [{i.status}] {i.kind}: {i.summary} (seen {i.count}x)\n{i.evidence[:600]}"
                           for i in items)

    def incident_fix(incident_id: str, deploy: bool = True) -> str:
        return fix_incident(session, incident_id, deploy)

    def health_report(days: int = 30) -> str:
        return mon.health_report(days)

    def agent_files(folder: str = "deploy/agent") -> str:
        dest = session.workspace.resolve(folder)
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("yw_agent.py", "install.sh"):
            shutil.copy2(AGENT_DIR / name, dest / name)
        cfg = {"urls": mon.config().get("urls", ["http://127.0.0.1:8000/health"]), "backup_dir": "/backups",
               "backup_max_age_hours": 26, "disk_warn_percent": 85, "status_file": "/var/lib/yw-agent/status.json"}
        (dest / "yw-agent.json").write_text(json.dumps(cfg, indent=2), "utf-8")
        return (f"Agent files written to {folder}. Copy the folder to the server and run `sudo bash install.sh` there. "
                "Then monitor_setup with agent_cmd = \"ssh <user>@<host> cat /var/lib/yw-agent/status.json\".")

    for t in [
        Tool("monitor_setup", "Configure monitoring for the live app (urls, ssl_hosts, logs_cmd, disk_cmd, backup_dir/"
             "backup_cmd, restore_test_cmd, agent_cmd, deploy_target, deploy_options).",
             obj({"config": {"type": "object"}}, ["config"]), monitor_setup, WRITE, "ops"),
        Tool("monitor_run", "Run all monitoring checks now and record new incidents.", obj({}), monitor_run,
             "exec", "ops"),
        Tool("incidents", "List incidents (status: open, fixing, fixed, all).", obj({"status": {"type": "string"}}),
             incidents, SAFE, "ops"),
        Tool("incident_fix", "Fix an incident end to end: reproduce with a test, root-cause, fix, pass all gates, then "
             "deploy (asks first) and re-check.", obj({"incident_id": {"type": "string"}, "deploy": {"type": "boolean"}},
                                                     ["incident_id"]), incident_fix, WRITE, "ops"),
        Tool("health_report", "Health report for the last N days: uptime, response time, incidents, backups.",
             obj({"days": {"type": "integer"}}), health_report, SAFE, "ops"),
        Tool("agent_files", "Write the server monitoring agent (local only, sends nothing) into the project.",
             obj({"folder": {"type": "string"}}), agent_files, WRITE, "ops"),
    ]:
        reg.register(t)
