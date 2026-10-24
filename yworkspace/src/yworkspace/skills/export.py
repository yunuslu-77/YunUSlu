"""Export skills to each AI's own format, so they work without yWorkspace too.

claude   → <out>/claude/<lang>/<name>/SKILL.md   (upload the folder as a skill, or copy to ~/.claude/skills/)
chatgpt  → <out>/chatgpt/<lang>/<name>.md         (fields for a Custom GPT)
gemini   → <out>/gemini/<lang>/<name>.md          (instructions for a Gem)
deepseek → <out>/deepseek/<lang>/<name>.md        (system prompt to paste at the start of a chat)
prompt   → <out>/prompt/<lang>/<name>.md          (plain system prompt for any model)
"""

from __future__ import annotations

from pathlib import Path

import yaml

from . import Skill, load_all

FORMATS = ("claude", "chatgpt", "gemini", "deepseek", "prompt")
FAMILY = {"claude": "claude", "chatgpt": "openai", "gemini": "gemini", "deepseek": "deepseek", "prompt": None}


def _desc(s: Skill, lang: str) -> str:
    trig = ", ".join(s.triggers[:12])
    if lang == "tr":
        return f"{s.description} Şu konularda kullan: {trig}."
    return f"{s.description} Use when the task involves: {trig}."


def render(s: Skill, fmt: str, lang: str) -> tuple[str, str]:
    """Return (relative path, content)."""
    title = s.title_tr if lang == "tr" else s.title_en
    body = s.text(lang, FAMILY[fmt])
    reply_lang = "Kullanıcıya Türkçe cevap ver." if lang == "tr" else "Reply to the user in English."
    if fmt == "claude":
        name = s.name + ("-tr" if lang == "tr" else "")
        front = yaml.safe_dump({"name": name, "description": _desc(s, lang).replace("\n", " ")},
                               allow_unicode=True, sort_keys=False, width=10_000)
        return f"claude/{lang}/{name}/SKILL.md", f"---\n{front}---\n\n# {title}\n\n{body}\n"
    if fmt == "chatgpt":
        starters = "\n".join(f"- {t}" for t in s.triggers[:4])
        return f"chatgpt/{lang}/{s.name}.md", (
            f"# {'Özel GPT' if lang == 'tr' else 'Custom GPT'}: {title}\n\n## {'Ad' if lang == 'tr' else 'Name'}\n{title}\n\n"
            f"## {'Açıklama' if lang == 'tr' else 'Description'}\n{s.description}\n\n"
            f"## {'Talimatlar' if lang == 'tr' else 'Instructions'}\n```\n{body}\n\n{reply_lang}\n```\n\n"
            f"## {'Sohbet başlatıcılar' if lang == 'tr' else 'Conversation starters'}\n{starters}\n")
    if fmt == "gemini":
        return f"gemini/{lang}/{s.name}.md", (
            f"# Gemini Gem: {title}\n\n## {'Ad' if lang == 'tr' else 'Name'}\n{title}\n\n"
            f"## {'Talimatlar' if lang == 'tr' else 'Instructions'}\n```\nRole and task: {s.description}\n\n{body}\n\n"
            f"{reply_lang}\n```\n")
    if fmt == "deepseek":
        intro = ("Bu sohbetin başına yapıştırın. / Paste at the start of the chat." if lang == "tr"
                 else "Paste at the start of the chat.")
        return f"deepseek/{lang}/{s.name}.md", f"# DeepSeek: {title}\n\n{intro}\n\n```\n{body}\n\n{reply_lang}\n```\n"
    return f"prompt/{lang}/{s.name}.md", f"# {title}\n\n{body}\n\n{reply_lang}\n"


def export(out_dir: Path, formats=FORMATS, langs=("tr", "en"), names: list[str] | None = None) -> list[Path]:
    written = []
    for s in load_all():
        if names and s.name not in names:
            continue
        for fmt in formats:
            for lang in langs:
                rel, content = render(s, fmt, lang)
                p = Path(out_dir) / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, "utf-8")
                written.append(p)
    return written
