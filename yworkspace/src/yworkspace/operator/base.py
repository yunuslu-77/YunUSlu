"""Shared logic for non-browser screens: numbered elements, labelled screenshots, human-like timing."""

from __future__ import annotations

import base64
import io
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import ToolError


@dataclass
class Element:
    n: int
    role: str
    name: str
    x: int
    y: int
    w: int
    h: int
    extra: str = ""

    def line(self) -> str:
        return f"[{self.n}] {self.role} \"{self.name}\" {self.extra}".rstrip()


def label_png(png: bytes, elements: list[Element]) -> bytes:
    """Draw numbered boxes on a screenshot (needs Pillow; returns the original image otherwise)."""
    try:
        from PIL import Image, ImageDraw, UnidentifiedImageError
    except ImportError:
        return png
    try:
        img = Image.open(io.BytesIO(png)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return png  # a broken capture must not break the screen tools
    d = ImageDraw.Draw(img)
    for e in elements:
        d.rectangle([e.x - e.w // 2, e.y - e.h // 2, e.x + e.w // 2, e.y + e.h // 2], outline=(232, 66, 10), width=2)
        d.rectangle([e.x - e.w // 2, e.y - e.h // 2 - 14, e.x - e.w // 2 + 8 * len(str(e.n)) + 6, e.y - e.h // 2],
                    fill=(232, 66, 10))
        d.text((e.x - e.w // 2 + 3, e.y - e.h // 2 - 13), str(e.n), fill=(255, 255, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


@dataclass
class ScreenBase:
    evidence_dir: Path
    persona: object
    elements: list[Element] = field(default_factory=list)
    steps: int = 0

    def __post_init__(self) -> None:
        Path(self.evidence_dir).mkdir(parents=True, exist_ok=True)

    # Subclasses implement these -------------------------------------------------
    def _tree(self) -> tuple[list[Element], str]:
        """(elements, description text such as app/window name)."""
        return [], ""

    def _screenshot(self) -> bytes | None:
        return None

    # Shared --------------------------------------------------------------------
    def think(self) -> None:
        lo, hi = getattr(self.persona, "think_time", (0.3, 1.0))
        time.sleep(random.uniform(lo, hi) * 0.25)

    def el(self, n: int) -> Element:
        for e in self.elements:
            if e.n == int(n):
                return e
        raise ToolError("no_element", f"No element [{n}] on the current screen.", "Call screen_view to refresh.")

    def view(self):
        self.elements, title = self._tree()
        lines = [title, f"Persona: {getattr(self.persona, 'title_tr', '')}", "", "Elements:"]
        lines += [e.line() for e in self.elements] or ["(no accessible elements; use the screenshot)"]
        images = []
        png = self._screenshot()
        if png:
            labelled = label_png(png, self.elements)
            self.steps += 1
            shot = Path(self.evidence_dir) / f"step-{self.steps:03d}.png"
            shot.write_bytes(labelled)
            lines.append(f"\nScreenshot saved: {shot.name}")
            images.append(base64.b64encode(labelled).decode())
        return "\n".join(lines), images

    def a11y(self) -> list[str]:
        issues = []
        for e in self.elements:
            if e.role in ("button", "image-button", "imagebutton") and not e.name.strip():
                issues.append(f"[{e.n}] {e.role} has no accessible name (content description)")
            if e.w and e.h and (e.w < 48 or e.h < 48) and e.role in ("button", "imagebutton", "checkbox"):
                issues.append(f"[{e.n}] small touch target {e.w}x{e.h} px (recommended ≥ 48 dp)")
        return issues

    def wait_for(self, text: str, timeout: int = 15) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            elements, title = self._tree()
            if any(text.lower() in (e.name or "").lower() for e in elements) or text.lower() in title.lower():
                self.elements = elements
                return True
            time.sleep(1)
        return False

    def select(self, n: int, option: str) -> None:
        self.click(n)
        time.sleep(0.5)
        self.elements, _ = self._tree()
        match = next((e for e in self.elements if e.name.strip().lower() == option.lower()), None)
        if match is None:
            raise ToolError("no_option", f"Option {option!r} not visible after opening the list.")
        self.click(match.n)

    def drag(self, n_from: int, n_to: int) -> None:
        a, b = self.el(n_from), self.el(n_to)
        self.swipe_xy(a.x, a.y, b.x, b.y, 800)

    def scroll(self, direction: str = "down", amount: int = 600) -> None:
        w, h = self.size()
        x = w // 2
        y1, y2 = (int(h * 0.7), int(h * 0.7) - amount) if direction == "down" else (int(h * 0.3), int(h * 0.3) + amount)
        self.swipe_xy(x, y1, x, max(1, y2), 400)

    def size(self) -> tuple[int, int]:
        return 1080, 2340

    def swipe_xy(self, x1: int, y1: int, x2: int, y2: int, ms: int) -> None:
        raise ToolError("unsupported", "Swiping is not supported on this screen.")

    def reload(self) -> None:
        pass

    def close(self) -> str:
        return "Screen closed."
