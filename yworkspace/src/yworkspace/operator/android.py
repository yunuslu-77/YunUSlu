"""Use an Android app like a person through ADB: real taps, swipes, typing, back button, permissions.

Needs adb and a running emulator or a USB-connected device. The emulator needs hardware virtualization
(KVM on Linux). Without a device, nothing is faked: the tool says what is missing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile

from ..core.errors import ToolError
from .base import Element, ScreenBase

BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
ROLE = {"android.widget.Button": "button", "android.widget.ImageButton": "imagebutton",
        "android.widget.EditText": "edit", "android.widget.CheckBox": "checkbox", "android.widget.Switch": "switch",
        "android.widget.RadioButton": "radio", "android.widget.TextView": "text", "android.widget.ImageView": "image",
        "android.widget.Spinner": "dropdown"}


def parse_hierarchy(xml_text: str) -> list[Element]:
    """Interactive and text nodes from `uiautomator dump`, numbered in reading order."""
    start = xml_text.find("<?xml")
    if start == -1:
        start = xml_text.find("<hierarchy")
    root = ET.fromstring(xml_text[start:xml_text.rfind(">") + 1])
    out: list[Element] = []
    for node in root.iter("node"):
        a = node.attrib
        m = BOUNDS.match(a.get("bounds", ""))
        if not m:
            continue
        x1, y1, x2, y2 = map(int, m.groups())
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        cls = a.get("class", "")
        interactive = a.get("clickable") == "true" or a.get("checkable") == "true" or cls.endswith("EditText") \
            or a.get("scrollable") == "true"
        text = a.get("text") or a.get("content-desc") or ""
        if not interactive and not text:
            continue
        role = ROLE.get(cls, "view" if interactive else "text")
        if a.get("clickable") == "true" and role in ("text", "view", "image"):
            role = "button" if role != "image" else "imagebutton"
        extra = []
        if a.get("checked") == "true":
            extra.append("checked")
        if a.get("enabled") == "false":
            extra.append("disabled")
        if a.get("password") == "true":
            extra.append("password")
        rid = a.get("resource-id", "")
        if rid:
            extra.append("id=" + rid.split("/")[-1])
        out.append(Element(len(out) + 1, role, text.strip()[:80], (x1 + x2) // 2, (y1 + y2) // 2, x2 - x1, y2 - y1,
                           " ".join(extra)))
    return out


def adb_text(s: str) -> str:
    """Escape for `adb shell input text` (ASCII only; spaces become %s)."""
    out = []
    for ch in s:
        if ch == " ":
            out.append("%s")
        elif ch in "&|<>;()$`\\\"'*?[]#~":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


class AndroidScreen(ScreenBase):
    def __init__(self, evidence_dir, persona, adb: str = "adb", serial: str | None = None, runner=None):
        super().__init__(evidence_dir, persona)
        self.adb = adb
        self.serial = serial
        self.run = runner or self._run
        self.package = ""
        self._size: tuple[int, int] | None = None

    def _run(self, args: list[str], binary: bool = False, timeout: int = 120):
        if not shutil.which(self.adb):
            raise ToolError("no_adb", "adb (Android platform tools) is not installed.",
                            "Install Android platform-tools, start an emulator (needs KVM) or connect a phone with "
                            "USB debugging enabled.")
        cmd = [self.adb] + (["-s", self.serial] if self.serial else []) + args
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if r.returncode != 0:
            raise ToolError("adb_failed", (r.stderr or r.stdout).decode(errors="replace")[-800:])
        return r.stdout if binary else r.stdout.decode(errors="replace")

    def open(self, target: str):
        devices = self.run(["devices"])
        if not re.search(r"\tdevice\b", devices):
            raise ToolError("no_device", "No Android device or emulator is connected.",
                            "Start an emulator (emulator -avd <name>) or plug in a phone with USB debugging.")
        if target.endswith(".apk"):
            self.run(["install", "-r", "-g", target], timeout=600)
            self.package = self._package_of(target)
        else:
            self.package = target
        self.run(["shell", "monkey", "-p", self.package, "-c", "android.intent.category.LAUNCHER", "1"])
        time.sleep(2)
        return self.view()

    @staticmethod
    def _package_of(apk: str) -> str:
        if shutil.which("aapt"):
            out = subprocess.run(["aapt", "dump", "badging", apk], capture_output=True, text=True).stdout
            m = re.search(r"package: name='([^']+)'", out)
            if m:
                return m.group(1)
        with zipfile.ZipFile(apk) as z:  # binary manifest: fall back to the first package-like string
            raw = z.read("AndroidManifest.xml").decode("utf-16-le", errors="ignore")
        m = re.search(r"([a-z][a-z0-9_]*(?:\.[a-z0-9_]+){1,})", raw)
        if not m:
            raise ToolError("no_package", "Could not read the package name; pass it as target instead of the APK.")
        return m.group(1)

    def _tree(self):
        xml = self.run(["exec-out", "uiautomator", "dump", "/dev/tty"])
        activity = ""
        try:
            act = self.run(["shell", "dumpsys", "activity", "activities"])
            m = re.search(r"mResumedActivity: .* ([\w.]+/[\w.$]+)", act)
            activity = m.group(1) if m else ""
        except ToolError:
            pass
        return parse_hierarchy(xml), f"Android app: {self.package} {activity}".strip()

    def _screenshot(self):
        return self.run(["exec-out", "screencap", "-p"], binary=True)

    def size(self):
        if self._size is None:
            m = re.search(r"(\d+)x(\d+)", self.run(["shell", "wm", "size"]))
            self._size = (int(m.group(1)), int(m.group(2))) if m else (1080, 2340)
        return self._size

    def click(self, n: int, double: bool = False) -> None:
        e = self.el(n)
        self.think()
        for _ in range(2 if double or getattr(self.persona, "double_clicks", False) else 1):
            self.run(["shell", "input", "tap", str(e.x), str(e.y)])

    def long_press(self, n: int) -> None:
        e = self.el(n)
        self.swipe_xy(e.x, e.y, e.x, e.y, 900)

    def type(self, n: int, text: str, clear: bool = True, submit: bool = False) -> None:
        self.click(n)
        if clear:  # works on every Android version: go to the end, delete backwards
            self.run(["shell", "input", "keyevent", "KEYCODE_MOVE_END"])
            self.run(["shell", "input", "keyevent"] + ["KEYCODE_DEL"] * 60)
        if text.isascii():
            for chunk in re.findall(r".{1,20}", text, re.S):
                self.run(["shell", "input", "text", adb_text(chunk)])
                self.think()
        else:  # non-ASCII (ç, ğ, ı, ö, ş, ü): needs the ADB Keyboard IME
            self.run(["shell", "am", "broadcast", "-a", "ADB_INPUT_TEXT", "--es", "msg", text])
        if submit:
            self.run(["shell", "input", "keyevent", "KEYCODE_ENTER"])

    def key(self, keys: str) -> None:
        code = {"enter": "KEYCODE_ENTER", "back": "KEYCODE_BACK", "home": "KEYCODE_HOME", "tab": "KEYCODE_TAB",
                "escape": "KEYCODE_ESCAPE", "delete": "KEYCODE_DEL"}.get(keys.lower(), keys)
        self.run(["shell", "input", "keyevent", code])

    def swipe_xy(self, x1, y1, x2, y2, ms):
        self.run(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms)])

    def back(self) -> None:
        self.run(["shell", "input", "keyevent", "KEYCODE_BACK"])

    def reload(self) -> None:
        if self.package:
            self.run(["shell", "am", "force-stop", self.package])
            self.run(["shell", "monkey", "-p", self.package, "-c", "android.intent.category.LAUNCHER", "1"])

    def device(self, action: str) -> str:
        actions = {
            "rotate": ["shell", "settings", "put", "system", "user_rotation", "1"],
            "portrait": ["shell", "settings", "put", "system", "user_rotation", "0"],
            "dark_mode": ["shell", "cmd", "uimode", "night", "yes"],
            "light_mode": ["shell", "cmd", "uimode", "night", "no"],
            "offline": ["shell", "cmd", "connectivity", "airplane-mode", "enable"],
            "online": ["shell", "cmd", "connectivity", "airplane-mode", "disable"],
            "home": ["shell", "input", "keyevent", "KEYCODE_HOME"],
        }
        if action not in actions:
            raise ToolError("bad_action", f"Unknown device action {action}.", f"Use: {', '.join(actions)}")
        self.run(actions[action])
        return f"Device: {action}"

    def close(self) -> str:
        return "Android session ended (the app keeps running on the device)."
