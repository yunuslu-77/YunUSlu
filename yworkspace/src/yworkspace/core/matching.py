"""Smart find-and-replace.

Exact matches are required to apply an edit. When there is no exact match we look for
the closest region and show it to the model, so it can retry with the real text.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from .errors import ToolError


@dataclass
class Suggestion:
    start_line: int  # 1-based
    end_line: int
    text: str
    score: float
    whitespace_only: bool


def line_of_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def find_all(text: str, needle: str) -> list[int]:
    found, start = [], 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            return found
        found.append(i)
        start = i + 1


def _norm(line: str) -> str:
    return " ".join(line.split())


def closest_region(text: str, needle: str) -> Suggestion | None:
    lines = text.split("\n")
    target = needle.strip("\n").split("\n")
    n = len(target)
    if not lines or n == 0 or n > len(lines) + 2:
        return None
    target_norm = "\n".join(_norm(x) for x in target)
    best: Suggestion | None = None
    for size in {max(1, n - 1), n, n + 1}:
        if size > len(lines):
            continue
        for i in range(0, len(lines) - size + 1):
            window = lines[i : i + size]
            window_norm = "\n".join(_norm(x) for x in window)
            if window_norm == target_norm:
                return Suggestion(i + 1, i + size, "\n".join(window), 1.0, True)
            matcher = difflib.SequenceMatcher(None, window_norm, target_norm, autojunk=False)
            if matcher.real_quick_ratio() < (best.score if best else 0.5):
                continue
            score = matcher.ratio()
            if score > (best.score if best else 0.5):
                best = Suggestion(i + 1, i + size, "\n".join(window), score, False)
    return best


def numbered(text: str, first_line: int) -> str:
    return "\n".join(f"{first_line + k:6}\t{line}" for k, line in enumerate(text.split("\n")))


def apply_edit(text: str, old: str, new: str, replace_all: bool = False, path: str = "") -> tuple[str, int]:
    """Return (new_text, replacement_count) or raise a ToolError the model can learn from."""
    old = old.replace("\r\n", "\n")
    new = new.replace("\r\n", "\n")
    if old == "":
        raise ToolError(
            "empty_find",
            "The text to find is empty.",
            "To create a new file use the create tool. To add text, find a nearby line and include it in both find and replace.",
        )
    if old == new:
        raise ToolError("no_change", "The find and replace texts are identical, so nothing would change.")
    hits = find_all(text, old)
    if not hits:
        sug = closest_region(text, old)
        if sug is None:
            raise ToolError(
                "not_found",
                f"The text to find does not appear in {path}.",
                "Read the file again and copy the exact lines you want to change, including indentation.",
            )
        reason = (
            "It matches except for whitespace/indentation."
            if sug.whitespace_only
            else f"The closest region is {round(sug.score * 100)}% similar."
        )
        raise ToolError(
            "not_found",
            f"The text to find does not appear exactly in {path}. {reason} "
            f"Did you mean lines {sug.start_line}-{sug.end_line}?\n"
            f"{numbered(sug.text, sug.start_line)}",
            "Copy the text exactly as shown above (without the line-number column) and try again.",
        )
    if len(hits) > 1 and not replace_all:
        where = ", ".join(str(line_of_offset(text, h)) for h in hits[:20])
        raise ToolError(
            "ambiguous",
            f"The text to find appears {len(hits)} times in {path} (starting at lines {where}).",
            "Add more surrounding lines so it matches exactly one place, or set replace_all to true.",
        )
    if replace_all:
        return text.replace(old, new), len(hits)
    i = hits[0]
    return text[:i] + new + text[i + len(old) :], 1
