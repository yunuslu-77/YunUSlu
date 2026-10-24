"""Run the AI's commands inside an isolated Docker container that only sees the project folder."""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import ToolError

DEFAULT_IMAGE = os.environ.get("YW_SANDBOX_IMAGE", "python:3.12-slim")
DEFAULT_PORTS = (3000, 5000, 5173, 8000, 8080)
OUTPUT_HEAD = 6000
OUTPUT_TAIL = 6000
PROC_DIR = "/tmp/yw-proc"
_NAME_RX = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")


@dataclass
class RunResult:
    exit_code: int
    output: str
    duration: float
    timed_out: bool = False

    def to_text(self) -> str:
        status = "TIMED OUT" if self.timed_out else f"exit code {self.exit_code}"
        return f"[{status}, {self.duration:.1f}s]\n{self.output}".rstrip()


def clip(text: str) -> str:
    if len(text) <= OUTPUT_HEAD + OUTPUT_TAIL:
        return text
    skipped = len(text) - OUTPUT_HEAD - OUTPUT_TAIL
    return f"{text[:OUTPUT_HEAD]}\n…[{skipped} characters omitted]…\n{text[-OUTPUT_TAIL:]}"


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@dataclass
class DockerSandbox:
    root: Path
    image: str = DEFAULT_IMAGE
    memory: str = "4g"
    cpus: str = "2"
    pids_limit: int = 1024
    network: bool = True
    ports: tuple[int, ...] = DEFAULT_PORTS
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        digest = hashlib.sha1(str(self.root).encode()).hexdigest()[:10]
        self.name = f"yw-{digest}"

    # ---------------------------------------------------------- lifecycle
    def _docker(self, *args: str, timeout: float = 120, input: str | None = None) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout,
                                  input=input, encoding="utf-8", errors="replace")
        except FileNotFoundError as e:
            raise ToolError("no_docker", "Docker is not installed.",
                            "Run the yWorkspace setup wizard to install Docker.") from e

    def running(self) -> bool:
        r = self._docker("inspect", "-f", "{{.State.Running}}", self.name, timeout=30)
        return r.returncode == 0 and r.stdout.strip() == "true"

    def ensure(self) -> None:
        if self.running():
            return
        self._docker("rm", "-f", self.name, timeout=60)
        args = ["run", "-d", "--init", "--name", self.name, "--label", "yworkspace=1",
                "--label", f"yworkspace.root={self.root}",
                "-v", f"{self.root}:/workspace", "-w", "/workspace",
                "--memory", self.memory, "--cpus", self.cpus, "--pids-limit", str(self.pids_limit),
                "--security-opt", "no-new-privileges", "-e", "HOME=/home/yw",
                "-e", "PATH=/home/yw/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"]
        if not self.network:
            args += ["--network", "none"]
        else:
            for p in self.ports:
                args += ["-p", f"127.0.0.1::{p}"]
        for k, v in self.env.items():
            args += ["-e", f"{k}={v}"]
        args += [self.image, "sleep", "infinity"]
        r = self._docker(*args, timeout=600)
        if r.returncode != 0:
            raise ToolError("sandbox_start_failed", f"Could not start the sandbox container: {r.stderr.strip()[:800]}",
                            "Check that Docker is running (setup wizard → System Health).")
        uid = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "0:0"
        self._docker("exec", "-u", "0", self.name, "sh", "-c",
                     f"mkdir -p /home/yw {PROC_DIR} && chown -R {uid} /home/yw {PROC_DIR} && chmod 1777 {PROC_DIR}",
                     timeout=60)

    def stop(self) -> None:
        self._docker("rm", "-f", self.name, timeout=60)

    def _user(self) -> list[str]:
        return ["-u", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []

    # ---------------------------------------------------------- commands
    def _workdir(self, cwd: str | None) -> str:
        if not cwd or cwd in (".", "/workspace"):
            return "/workspace"
        full = (self.root / cwd).resolve()
        if full != self.root and self.root not in full.parents:
            raise ToolError("outside_workspace", f"{cwd} is outside the project folder.")
        return "/workspace/" + full.relative_to(self.root).as_posix()

    def run(self, command: str, timeout: int = 120, cwd: str | None = None, as_root: bool = False) -> RunResult:
        if not command.strip():
            raise ToolError("empty_command", "The command is empty.")
        self.ensure()
        timeout = max(1, min(int(timeout), 3600))
        user = ["-u", "0"] if as_root else self._user()
        wrapped = f"timeout -k 5 {timeout} sh -c {shlex.quote(command)}"
        start = time.monotonic()
        try:
            r = self._docker("exec", *user, "-w", self._workdir(cwd), self.name, "sh", "-c", wrapped,
                             timeout=timeout + 30)
        except subprocess.TimeoutExpired:
            return RunResult(124, "Command did not finish.", time.monotonic() - start, True)
        out = (r.stdout or "") + (r.stderr or "")
        timed_out = r.returncode in (124, 137) and time.monotonic() - start >= timeout
        if timed_out:
            out += (f"\n[stopped after {timeout}s. For servers and other long-running commands use "
                    "start_process instead.]")
        return RunResult(r.returncode, clip(out), time.monotonic() - start, timed_out)

    # ---------------------------------------------------- background processes
    def _check_name(self, name: str) -> str:
        if not _NAME_RX.match(name):
            raise ToolError("bad_name", "Process names may only use letters, digits, '-', '_' and '.'.")
        return name

    def start_process(self, name: str, command: str, cwd: str | None = None) -> str:
        self._check_name(name)
        self.ensure()
        if self._pid(name):
            raise ToolError("already_running", f"A process named {name} is already running.",
                            "Stop it first with stop_process, or pick another name.")
        log, pidf = f"{PROC_DIR}/{name}.log", f"{PROC_DIR}/{name}.pid"
        script = (f"cd {shlex.quote(self._workdir(cwd))} && : > {log} && "
                  f"setsid sh -c {shlex.quote(command)} >> {log} 2>&1 < /dev/null & echo $! > {pidf}")
        r = self._docker("exec", *self._user(), self.name, "sh", "-c", script, timeout=60)
        if r.returncode != 0:
            raise ToolError("start_failed", r.stderr.strip()[:800])
        time.sleep(1.0)
        status = "running" if self._pid(name) else "exited immediately"
        return f"Started {name} ({status}).\n{self.logs(name, 30)}\n{self.port_map()}".rstrip()

    def _pid(self, name: str) -> int | None:
        r = self._docker("exec", self.name, "sh", "-c",
                         f"p=$(cat {PROC_DIR}/{name}.pid 2>/dev/null) && kill -0 $p 2>/dev/null && echo $p",
                         timeout=30)
        out = r.stdout.strip()
        return int(out) if out.isdigit() else None

    def logs(self, name: str, tail: int = 100) -> str:
        self._check_name(name)
        r = self._docker("exec", self.name, "sh", "-c", f"tail -n {int(tail)} {PROC_DIR}/{name}.log 2>&1", timeout=30)
        return f"[logs of {name}, last {tail} lines]\n{clip(r.stdout)}".rstrip()

    def stop_process(self, name: str) -> str:
        self._check_name(name)
        pid = self._pid(name)
        if not pid:
            return f"{name} is not running."
        self._docker("exec", "-u", "0", self.name, "sh", "-c",
                     f"kill -TERM -{pid} 2>/dev/null || kill -TERM {pid}; sleep 2; kill -KILL -{pid} 2>/dev/null; true",
                     timeout=30)
        return f"Stopped {name}."

    def processes(self) -> str:
        r = self._docker("exec", self.name, "sh", "-c",
                         f"for f in {PROC_DIR}/*.pid; do [ -e \"$f\" ] || continue; n=$(basename $f .pid); "
                         f"if kill -0 $(cat $f) 2>/dev/null; then echo \"$n running\"; else echo \"$n stopped\"; fi; done",
                         timeout=30)
        return r.stdout.strip() or "No background processes."

    def port_map(self) -> str:
        r = self._docker("port", self.name, timeout=30)
        lines = [ln for ln in r.stdout.strip().splitlines() if ln]
        if not lines:
            return ""
        return "Ports (container -> your computer):\n" + "\n".join(f"  {ln}" for ln in lines)

    # ---------------------------------------------------------- packages
    def install(self, manager: str, packages: list[str], timeout: int = 900) -> RunResult:
        bad = [p for p in packages if not re.match(r"^[A-Za-z0-9@/._=<>!~^:+-]+$", p)]
        if bad or not packages:
            raise ToolError("bad_package", f"Invalid package names: {bad or packages}")
        pk = " ".join(shlex.quote(p) for p in packages)
        commands = {
            "pip": (f"pip install --user --no-input {pk}", False),
            "npm": (f"npm install {pk}", False),
            "pnpm": (f"pnpm add {pk}", False),
            "apt": (f"apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq {pk}", True),
        }
        if manager not in commands:
            raise ToolError("bad_manager", f"Unknown package manager {manager}.", f"Use one of: {', '.join(commands)}.")
        cmd, root = commands[manager]
        return self.run(cmd, timeout=timeout, as_root=root)
