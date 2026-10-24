"""Know the computer: OS, memory, disk, GPU. Standard library only, so it works before anything is installed."""

from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass
class GPU:
    vendor: str  # nvidia | amd | apple | intel | none
    name: str = ""
    vram_gb: float = 0.0


@dataclass
class SystemInfo:
    os: str  # windows | macos | linux
    os_version: str
    arch: str
    ram_gb: float
    disk_free_gb: float
    gpus: list[GPU] = field(default_factory=list)
    distro: str = ""  # linux: debian | fedora | arch | other
    wsl: bool = False

    @property
    def best_gpu(self) -> GPU:
        return max(self.gpus, key=lambda g: g.vram_gb, default=GPU("none"))

    def describe(self) -> str:
        g = self.best_gpu
        gpu = f"{g.name} ({g.vram_gb:.0f} GB)" if g.vendor != "none" else "yok / none"
        return (f"{self.os} {self.os_version} {self.arch}, RAM {self.ram_gb:.0f} GB, "
                f"boş disk {self.disk_free_gb:.0f} GB, GPU: {gpu}")


def _run(cmd: list[str], timeout: int = 10) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _ram_gb() -> float:
    if sys.platform.startswith("linux"):
        try:
            for line in open("/proc/meminfo"):
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) / 1024**2
        except OSError:
            return 0.0
    if sys.platform == "darwin":
        out = _run(["sysctl", "-n", "hw.memsize"]).strip()
        return int(out) / 1024**3 if out.isdigit() else 0.0
    if sys.platform == "win32":
        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMSTAT()
        m.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullTotalPhys / 1024**3
    return 0.0


def _gpus(os_name: str, arch: str) -> list[GPU]:
    out: list[GPU] = []
    if shutil.which("nvidia-smi"):
        for line in _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]).splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 2 and parts[1].replace(".", "").isdigit():
                out.append(GPU("nvidia", parts[0], float(parts[1]) / 1024))
    if os_name == "macos" and arch in ("arm64", "aarch64"):
        out.append(GPU("apple", "Apple Silicon (unified memory)", _ram_gb() * 0.66))
    if os_name == "linux" and not out and shutil.which("rocm-smi"):
        txt = _run(["rocm-smi", "--showmeminfo", "vram", "--csv"])
        m = re.search(r"(\d{9,})", txt)
        out.append(GPU("amd", "AMD (ROCm)", int(m.group(1)) / 1024**3 if m else 0.0))
    if os_name == "windows" and not out:
        txt = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"])
        for name in txt.splitlines():
            name = name.strip()
            if name:
                vendor = "amd" if "AMD" in name or "Radeon" in name else "intel" if "Intel" in name else "other"
                out.append(GPU(vendor, name, 0.0))
    return out


def _distro() -> str:
    try:
        text = open("/etc/os-release").read().lower()
    except OSError:
        return "other"
    like = re.search(r"^id_like=(.*)$", text, re.M)
    ids = (re.search(r"^id=(.*)$", text, re.M).group(1) if re.search(r"^id=", text, re.M) else "") + " " + \
        (like.group(1) if like else "")
    for key, fam in (("debian", "debian"), ("ubuntu", "debian"), ("pardus", "debian"), ("fedora", "fedora"),
                     ("rhel", "fedora"), ("centos", "fedora"), ("arch", "arch"), ("suse", "suse")):
        if key in ids:
            return fam
    return "other"


def detect() -> SystemInfo:
    os_name = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    arch = platform.machine().lower()
    home = os.path.expanduser("~")
    free = shutil.disk_usage(home).free / 1024**3
    info = SystemInfo(os_name, platform.release() if os_name != "macos" else platform.mac_ver()[0], arch,
                      _ram_gb(), free, _gpus(os_name, arch))
    if os_name == "linux":
        info.distro = _distro()
        info.wsl = "microsoft" in platform.release().lower()
    return info


def recommend_local_model(info: SystemInfo) -> tuple[str, str]:
    """(ollama model tag, reason). Coding-focused open models; tags change, the user can pick another."""
    g = info.best_gpu
    vram = g.vram_gb
    ram = info.ram_gb
    if vram >= 22 or (g.vendor == "apple" and ram >= 48):
        return "qwen2.5-coder:32b", "güçlü ekran kartı / strong GPU"
    if vram >= 10 or (g.vendor == "apple" and ram >= 24) or ram >= 48:
        return "qwen2.5-coder:14b", "orta-üst donanım / upper-mid hardware"
    if vram >= 5 or ram >= 16:
        return "qwen2.5-coder:7b", "orta donanım / mid-range hardware"
    if ram >= 8:
        return "qwen2.5-coder:3b", "8 GB RAM: küçük model / small model"
    return "qwen2.5-coder:1.5b", "düşük RAM: en küçük model / smallest model"
