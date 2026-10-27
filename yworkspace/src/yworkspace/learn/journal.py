"""Self-improving skills.

1. Record: where the AI got stuck, which errors it repeated (local journal, never leaves the computer).
2. Analyse: group repeated mistakes per model family.
3. Propose: an extra instruction for the related skill / model.
4. Prove: try it on yWorkspace Bench; keep it only if results improve.
5. Approve and share: the user applies it locally and may send the general lesson (no project code) as a PR.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections import defaultdict
from pathlib import Path

from ..config import home

ADVICE = {
    "not_found": "Before editing or reading, confirm the path with list/glob and copy the find text exactly from a "
                 "fresh read (including indentation).",
    "ambiguous": "Make the find text unique: include one or two neighbouring lines, or use replace_all only when "
                 "every occurrence must change.",
    "stale": "The file changed since you read it. Read it again right before editing.",
    "not_read": "Read a file before overwriting or editing it.",
    "no_change": "Do not send edits whose replacement equals the original text.",
    "missing_argument": "Check the tool's required arguments before calling it.",
    "unknown_tool": "Only call tools from the list you were given; do not invent tool names.",
    "outside_workspace": "Use paths relative to the project root; never ../ or absolute paths.",
    "protected": ".yw/ is internal; write project files elsewhere.",
    "exists": "When the file already exists, read it and edit it instead of creating it again.",
    "gate:no unfinished code": "Never leave TODO, placeholder bodies or 'rest of the code' comments; finish every "
                               "function before marking a task done.",
    "gate:tests exist": "Write automated tests for new behaviour in the same step as the code.",
    "gate:checks pass": "Run the project's checks (tests, lint, build) after every change and fix failures before "
                        "moving on.",
    "gate:every task has evidence": "When closing a task, paste the real command output that proves it works.",
}


def signature(text: str) -> str:
    """A privacy-safe, general form of an error: no paths, names, numbers or quoted code."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    s = re.sub(r"(?:[A-Za-z]:)?[\w.-]*[/\\][\w./\\-]+", "<path>", first)
    s = re.sub(r"(['\"`]).*?\1", "<text>", s)
    s = re.sub(r"\b\d+(\.\d+)?\b", "<n>", s)
    s = re.sub(r"\b[\w-]+\.(py|js|ts|tsx|kt|java|dart|go|rs|json|yaml|yml|md)\b", "<file>", s)
    return re.sub(r"\s+", " ", s)[:200]


def error_code(text: str) -> str:
    m = re.match(r"ERROR \[([a-z_]+)\]", text.strip())
    return m.group(1) if m else ""


class Journal:
    def __init__(self, base: Path | None = None):
        self.base = Path(base) if base else home() / "learn"
        self.path = self.base / "journal.jsonl"
        self.lessons_path = self.base / "lessons.json"

    def record(self, kind: str, family: str | None, signature_text: str, code: str = "", tool: str = "",
               detail: str = "") -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        entry = {"time": time.time(), "kind": kind, "family": family or "unknown", "code": code, "tool": tool,
                 "signature": signature_text, "detail": detail[:300]}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text("utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    # ------------------------------------------------------------------ lessons
    def lessons(self) -> list[dict]:
        if not self.lessons_path.exists():
            return []
        return json.loads(self.lessons_path.read_text("utf-8"))

    def save_lessons(self, items: list[dict]) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        self.lessons_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), "utf-8")


def patterns(entries: list[dict], min_count: int = 3) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        key = (e["family"], e.get("code") or e["kind"], e.get("tool", ""), e["signature"])
        groups[key].append(e)
    out = []
    for (family, code, tool, sig), items in groups.items():
        if len(items) >= min_count:
            out.append({"family": family, "code": code, "tool": tool, "signature": sig, "count": len(items),
                        "kind": items[0]["kind"]})
    return sorted(out, key=lambda p: -p["count"])


def skill_for(p: dict) -> str:
    """Which skill a lesson belongs to."""
    code = p["code"]
    if code in ("not_found", "ambiguous", "stale", "not_read", "no_change", "exists", "outside_workspace",
                "protected", "is_directory", "binary_file"):
        return "file-discipline"
    if code.startswith("gate:"):
        return {"gate:tests exist": "testing", "gate:checks pass": "debugging"}.get(code, "deep-work")
    if p["kind"] == "check_failed":
        return "debugging"
    from ..skills import load_all, select
    names = {s.name for s in load_all()}
    for s in select("developer", f"{p['tool']} {p['signature']}", limit=3):
        if not s.always and s.name in names:
            return s.name
    return "deep-work"


def propose(journal: Journal, min_count: int = 3) -> list[dict]:
    existing = journal.lessons()
    known = {(x["family"], x["signature"], x["code"]) for x in existing}
    new = []
    for p in patterns(journal.entries(), min_count):
        if (p["family"], p["signature"], p["code"]) in known:
            for x in existing:
                if (x["family"], x["signature"], x["code"]) == (p["family"], p["signature"], p["code"]):
                    x["count"] = p["count"]
            continue
        advice = ADVICE.get(p["code"]) or (f"A frequent failure with {p['tool'] or 'this kind of task'}: "
                                           f"\"{p['signature']}\". Check for it before finishing.")
        lesson = {"id": uuid.uuid4().hex[:6], "family": p["family"], "skill": skill_for(p), "code": p["code"],
                  "tool": p["tool"], "signature": p["signature"], "count": p["count"],
                  "lesson": f"Repeated mistake (seen {p['count']} times): {p['signature']}. {advice}",
                  "status": "proposed", "bench": {}}
        existing.append(lesson)
        new.append(lesson)
    journal.save_lessons(existing)
    return new


def learned_dir() -> Path:
    return home() / "skills-learned"


def apply(lesson: dict) -> Path:
    """Write the lesson into the user's local overlay for that skill (read by Skill.text)."""
    d = learned_dir() / lesson["skill"]
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{lesson['family'] if lesson['family'] != 'unknown' else 'all'}.md"
    lines = p.read_text("utf-8").splitlines() if p.exists() else []
    entry = f"- {lesson['lesson']} <!-- lesson {lesson['id']} -->"
    if not any(f"lesson {lesson['id']}" in x for x in lines):
        lines.append(entry)
    p.write_text("\n".join(lines) + "\n", "utf-8")
    return p


def unapply(lesson: dict) -> None:
    for p in (learned_dir() / lesson["skill"]).glob("*.md"):
        lines = [x for x in p.read_text("utf-8").splitlines() if f"lesson {lesson['id']}" not in x]
        p.write_text("\n".join(lines) + ("\n" if lines else ""), "utf-8")


def share_text(lesson: dict) -> str:
    """What may be shared: the general lesson only - no project code, paths or personal data."""
    fam = lesson["family"]
    target = (f"yworkspace/src/yworkspace/skills/library/*/{lesson['skill']}/models/{fam}.md"
              if fam not in ("unknown", "all") else f"yworkspace/src/yworkspace/skills/library/*/{lesson['skill']}/"
                                                    "checklist.md")
    bench = lesson.get("bench") or {}
    proof = (f"Bench: pass rate {bench.get('before')} → {bench.get('after')} on {bench.get('tasks')} tasks."
             if bench else "Not yet proven on yWorkspace Bench.")
    return (f"## Skill improvement: {lesson['skill']} ({fam})\n\nAdd to `{target}`:\n\n```\n- {lesson['lesson']}\n```\n\n"
            f"{proof}\n\nNo project code or personal data is included. Open a pull request to "
            "github.com/yunuslu-77/YunUSlu with this text (LICENSING.md: contributions must be reported to the owner).\n")
