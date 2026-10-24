"""Cheap structural outline of a file so a model can navigate big files without reading them whole."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass
class Symbol:
    line: int
    kind: str
    name: str
    depth: int = 0

    def render(self) -> str:
        return f"{self.line:6}  {'  ' * self.depth}{self.kind} {self.name}"


_REGEX_RULES: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "js": [
        ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)")),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\*?\s+([A-Za-z_$][\w$]*)")),
        ("const", re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>")),
        ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")),
        ("type", re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=")),
    ],
    "kotlin": [
        ("class", re.compile(r"^\s*(?:[a-z]+\s+)*(?:class|object|interface)\s+([A-Za-z_]\w*)")),
        ("fun", re.compile(r"^\s*(?:[a-z]+\s+)*fun\s+(?:<[^>]+>\s*)?(?:[\w.]+\.)?([A-Za-z_]\w*)")),
    ],
    "java": [
        ("class", re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*(?:class|interface|enum|record)\s+([A-Za-z_]\w*)")),
        ("method", re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)+[\w<>\[\], ]+\s+([a-zA-Z_]\w*)\s*\(")),
    ],
    "go": [
        ("func", re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)")),
        ("type", re.compile(r"^type\s+([A-Za-z_]\w*)")),
    ],
    "dart": [
        ("class", re.compile(r"^\s*(?:abstract\s+)?(?:class|mixin|enum|extension)\s+([A-Za-z_]\w*)")),
        ("function", re.compile(r"^\s*(?:static\s+)?(?:Future<[^>]*>|void|[A-Z]\w*(?:<[^>]*>)?|int|double|bool|String)\s+([a-z_]\w*)\s*\(")),
    ],
    "rust": [
        ("fn", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)")),
        ("struct", re.compile(r"^\s*(?:pub\s+)?(?:struct|enum|trait|impl)\s+([A-Za-z_][\w<> ,]*)")),
    ],
}

_EXT = {
    ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js", ".mjs": "js", ".cjs": "js", ".vue": "js",
    ".kt": "kotlin", ".kts": "kotlin", ".java": "java", ".go": "go", ".dart": "dart", ".rs": "rust",
}


def _python(text: str) -> list[Symbol]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _regex(text, [("def", re.compile(r"^\s*(?:async\s+)?def\s+(\w+)")), ("class", re.compile(r"^\s*class\s+(\w+)"))])
    out: list[Symbol] = []

    def walk(node: ast.AST, depth: int) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                out.append(Symbol(child.lineno, "class", child.name, depth))
                walk(child, depth + 1)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append(Symbol(child.lineno, "def", child.name, depth))
                walk(child, depth + 1)

    walk(tree, 0)
    return out


def _markdown(text: str) -> list[Symbol]:
    out, fence = [], False
    for i, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            out.append(Symbol(i, "#" * len(m.group(1)), m.group(2).strip(), len(m.group(1)) - 1))
    return out


def _regex(text: str, rules: list[tuple[str, re.Pattern[str]]]) -> list[Symbol]:
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        for kind, pattern in rules:
            m = pattern.match(line)
            if m:
                indent = len(line) - len(line.lstrip())
                out.append(Symbol(i, kind, m.group(1).strip(), indent // 4))
                break
    return out


def outline(path: str, text: str) -> list[Symbol]:
    lower = path.lower()
    if lower.endswith((".py", ".pyi")):
        return _python(text)
    if lower.endswith((".md", ".markdown")):
        return _markdown(text)
    for ext, lang in _EXT.items():
        if lower.endswith(ext):
            return _regex(text, _REGEX_RULES[lang])
    return []
