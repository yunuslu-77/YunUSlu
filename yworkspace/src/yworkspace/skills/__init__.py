"""Skill library: load, match to a task, and export to every AI's own format.

A skill folder (skills/library/<category>/<name>/):
  skill.yaml          name, titles, description, triggers, roles, priority
  core.en.md          main instructions (English)
  core.tr.md          main instructions (Turkish)
  checklist.md        optional: review / done checklist (English, shared)
  examples.md         optional: worked examples (weak models learn best from examples)
  models/<id>.md      optional: extra notes for one model family (deepseek, gemini, claude, openai, small-local)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

LIBRARY = Path(__file__).parent / "library"
EXTRA_DIRS: list[Path] = []  # plugins add their skill folders here
MAX_CHARS = 9000


@dataclass
class Skill:
    name: str
    category: str
    path: Path
    title_tr: str
    title_en: str
    description: str
    triggers: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)  # roles it always applies to
    priority: int = 50
    always: bool = False

    def text(self, lang: str = "en", model_family: str | None = None, with_extras: bool = True) -> str:
        core = self.path / f"core.{lang}.md"
        if not core.exists():
            core = self.path / "core.en.md"
        parts = [core.read_text("utf-8").strip()]
        if with_extras:
            for extra in ("checklist.md", "examples.md"):
                p = self.path / extra
                if p.exists():
                    parts.append(p.read_text("utf-8").strip())
        if model_family:
            p = self.path / "models" / f"{model_family}.md"
            if p.exists():
                parts.append("### Notes for your model\n" + p.read_text("utf-8").strip())
        learned = _learned(self.name, model_family)
        if learned:
            parts.append("### Lessons learned on this computer\n" + learned)
        return "\n\n".join(parts)


def _learned(name: str, family: str | None) -> str:
    """Lessons the user approved (learn/), stored outside the library so updates never overwrite them."""
    from ..config import home
    d = home() / "skills-learned" / name
    texts = []
    for f in ("all", family):
        p = d / f"{f}.md" if f else None
        if p is not None and p.exists():
            texts.append(p.read_text("utf-8").strip())
    return "\n".join(t for t in texts if t)


def load_all(extra_dirs: list[Path] | None = None) -> list[Skill]:
    out = []
    for base in [LIBRARY, *EXTRA_DIRS, *(extra_dirs or [])]:
        for meta in sorted(Path(base).glob("*/*/skill.yaml")):
            d = yaml.safe_load(meta.read_text("utf-8")) or {}
            out.append(Skill(d.get("name", meta.parent.name), meta.parent.parent.name, meta.parent,
                             d.get("title_tr", meta.parent.name), d.get("title_en", meta.parent.name),
                             d.get("description", ""), [t.lower() for t in d.get("triggers", [])],
                             d.get("roles", []), int(d.get("priority", 50)), bool(d.get("always", False))))
    return out


def model_family(preset: str | None) -> str | None:
    if not preset:
        return None
    p = preset.lower()
    if p.startswith("ollama"):
        return "small-local"
    for fam in ("deepseek", "gemini", "claude", "qwen", "mistral", "grok", "kimi"):
        if fam in p:
            return fam
    if p.startswith("openai") or "gpt" in p:
        return "openai"
    return None


def score(skill: Skill, role: str, text: str) -> float:
    """Concrete trigger matches in the task/project outweigh generic role defaults."""
    s = 0.0
    if role in skill.roles:
        s += 10
    low = text.lower()
    # Turkish adds suffixes (ödeme → ödemeli), so longer triggers only need to match at a word start.
    hits = sum(1 for trig in skill.triggers
               if re.search(r"(?<![\w])" + re.escape(trig) + ("" if len(trig) >= 4 else r"(?![\w])"), low))
    s += 25 * min(hits, 4)
    return s + skill.priority / 100 if s else 0.0


def project_text(root: Path | None) -> str:
    """Signals from the project itself (package.json, pyproject, spec) so matching works mid-project."""
    if root is None:
        return ""
    root = Path(root)
    out = []
    for name in ("package.json", "pyproject.toml", "requirements.txt", "pubspec.yaml", "build.gradle.kts",
                 "build.gradle", "go.mod", "Cargo.toml", "docker-compose.yml", ".yw/SPEC.md"):
        p = root / name
        if p.exists():
            out.append(p.read_text("utf-8", errors="replace")[:4000])
    return "\n".join(out)


def select(role: str, text: str, root: Path | None = None, limit: int = 4,
           extra_dirs: list[Path] | None = None) -> list[Skill]:
    context = text + "\n" + project_text(root)
    skills = load_all(extra_dirs)
    always = sorted((s for s in skills if s.always), key=lambda s: -s.priority)
    ranked = sorted(((score(s, role, context), s) for s in skills if not s.always), key=lambda x: -x[0])
    return always + [s for sc, s in ranked if sc > 0][:limit]


def skills_for(role: str, text: str, lang: str, root=None, preset: str | None = None) -> str:
    chosen = select(role, text, root)
    if not chosen:
        return ""
    fam = model_family(preset)
    parts, used = [], 0
    for s in chosen:
        body = s.text(lang, fam)
        if used + len(body) > MAX_CHARS:
            body = s.text(lang, fam, with_extras=False)
            if used + len(body) > MAX_CHARS:
                continue
        parts.append(f"## Skill: {s.title_en if lang == 'en' else s.title_tr}\n{body}")
        used += len(body)
    return "# Skills for this work\n\n" + "\n\n".join(parts)
