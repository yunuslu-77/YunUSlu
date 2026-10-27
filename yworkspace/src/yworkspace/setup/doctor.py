"""System health checks used by `yw doctor`, the setup wizard and the web UI."""

from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import dataclass

from ..config import Config, get_secret


@dataclass
class HealthItem:
    name: str
    ok: bool
    detail: str = ""
    required: bool = True
    fix: str = ""


def run_doctor(cfg: Config) -> list[HealthItem]:
    from ..models.profiles import get_profile
    from ..sandbox import docker_available

    items = [HealthItem("Python ≥ 3.10", sys.version_info >= (3, 10), platform.python_version())]
    if cfg.sandbox == "docker":
        ok = docker_available()
        items.append(HealthItem("Docker", ok, "" if ok else "not running", True,
                                "Run the setup wizard: yw setup"))
    else:
        items.append(HealthItem("Sandbox", True, "local mode (commands run directly on this computer)", False))
        if sys.platform == "win32":
            from ..sandbox.local import windows_bash
            bash = windows_bash()
            items.append(HealthItem("bash (Git for Windows)", bash is not None, bash or "missing: commands fall back to "
                                    "cmd.exe and many will fail", True, "Install Git for Windows: winget install Git.Git"))
    items.append(HealthItem("git", shutil.which("git") is not None, "", False))
    try:
        prof = get_profile(cfg.model)
        if prof.local:
            items.append(HealthItem(f"Model {prof.id}", True, "local model"))
        else:
            has = bool(prof.key_env and get_secret(prof.key_env))
            items.append(HealthItem(f"Model {prof.id}", has, "" if has else f"missing {prof.key_env}", True,
                                    f"yw key {prof.key_env} <your-key>"))
    except KeyError as e:
        items.append(HealthItem("Model", False, str(e)))
    from ..config import home
    free = shutil.disk_usage(home().parent if home().parent.exists() else "/").free // 2**30
    items.append(HealthItem("Disk space", free >= 10, f"{free} GB free", False))
    return items
