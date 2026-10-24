"""iOS (and alternatively Android) through an Appium server, using the W3C WebDriver protocol directly.
iOS needs a Mac with Xcode and Appium's XCUITest driver: `appium driver install xcuitest`, then `appium`."""

from __future__ import annotations

import base64
import xml.etree.ElementTree as ET

import httpx

from ..core.errors import ToolError
from .base import Element, ScreenBase


class AppiumScreen(ScreenBase):
    def __init__(self, evidence_dir, persona, server: str = "http://127.0.0.1:4723", client=None):
        super().__init__(evidence_dir, persona)
        self.server = server.rstrip("/")
        self.http = client or httpx.Client(timeout=120)
        self.sid = None
        self._size = (390, 844)

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.server}/session/{self.sid}{path}" if self.sid and not path.startswith("/session") else \
            f"{self.server}{path}"
        try:
            r = self.http.request(method, url, json=body)
        except httpx.HTTPError as e:
            raise ToolError("no_appium", f"Appium server not reachable at {self.server}: {e}",
                            "On the Mac: npm i -g appium && appium driver install xcuitest && appium") from e
        data = r.json()
        if r.status_code >= 400:
            raise ToolError("appium_error", str(data.get("value", data))[:800])
        return data.get("value", data)

    def open(self, target: str):
        caps = {"platformName": "iOS", "appium:automationName": "XCUITest", "appium:newCommandTimeout": 600}
        caps["appium:app" if target.endswith((".app", ".ipa", ".zip")) else "appium:bundleId"] = target
        value = self._call("POST", "/session", {"capabilities": {"alwaysMatch": caps}})
        self.sid = value.get("sessionId") or value.get("session_id")
        rect = self._call("GET", "/window/rect")
        self._size = (int(rect.get("width", 390)), int(rect.get("height", 844)))
        return self.view()

    def _tree(self):
        xml = self._call("GET", "/source")
        root = ET.fromstring(xml)
        out: list[Element] = []
        for node in root.iter():
            a = node.attrib
            if a.get("visible") == "false" or "x" not in a:
                continue
            t = node.tag.replace("XCUIElementType", "").lower()
            role = {"button": "button", "textfield": "edit", "securetextfield": "edit", "switch": "switch",
                    "statictext": "text", "link": "link", "cell": "listitem", "image": "image"}.get(t)
            name = a.get("label") or a.get("name") or a.get("value") or ""
            if role is None or (role in ("text", "image") and not name):
                continue
            x, y, w, h = (int(float(a.get(k, 0))) for k in ("x", "y", "width", "height"))
            if w < 2 or h < 2:
                continue
            out.append(Element(len(out) + 1, role, name[:80], x + w // 2, y + h // 2, w, h,
                               "password" if t == "securetextfield" else ""))
        return out, f"iOS app (session {self.sid})"

    def _screenshot(self):
        return base64.b64decode(self._call("GET", "/screenshot"))

    def size(self):
        return self._size

    def _pointer(self, actions: list[dict]) -> None:
        self._call("POST", "/actions", {"actions": [{"type": "pointer", "id": "finger1",
                                                     "parameters": {"pointerType": "touch"}, "actions": actions}]})

    def click(self, n: int, double: bool = False) -> None:
        e = self.el(n)
        self.think()
        seq = [{"type": "pointerMove", "duration": 0, "x": e.x, "y": e.y}, {"type": "pointerDown", "button": 0},
               {"type": "pause", "duration": 80}, {"type": "pointerUp", "button": 0}]
        self._pointer(seq * (2 if double else 1))

    def type(self, n: int, text: str, clear: bool = True, submit: bool = False) -> None:
        self.click(n)
        active = self._call("GET", "/element/active")
        eid = next(iter(active.values()))
        if clear:
            self._call("POST", f"/element/{eid}/clear", {})
        self._call("POST", f"/element/{eid}/value", {"text": text + ("\n" if submit else "")})

    def key(self, keys: str) -> None:
        self._call("POST", "/actions", {"actions": [{"type": "key", "id": "kb", "actions": [
            {"type": "keyDown", "value": keys}, {"type": "keyUp", "value": keys}]}]})

    def swipe_xy(self, x1, y1, x2, y2, ms):
        self._pointer([{"type": "pointerMove", "duration": 0, "x": x1, "y": y1}, {"type": "pointerDown", "button": 0},
                       {"type": "pointerMove", "duration": ms, "x": x2, "y": y2}, {"type": "pointerUp", "button": 0}])

    def back(self) -> None:
        w, h = self._size
        self.swipe_xy(2, h // 2, w // 2, h // 2, 300)  # iOS back gesture

    def close(self) -> str:
        if self.sid:
            try:
                self._call("DELETE", "")
            finally:
                self.sid = None
        return "iOS session ended."
