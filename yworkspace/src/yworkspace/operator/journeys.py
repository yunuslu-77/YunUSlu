"""User journeys from the spec, their results, and the done gate that requires them."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

UI_MARKERS = ("react", "next", "vue", "svelte", "angular", "vite", "flutter", "jetpack", "compose", "solid-js")


@dataclass
class JourneyResult:
    name: str
    passed: bool
    persona: str = ""
    notes: str = ""
    evidence: list[str] = field(default_factory=list)
    time: float = field(default_factory=time.time)


def parse_journeys(spec: str) -> list[str]:
    """Journeys from the '# User journeys' section: its '##' sub-headings if present, otherwise its top-level
    list items (indented items are steps, not journeys)."""
    m = re.search(r"^#+\s*(user journeys|kullanıcı yolculukları)\s*$(.*?)(?=^#\s|\Z)", spec, re.I | re.M | re.S)
    if not m:
        return []
    lines = m.group(2).splitlines()
    heads = [re.match(r"^#{2,}\s+(.*)", ln.strip()) for ln in lines]
    if any(heads):
        return [h.group(1).strip() for h in heads if h]
    return [it.group(1).strip() for ln in lines if (it := re.match(r"^(?:[-*]|\d+[.)])\s+(.*)", ln))]


def has_ui(root: Path) -> bool:
    root = Path(root)
    pkg = root / "package.json"
    if pkg.exists() and any(k in pkg.read_text("utf-8").lower() for k in UI_MARKERS):
        return True
    if (root / "pubspec.yaml").exists() or (root / "app" / "src" / "main" / "AndroidManifest.xml").exists():
        return True
    for p in root.rglob("*.html"):
        if ".yw" not in p.parts and "node_modules" not in p.parts:
            return True
    for p in root.rglob("templates"):
        if p.is_dir() and ".yw" not in p.parts:
            return True
    return False


class JourneyStore:
    def __init__(self, root: Path):
        self.path = Path(root) / ".yw" / "journeys.json"

    def all(self) -> list[JourneyResult]:
        if not self.path.exists():
            return []
        return [JourneyResult(**r) for r in json.loads(self.path.read_text("utf-8"))]

    def add(self, result: JourneyResult) -> None:
        items = [r for r in self.all() if not (r.name == result.name and r.persona == result.persona)]
        items.append(result)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(r) for r in items], indent=2, ensure_ascii=False), "utf-8")

    def latest(self) -> dict[str, JourneyResult]:
        out: dict[str, JourneyResult] = {}
        for r in sorted(self.all(), key=lambda r: r.time):
            out[r.name] = r
        return out


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def journeys_gate_status(root: Path, spec: str) -> tuple[bool, str]:
    journeys = parse_journeys(spec)
    if not journeys or not has_ui(root):
        return True, "no UI journeys required"
    latest = {_norm(k): v for k, v in JourneyStore(root).latest().items()}
    missing, failed = [], []
    for j in journeys:
        key = _norm(j)
        hit = latest.get(key) or next((v for k, v in latest.items() if key[:40] in k or k[:40] in key), None)
        if hit is None:
            missing.append(j)
        elif not hit.passed:
            failed.append(f"{j}: {hit.notes[:200]}")
    if missing or failed:
        detail = ""
        if missing:
            detail += "Not yet walked through like a real user:\n" + "\n".join(f"- {m}" for m in missing)
        if failed:
            detail += "\nFailed:\n" + "\n".join(f"- {f}" for f in failed)
        detail += "\nUse screen_open / screen_view / tap / type to do each journey, then journey_result."
        return False, detail.strip()
    return True, f"{len(journeys)} journeys passed"
