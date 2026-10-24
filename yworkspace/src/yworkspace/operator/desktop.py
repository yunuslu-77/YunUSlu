"""Use a desktop application (Windows, macOS, Linux) like a person: accessibility tree for reading, real mouse
and keyboard for acting. Reuses the Desktop Bridge's accessibility backends. Needs `pip install "yworkspace[bridge]"`.
Runs on the user's real desktop only with their permission (screen_open asks through the approval system)."""

from __future__ import annotations

import io
import re
import sys
import time

from ..core.errors import ToolError
from .base import Element, ScreenBase

ROLE_NAMES = {"button", "edit", "text", "link", "checkbox", "menuitem", "tab", "listitem", "combobox", "document"}


class DesktopScreen(ScreenBase):
    def __init__(self, evidence_dir, persona, backend=None, pyautogui=None):
        super().__init__(evidence_dir, persona)
        try:
            if backend is None:
                from ..bridge.accessibility import for_platform
                backend = for_platform()
            if pyautogui is None:
                import pyautogui as pg
                pyautogui = pg
        except ImportError as e:
            raise ToolError("no_desktop", f"Desktop control is not installed: {e}",
                            'pip install "yworkspace[bridge]" (macOS also needs the Accessibility permission).') from e
        self.a11y_backend = backend
        self.pg = pyautogui
        self.window = None
        self._handles: dict[int, object] = {}

    def open(self, target: str):
        self.window = self.a11y_backend.find_window(re.compile(target, re.I))
        if self.window is None:
            raise ToolError("no_window", f"No window matches {target!r}.", "Start the app first, then use its title.")
        self.a11y_backend.activate(self.window)
        time.sleep(0.5)
        return self.view()

    def _tree(self):
        x0, y0, w, h = self.a11y_backend.rect(self.window)
        self._origin = (x0, y0)
        out: list[Element] = []
        self._handles = {}
        for role, text, handle in self.a11y_backend.nodes(self.window):
            if role not in ROLE_NAMES:
                continue
            try:
                ex, ey, ew, eh = self.a11y_backend.rect((None, handle)) if sys.platform == "darwin" else \
                    self._node_rect(handle)
            except Exception:
                continue
            if ew <= 1 or eh <= 1:
                continue
            n = len(out) + 1  # coordinates relative to the window, like the screenshot
            out.append(Element(n, role, (text or "").strip()[:80], ex - x0 + ew // 2, ey - y0 + eh // 2, ew, eh))
            self._handles[n] = handle
            if len(out) >= 300:
                break
        return out, f"Window: {target_title(self.window)} ({w}x{h} at {x0},{y0})"

    def _node_rect(self, handle):
        r = getattr(handle, "BoundingRectangle", None)
        if r is not None:  # Windows UIA
            return r.left, r.top, r.width(), r.height()
        comp = handle.queryComponent()  # Linux AT-SPI
        import pyatspi
        e = comp.getExtents(pyatspi.DESKTOP_COORDS)
        return e.x, e.y, e.width, e.height

    def _screenshot(self):
        x, y, w, h = self.a11y_backend.rect(self.window)
        img = self.pg.screenshot(region=(x, y, w, h))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def _abs(self, x: int, y: int) -> tuple[int, int]:
        ox, oy = getattr(self, "_origin", (0, 0))
        return ox + x, oy + y

    def size(self):
        _x, _y, w, h = self.a11y_backend.rect(self.window)
        return w, h

    def click(self, n: int, double: bool = False) -> None:
        e = self.el(n)
        self.think()
        self.pg.moveTo(*self._abs(e.x, e.y), duration=0.3)
        if double or getattr(self.persona, "double_clicks", False):
            self.pg.doubleClick()
        else:
            self.pg.click()

    def type(self, n: int, text: str, clear: bool = True, submit: bool = False) -> None:
        self.click(n)
        mod = "command" if sys.platform == "darwin" else "ctrl"
        if clear:
            self.pg.hotkey(mod, "a")
            self.pg.press("delete")
        lo, hi = getattr(self.persona, "typing_delay", (40, 110))
        if text.isascii():
            self.pg.write(text, interval=(lo + hi) / 2000 * 0.3)
        else:  # pyautogui cannot type non-ASCII: paste it instead
            from ..core import clipboard
            saved = clipboard.paste()
            clipboard.copy(text)
            self.pg.hotkey(mod, "v")
            if saved is not None:
                clipboard.copy(saved)
        if submit:
            self.pg.press("enter")

    def key(self, keys: str) -> None:
        self.pg.hotkey(*[k.strip().lower() for k in keys.split("+")])

    def swipe_xy(self, x1, y1, x2, y2, ms):
        self.pg.moveTo(*self._abs(x1, y1))
        self.pg.dragTo(*self._abs(x2, y2), duration=ms / 1000)

    def scroll(self, direction: str = "down", amount: int = 600) -> None:
        self.pg.scroll(-amount // 100 if direction == "down" else amount // 100)

    def back(self) -> None:
        self.pg.hotkey("alt", "left")


def target_title(window) -> str:
    for attr in ("Name", "name"):
        v = getattr(window, attr, None)
        if isinstance(v, str):
            return v
    if isinstance(window, tuple):
        return str(window[0].localizedName())
    return "window"
