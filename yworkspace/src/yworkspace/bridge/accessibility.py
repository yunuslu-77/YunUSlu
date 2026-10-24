"""Reading desktop apps through the operating system's accessibility tree.

Backends: Windows UI Automation (package `uiautomation`), macOS AX API (`pyobjc`), Linux AT-SPI (`pyatspi`).
Each backend exposes the same small interface used by bridge.desktop.SystemDriver and operator tools.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator

MIN_REPLY_CHARS = 2


class Backend:
    def find_window(self, title: re.Pattern[str]): ...
    def is_foreground(self, window) -> bool: ...
    def activate(self, window) -> None: ...
    def rect(self, window) -> tuple[int, int, int, int]: ...
    def nodes(self, window) -> Iterator[tuple[str, str, object]]:  # (role, text, handle)
        ...
    def press(self, handle) -> None: ...

    def last_text_block(self, window) -> str:
        texts = [t for role, t, _ in self.nodes(window) if role in ("text", "document", "paragraph", "group")
                 and t and len(t.strip()) >= MIN_REPLY_CHARS]
        return texts[-1] if texts else ""

    def has_button(self, window, name: str) -> bool:
        return any(role == "button" and name.lower() in (t or "").lower() for role, t, _ in self.nodes(window))

    def press_last_button(self, window, name: str) -> bool:
        buttons = [h for role, t, h in self.nodes(window) if role == "button" and (t or "").strip().lower() == name.lower()]
        if not buttons:
            return False
        self.press(buttons[-1])
        return True

    def tree_text(self, window, limit: int = 400) -> list[tuple[int, str, str]]:
        """Numbered list of interactive/visible elements, used by the operator 'screen map'."""
        out = []
        for role, text, _h in self.nodes(window):
            if role in ("button", "edit", "text", "link", "checkbox", "menuitem", "tab", "listitem", "combobox"):
                out.append((len(out) + 1, role, (text or "").strip()[:120]))
                if len(out) >= limit:
                    break
        return out


class WindowsBackend(Backend):
    def __init__(self):
        import uiautomation as auto
        self.auto = auto

    def find_window(self, title):
        for w in self.auto.GetRootControl().GetChildren():
            if w.Name and title.search(w.Name):
                return w
        return None

    def is_foreground(self, window) -> bool:
        fg = self.auto.GetForegroundControl()
        return fg is not None and fg.NativeWindowHandle == window.NativeWindowHandle

    def activate(self, window) -> None:
        window.SetActive()
        window.SetFocus()

    def rect(self, window):
        r = window.BoundingRectangle
        return r.left, r.top, r.width(), r.height()

    _ROLE = {"ButtonControl": "button", "EditControl": "edit", "TextControl": "text", "DocumentControl": "document",
             "HyperlinkControl": "link", "CheckBoxControl": "checkbox", "MenuItemControl": "menuitem",
             "TabItemControl": "tab", "ListItemControl": "listitem", "ComboBoxControl": "combobox",
             "GroupControl": "group"}

    def nodes(self, window):
        for ctrl, _depth in self.auto.WalkControl(window, maxDepth=40):
            role = self._ROLE.get(ctrl.ControlTypeName)
            if role:
                text = ctrl.Name
                if role in ("document", "edit"):
                    try:
                        text = ctrl.GetValuePattern().Value or ctrl.Name
                    except Exception:
                        pass
                yield role, text, ctrl

    def press(self, handle) -> None:
        try:
            handle.GetInvokePattern().Invoke()
        except Exception:
            handle.Click()


class MacBackend(Backend):
    def __init__(self):
        import AppKit
        import ApplicationServices as AS
        self.AS, self.AppKit = AS, AppKit

    def _attr(self, el, name):
        err, val = self.AS.AXUIElementCopyAttributeValue(el, name, None)
        return val if err == 0 else None

    def find_window(self, title):
        for app in self.AppKit.NSWorkspace.sharedWorkspace().runningApplications():
            el = self.AS.AXUIElementCreateApplication(app.processIdentifier())
            for w in self._attr(el, "AXWindows") or []:
                name = self._attr(w, "AXTitle") or ""
                if title.search(name) or title.search(app.localizedName() or ""):
                    return (app, w)
        return None

    def is_foreground(self, window) -> bool:
        front = self.AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        return front is not None and front.processIdentifier() == window[0].processIdentifier()

    def activate(self, window) -> None:
        window[0].activateWithOptions_(self.AppKit.NSApplicationActivateIgnoringOtherApps)
        self.AS.AXUIElementPerformAction(window[1], "AXRaise")

    def rect(self, window):
        pos = self._attr(window[1], "AXPosition")
        size = self._attr(window[1], "AXSize")
        p = self.AS.AXValueGetValue(pos, self.AS.kAXValueCGPointType, None)[1]
        s = self.AS.AXValueGetValue(size, self.AS.kAXValueCGSizeType, None)[1]
        return int(p.x), int(p.y), int(s.width), int(s.height)

    _ROLE = {"AXButton": "button", "AXTextArea": "edit", "AXTextField": "edit", "AXStaticText": "text",
             "AXWebArea": "document", "AXLink": "link", "AXCheckBox": "checkbox", "AXMenuItem": "menuitem",
             "AXGroup": "group"}

    def nodes(self, window):
        stack = [window[1]]
        seen = 0
        while stack and seen < 20000:
            el = stack.pop(0)
            seen += 1
            role = self._ROLE.get(self._attr(el, "AXRole") or "")
            if role:
                text = self._attr(el, "AXValue") or self._attr(el, "AXTitle") or self._attr(el, "AXDescription") or ""
                yield role, str(text), el
            stack.extend(self._attr(el, "AXChildren") or [])

    def press(self, handle) -> None:
        self.AS.AXUIElementPerformAction(handle, "AXPress")


class LinuxBackend(Backend):
    def __init__(self):
        import pyatspi
        self.at = pyatspi

    def find_window(self, title):
        desktop = self.at.Registry.getDesktop(0)
        for app in desktop:
            for frame in app or []:
                if frame and (title.search(frame.name or "") or title.search(app.name or "")):
                    return frame
        return None

    def is_foreground(self, window) -> bool:
        return window.getState().contains(self.at.STATE_ACTIVE)

    def activate(self, window) -> None:
        try:
            window.queryComponent().grabFocus()
        except Exception:
            pass

    def rect(self, window):
        e = window.queryComponent().getExtents(self.at.DESKTOP_COORDS)
        return e.x, e.y, e.width, e.height

    _ROLE = {"push button": "button", "entry": "edit", "text": "text", "paragraph": "paragraph",
             "document web": "document", "document frame": "document", "link": "link", "check box": "checkbox",
             "menu item": "menuitem", "section": "group", "label": "text"}

    def nodes(self, window):
        stack = [window]
        seen = 0
        while stack and seen < 20000:
            el = stack.pop(0)
            seen += 1
            role = self._ROLE.get(el.getRoleName())
            if role:
                text = el.name or ""
                if role in ("text", "paragraph", "document", "edit"):
                    try:
                        t = el.queryText()
                        text = t.getText(0, t.characterCount) or text
                    except NotImplementedError:
                        pass
                yield role, text, el
            stack.extend(c for c in el if c is not None)

    def press(self, handle) -> None:
        handle.queryAction().doAction(0)


def for_platform() -> Backend:
    if sys.platform == "win32":
        return WindowsBackend()
    if sys.platform == "darwin":
        return MacBackend()
    return LinuxBackend()
