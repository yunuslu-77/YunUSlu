"""Desktop Bridge: drive a desktop chat app (no MCP support) like a person, through clipboard + keyboard.

Architecture:
  BridgeRunner (OS independent, tested)  ── uses ──>  Driver (OS specific)
  Driver = window control + keyboard + reading the last reply (accessibility tree or copy button).

Safety (always on): clipboard is restored, the target window is verified before every paste, an emergency
stop hotkey and mouse-to-corner stop the bridge, and user activity pauses it.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..protocol.session import TextSession

PROFILE_DIR = Path(__file__).parent / "profiles"
EXTRA_PROFILE_DIRS: list[Path] = []  # plugins add app profiles here


@dataclass
class AppProfile:
    name: str
    window_title: str  # regex
    send_keys: list[str] = field(default_factory=lambda: ["enter"])
    focus_input: str = "click_bottom"  # click_bottom | shortcut:<keys> | none
    reply_via: str = "accessibility"  # accessibility | copy_button | screen_ocr
    copy_button_name: str = "Copy"  # accessible name of the per-message copy button
    busy_names: list[str] = field(default_factory=lambda: ["Stop", "Durdur"])  # buttons visible while generating
    max_chars: int = 20000
    settle_seconds: float = 3.0
    notes: str = ""

    @classmethod
    def load(cls, name: str) -> AppProfile:
        dirs = [*EXTRA_PROFILE_DIRS, PROFILE_DIR]
        p = next((d / f"{name}.json" for d in dirs if (d / f"{name}.json").exists()), PROFILE_DIR / f"{name}.json")
        if not p.exists():
            known = ", ".join(x.stem for d in dirs for x in d.glob("*.json"))
            raise FileNotFoundError(f"No desktop app profile {name!r}. Known: {known}")
        return cls(**json.loads(p.read_text("utf-8")))


class Driver(Protocol):
    def find_window(self, title_regex: str) -> object | None: ...
    def is_foreground(self, window: object) -> bool: ...
    def activate(self, window: object) -> None: ...
    def focus_input(self, window: object, how: str) -> None: ...
    def paste(self, text: str) -> None: ...
    def press(self, keys: list[str]) -> None: ...
    def last_reply(self, window: object, profile: AppProfile) -> str: ...
    def is_busy(self, window: object, profile: AppProfile) -> bool: ...
    def clipboard_get(self) -> str | None: ...
    def clipboard_set(self, text: str) -> None: ...
    def user_active_since(self, t: float) -> bool: ...
    def stop_requested(self) -> bool: ...


class BridgeStopped(Exception):
    pass


@dataclass
class BridgeRunner:
    driver: Driver
    profile: AppProfile
    session: TextSession
    reply_timeout: float = 900.0
    poll: float = 1.0
    log: list[str] = field(default_factory=list)

    def _guard(self, window) -> None:
        if self.driver.stop_requested():
            raise BridgeStopped("emergency stop")
        if not self.driver.is_foreground(window):
            self.driver.activate(window)
            time.sleep(0.5)
            if not self.driver.is_foreground(window):
                raise BridgeStopped("target window is not in front; refusing to paste")

    def _send(self, window, text: str) -> None:
        self._guard(window)
        self.driver.focus_input(window, self.profile.focus_input)
        self._guard(window)
        self.driver.clipboard_set(text)
        self.driver.paste(text)
        self.driver.press(self.profile.send_keys)
        self.log.append(f"sent {len(text)} chars")

    def _count(self, window) -> int | None:
        fn = getattr(self.driver, "reply_count", None)
        return fn(window, self.profile) if fn else None

    def _wait_reply(self, window, previous: str, count_before: int | None = None) -> str:
        """Wait for a NEW reply: the reply count grows (if the driver can count) or the text changes."""
        start = time.time()
        last, stable_since = previous, time.time()
        while time.time() - start < self.reply_timeout:
            time.sleep(self.poll)
            if self.driver.stop_requested():
                raise BridgeStopped("emergency stop")
            if self.driver.user_active_since(stable_since):
                self.log.append("user activity detected: waiting")
                stable_since = time.time()
                continue
            text = self.driver.last_reply(window, self.profile)
            if text != last:
                last, stable_since = text, time.time()
                continue
            count = self._count(window)
            is_new = (count > count_before) if (count is not None and count_before is not None) else text != previous
            if text and is_new and not self.driver.is_busy(window, self.profile) and \
                    time.time() - stable_since >= self.profile.settle_seconds:
                return text
        raise BridgeStopped("reply timed out")

    def deliver(self, window, parts: list[str]) -> str:
        reply = self.driver.last_reply(window, self.profile)
        for part in parts:
            before, count = reply, self._count(window)
            self._send(window, part)
            reply = self._wait_reply(window, before, count)
        return reply

    def run(self, max_turns: int = 200) -> str:
        window = self.driver.find_window(self.profile.window_title)
        if window is None:
            raise BridgeStopped(f"no window matching {self.profile.window_title!r}; open the app first")
        saved = self.driver.clipboard_get()
        self.session.max_message_chars = self.profile.max_chars
        try:
            parts = self.session.split(self.session.opening())
            for _ in range(max_turns):
                reply = self.deliver(window, parts)
                res = self.session.handle(reply)
                self.log.append(f"turn {self.session.turns}: {res.calls} calls, {res.errors} errors")
                if res.done:
                    return "done"
                parts = self.session.split(res.reply_to_ai)
            return "max turns"
        finally:
            if saved is not None:
                self.driver.clipboard_set(saved)


# ---------------------------------------------------------------------- real OS driver
class SystemDriver:
    """Real driver. Needs: pyautogui + pynput (all OS); uiautomation (Windows) or pyobjc (macOS) or pyatspi
    (Linux) for reading replies. Install with: pip install "yworkspace[bridge]"."""

    def __init__(self, stop_hotkey: str = "<ctrl>+<shift>+q"):
        import pyautogui  # noqa: F401  (imported to fail early with a clear message)
        from pynput import keyboard, mouse

        self._stop = False
        self._last_input = 0.0
        self._synthetic_until = 0.0
        pyautogui.FAILSAFE = True  # mouse to a screen corner raises FailSafeException
        self._hotkey = keyboard.GlobalHotKeys({stop_hotkey: self._request_stop})
        self._hotkey.start()

        def activity(*_a):
            if time.time() > self._synthetic_until:
                self._last_input = time.time()
        self._mouse = mouse.Listener(on_move=activity, on_click=activity)
        self._keys = keyboard.Listener(on_press=activity)
        self._mouse.start()
        self._keys.start()
        from . import accessibility
        self._a11y = accessibility.for_platform()

    def _request_stop(self) -> None:
        self._stop = True

    def stop_requested(self) -> bool:
        return self._stop

    def user_active_since(self, t: float) -> bool:
        return self._last_input > t

    def _synthetic(self, seconds: float = 1.5) -> None:
        self._synthetic_until = time.time() + seconds

    def find_window(self, title_regex: str):
        return self._a11y.find_window(re.compile(title_regex))

    def is_foreground(self, window) -> bool:
        return self._a11y.is_foreground(window)

    def activate(self, window) -> None:
        self._synthetic()
        self._a11y.activate(window)

    def focus_input(self, window, how: str) -> None:
        import pyautogui
        self._synthetic()
        if how == "click_bottom":
            x, y, w, h = self._a11y.rect(window)
            pyautogui.click(x + w // 2, y + h - 60)
        elif how.startswith("shortcut:"):
            pyautogui.hotkey(*how.split(":", 1)[1].split("+"))

    def paste(self, text: str) -> None:
        import sys

        import pyautogui
        self._synthetic()
        pyautogui.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
        time.sleep(0.3)

    def press(self, keys: list[str]) -> None:
        import pyautogui
        self._synthetic()
        pyautogui.hotkey(*keys)

    def last_reply(self, window, profile: AppProfile) -> str:
        if profile.reply_via == "copy_button":
            before = self.clipboard_get()
            self._synthetic()
            if self._a11y.press_last_button(window, profile.copy_button_name):
                time.sleep(0.4)
                text = self.clipboard_get() or ""
                if before is not None:
                    self.clipboard_set(before)
                return text
        if profile.reply_via == "screen_ocr":
            from . import ocr
            return ocr.read_window(self._a11y.rect(window))
        return self._a11y.last_text_block(window)

    def reply_count(self, window, profile: AppProfile) -> int:
        n = sum(1 for role, t, _ in self._a11y.nodes(window)
                if role == "button" and (t or "").strip().lower() == profile.copy_button_name.lower())
        return n

    def is_busy(self, window, profile: AppProfile) -> bool:
        return any(self._a11y.has_button(window, n) for n in profile.busy_names)

    def clipboard_get(self) -> str | None:
        from ..core import clipboard
        return clipboard.paste()

    def clipboard_set(self, text: str) -> None:
        from ..core import clipboard
        clipboard.copy(text)
