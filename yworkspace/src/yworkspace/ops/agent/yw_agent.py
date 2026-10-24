#!/usr/bin/env python3
"""yWorkspace server agent. Runs on YOUR server (cron/systemd timer), standard library only.

It checks the app, containers, disk and backups and writes the result to a local file.
It never sends data anywhere: yWorkspace reads the file over your own SSH connection.

Config: /etc/yw-agent.json  {"urls": [...], "backup_dir": "/backups", "backup_max_age_hours": 26,
                             "disk_warn_percent": 85, "status_file": "/var/lib/yw-agent/status.json"}
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

DEFAULT_CONFIG = "/etc/yw-agent.json"


def check_url(url):
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            ms = (time.monotonic() - start) * 1000
            return {"ok": r.status < 400, "detail": f"HTTP {r.status}, {ms:.0f} ms"}
    except Exception as e:  # noqa: BLE001 - any failure means "down"
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}


def check_containers():
    if not shutil.which("docker"):
        return {"ok": True, "detail": "docker not installed"}
    out = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"], capture_output=True, text=True)
    bad = [ln for ln in out.stdout.splitlines() if "unhealthy" in ln or "Exited" in ln or "Restarting" in ln]
    return {"ok": not bad, "detail": "; ".join(bad) or f"{len(out.stdout.splitlines())} containers fine"}


def check_disk(warn):
    total, used, _free = shutil.disk_usage("/")
    pct = used * 100 / total
    return {"ok": pct < warn, "detail": f"{pct:.0f}% used"}


def check_backups(folder, max_age_hours):
    if not folder or not os.path.isdir(folder):
        return {"ok": False, "detail": f"backup folder {folder} missing"}
    files = [os.path.join(folder, f) for f in os.listdir(folder)]
    if not files:
        return {"ok": False, "detail": "no backups"}
    age = (time.time() - max(os.path.getmtime(f) for f in files)) / 3600
    return {"ok": age <= max_age_hours, "detail": f"newest backup {age:.1f} h old"}


def main(config_path=DEFAULT_CONFIG):
    cfg = json.load(open(config_path)) if os.path.exists(config_path) else {}
    checks = {f"url {u}": check_url(u) for u in cfg.get("urls", [])}
    checks["containers"] = check_containers()
    checks["disk"] = check_disk(cfg.get("disk_warn_percent", 85))
    if cfg.get("backup_dir"):
        checks["backups"] = check_backups(cfg["backup_dir"], cfg.get("backup_max_age_hours", 26))
    status = {"time": time.time(), "host": os.uname().nodename, "checks": checks,
              "ok": all(c["ok"] for c in checks.values())}
    path = cfg.get("status_file", "/var/lib/yw-agent/status.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status, f, indent=2)
    os.replace(tmp, path)
    print(json.dumps(status))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG))
