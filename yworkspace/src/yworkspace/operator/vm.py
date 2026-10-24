"""Use an operating system image (ISO / disk image) in a QEMU virtual machine: see the screen, press keys,
move the mouse. Lets the AI walk through an installer it built, like a person would.

Needs qemu-system-x86_64 (and ideally KVM). The screen has no accessibility tree: vision models read the
screenshot; text-only models get OCR text when Tesseract is installed.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tempfile
import time
import zlib
from pathlib import Path

from ..core.errors import ToolError
from .base import Element, ScreenBase

QKEYS = {"enter": "ret", "return": "ret", "tab": "tab", "escape": "esc", "esc": "esc", "space": "spc",
         "backspace": "backspace", "delete": "delete", "up": "up", "down": "down", "left": "left", "right": "right",
         "control": "ctrl", "ctrl": "ctrl", "alt": "alt", "shift": "shift", "f2": "f2", "f10": "f10", "f12": "f12"}


def ppm_to_png(ppm: bytes) -> bytes:
    """Convert QEMU's PPM (P6) screendump to PNG using only the standard library."""
    parts = ppm.split(maxsplit=4)
    if parts[0] != b"P6":
        raise ValueError("not a P6 PPM")
    w, h, maxval = int(parts[1]), int(parts[2]), int(parts[3])
    if maxval != 255:
        raise ValueError("unsupported PPM depth")
    pixels = parts[4][: w * h * 3]
    raw = b"".join(b"\x00" + pixels[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return len(data).to_bytes(4, "big") + kind + data + zlib.crc32(kind + data).to_bytes(4, "big")
    ihdr = w.to_bytes(4, "big") + h.to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def key_combo(keys: str) -> list[dict]:
    """'Control+Alt+Delete' → QMP key list; single characters map to themselves."""
    out = []
    for k in keys.split("+"):
        k = k.strip()
        name = QKEYS.get(k.lower(), k.lower() if len(k) == 1 else k.lower())
        out.append({"type": "qcode", "data": name})
    return out


class Qmp:
    def __init__(self, path: str):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)
        self.f = self.sock.makefile("rwb")
        self._read()
        self.cmd("qmp_capabilities")

    def _read(self) -> dict:
        while True:
            line = self.f.readline()
            if not line:
                raise ToolError("qmp_closed", "The virtual machine stopped.")
            msg = json.loads(line)
            if "event" not in msg:
                return msg

    def cmd(self, name: str, **args) -> dict:
        self.f.write(json.dumps({"execute": name, "arguments": args} if args else {"execute": name}).encode() + b"\n")
        self.f.flush()
        resp = self._read()
        if "error" in resp:
            raise ToolError("qmp_error", str(resp["error"]))
        return resp.get("return", {})


class VmScreen(ScreenBase):
    def __init__(self, evidence_dir, persona, memory_mb: int = 2048):
        super().__init__(evidence_dir, persona)
        self.proc = None
        self.qmp: Qmp | None = None
        self.memory = memory_mb
        self.tmp = Path(tempfile.mkdtemp(prefix="yw-vm-"))
        self._size = (1024, 768)

    def open(self, target: str):
        exe = shutil.which("qemu-system-x86_64")
        if not exe:
            raise ToolError("no_qemu", "QEMU is not installed.", "Install qemu-system-x86 (and enable KVM for speed).")
        sock = str(self.tmp / "qmp.sock")
        disk = self.tmp / "disk.qcow2"
        args = [exe, "-m", str(self.memory), "-display", "none", "-vga", "std", "-qmp", f"unix:{sock},server,nowait",
                "-usb", "-device", "usb-tablet"]
        if Path("/dev/kvm").exists():
            args += ["-enable-kvm", "-cpu", "host"]
        if target.endswith(".iso"):
            if shutil.which("qemu-img"):
                subprocess.run(["qemu-img", "create", "-f", "qcow2", str(disk), "20G"], capture_output=True)
                args += ["-drive", f"file={disk},if=virtio"]
            args += ["-cdrom", target, "-boot", "d"]
        else:
            args += ["-drive", f"file={target},if=virtio,snapshot=on"]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(50):
            if Path(sock).exists():
                break
            time.sleep(0.2)
        self.qmp = Qmp(sock)
        time.sleep(5)
        return self.view()

    def _tree(self):
        text = self._ocr()
        return [], "Virtual machine screen" + (f"\nText on screen (OCR):\n{text}" if text else "")

    def _screenshot(self):
        if self.qmp is None:
            return None
        ppm = self.tmp / "screen.ppm"
        self.qmp.cmd("screendump", filename=str(ppm))
        png = ppm_to_png(ppm.read_bytes())
        w = int.from_bytes(png[16:20], "big")
        h = int.from_bytes(png[20:24], "big")
        self._size = (w, h)
        return png

    def _ocr(self) -> str:
        if not shutil.which("tesseract") or self.qmp is None:
            return ""
        png = self._screenshot()
        p = self.tmp / "ocr.png"
        p.write_bytes(png)
        r = subprocess.run(["tesseract", str(p), "-", "-l", "eng+tur"], capture_output=True, text=True)
        return r.stdout.strip()[:3000]

    def size(self):
        return self._size

    def click_xy(self, x: int, y: int) -> None:
        w, h = self._size
        ax, ay = int(x * 32767 / max(1, w - 1)), int(y * 32767 / max(1, h - 1))
        self.qmp.cmd("input-send-event", events=[{"type": "abs", "data": {"axis": "x", "value": ax}},
                                                 {"type": "abs", "data": {"axis": "y", "value": ay}}])
        for down in (True, False):
            self.qmp.cmd("input-send-event", events=[{"type": "btn", "data": {"down": down, "button": "left"}}])
            time.sleep(0.08)

    def click(self, n: int, double: bool = False) -> None:
        e = self.el(n)
        self.click_xy(e.x, e.y)

    def type(self, n: int, text: str, clear: bool = True, submit: bool = False) -> None:
        for ch in text:
            name = {" ": "spc", "\n": "ret", ".": "dot", ",": "comma", "-": "minus", "/": "slash"}.get(ch, ch.lower())
            keys = [{"type": "qcode", "data": name}]
            if ch.isupper():
                keys.insert(0, {"type": "qcode", "data": "shift"})
            self.qmp.cmd("send-key", keys=keys)
            time.sleep(0.05)
        if submit:
            self.key("Enter")

    def key(self, keys: str) -> None:
        self.qmp.cmd("send-key", keys=key_combo(keys))

    def swipe_xy(self, x1, y1, x2, y2, ms):
        self.click_xy(x1, y1)

    def back(self) -> None:
        self.key("Escape")

    def close(self) -> str:
        if self.proc is not None:
            try:
                if self.qmp:
                    self.qmp.cmd("quit")
            except Exception:
                pass
            self.proc.terminate()
            self.proc = None
        shutil.rmtree(self.tmp, ignore_errors=True)
        return "Virtual machine stopped."


def element_at(x: int, y: int, n: int = 1) -> Element:
    """Vision models may click by coordinates: make a one-off element for a point."""
    return Element(n, "point", f"{x},{y}", x, y, 2, 2)
