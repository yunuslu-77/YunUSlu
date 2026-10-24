"""Cross-platform clipboard using the operating system's own tools."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def _copy_cmd() -> list[str] | None:
    if sys.platform == "darwin":
        return ["pbcopy"]
    if sys.platform == "win32":
        return ["clip"]
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        return ["wl-copy"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard"]
    if shutil.which("xsel"):
        return ["xsel", "--clipboard", "--input"]
    return None


def _paste_cmd() -> list[str] | None:
    if sys.platform == "darwin":
        return ["pbpaste"]
    if sys.platform == "win32":
        return ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        return ["wl-paste", "--no-newline"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard", "-o"]
    if shutil.which("xsel"):
        return ["xsel", "--clipboard", "--output"]
    return None


def available() -> bool:
    return _copy_cmd() is not None and _paste_cmd() is not None


def copy(text: str) -> bool:
    cmd = _copy_cmd()
    if not cmd:
        return False
    data = text.encode("utf-16-le" if sys.platform == "win32" else "utf-8")
    return subprocess.run(cmd, input=data, timeout=10).returncode == 0


def paste() -> str | None:
    cmd = _paste_cmd()
    if not cmd:
        return None
    r = subprocess.run(cmd, capture_output=True, timeout=10)
    return r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else None
