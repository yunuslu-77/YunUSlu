"""Run commands directly on this computer. Only used when the user explicitly opts out of Docker."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import ToolError
from .docker import _NAME_RX, RunResult, clip


@dataclass
class LocalSandbox:
    root: Path
    _procs: dict[str, subprocess.Popen] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        self.logdir = self.root / ".yw" / "proc"
        self.logdir.mkdir(parents=True, exist_ok=True)

    def ensure(self) -> None:
        pass

    def stop(self) -> None:
        for name in list(self._procs):
            self.stop_process(name)

    def _cwd(self, cwd: str | None) -> Path:
        full = (self.root / (cwd or ".")).resolve()
        if full != self.root and self.root not in full.parents:
            raise ToolError("outside_workspace", f"{cwd} is outside the project folder.")
        return full

    def run(self, command: str, timeout: int = 120, cwd: str | None = None, as_root: bool = False) -> RunResult:
        if not command.strip():
            raise ToolError("empty_command", "The command is empty.")
        start = time.monotonic()
        try:
            r = subprocess.run(command, shell=True, cwd=self._cwd(cwd), capture_output=True, text=True,
                               timeout=timeout, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or "") if isinstance(e.stdout, str) else ""
            return RunResult(124, clip(out + f"\n[stopped after {timeout}s]"), time.monotonic() - start, True)
        return RunResult(r.returncode, clip(r.stdout + r.stderr), time.monotonic() - start)

    def start_process(self, name: str, command: str, cwd: str | None = None) -> str:
        if not _NAME_RX.match(name):
            raise ToolError("bad_name", "Process names may only use letters, digits, '-', '_' and '.'.")
        if name in self._procs and self._procs[name].poll() is None:
            raise ToolError("already_running", f"A process named {name} is already running.")
        log = open(self.logdir / f"{name}.log", "w", encoding="utf-8")
        kwargs = {"start_new_session": True} if sys.platform != "win32" else {}
        self._procs[name] = subprocess.Popen(command, shell=True, cwd=self._cwd(cwd), stdout=log,
                                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kwargs)
        time.sleep(1.0)
        state = "running" if self._procs[name].poll() is None else "exited immediately"
        return f"Started {name} ({state}).\n{self.logs(name, 30)}"

    def logs(self, name: str, tail: int = 100) -> str:
        p = self.logdir / f"{name}.log"
        lines = p.read_text("utf-8", errors="replace").splitlines()[-tail:] if p.exists() else []
        return f"[logs of {name}, last {tail} lines]\n" + clip("\n".join(lines))

    def stop_process(self, name: str) -> str:
        p = self._procs.get(name)
        if not p or p.poll() is not None:
            return f"{name} is not running."
        if sys.platform != "win32":
            os.killpg(p.pid, signal.SIGTERM)
        else:
            p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
        return f"Stopped {name}."

    def processes(self) -> str:
        if not self._procs:
            return "No background processes."
        return "\n".join(f"{n} {'running' if p.poll() is None else 'stopped'}" for n, p in self._procs.items())

    def port_map(self) -> str:
        return ""

    def install(self, manager: str, packages: list[str], timeout: int = 900) -> RunResult:
        cmd = {"pip": f"{sys.executable} -m pip install", "npm": "npm install", "pnpm": "pnpm add"}.get(manager)
        if not cmd:
            raise ToolError("bad_manager", f"{manager} is not available outside Docker.")
        return self.run(f"{cmd} {' '.join(packages)}", timeout=timeout)
