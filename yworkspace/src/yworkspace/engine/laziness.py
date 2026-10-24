"""Detect half-done work: placeholders, stubs and 'rest of the code here' comments."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".kt", ".kts", ".java",
            ".go", ".rs", ".dart", ".php", ".rb", ".cs", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".html",
            ".css", ".scss", ".sql", ".sh"}

PATTERNS = [
    (re.compile(r"\b(TODO|FIXME|XXX)\b"), "TODO/FIXME left in code"),
    (re.compile(r"(rest of (the )?(code|file|implementation)|remaining (code|implementation)|"
                r"(existing|previous|same) code (here|unchanged|as before)|\.\.\. ?(existing|rest)|"
                r"implement (this|here|me|later)|your (code|logic|implementation) here|add (your )?(code|logic) here|"
                r"not (yet )?implemented|placeholder (code|implementation|logic|function|data)|"
                r"stub(bed)? (out|implementation))", re.I),
     "placeholder instead of real code"),
    (re.compile(r"(geri kalan(ı)? (kod|aynı)|buraya (kod|kodunuzu|mantığı) (ekle|ekleyin|yaz)|"
                r"daha sonra (eklenecek|yazılacak|uygulanacak)|henüz (uygulanmadı|yazılmadı))", re.I),
     "placeholder instead of real code (Turkish)"),
    (re.compile(r"^\s*(//|#|/\*|\*)\s*\.{3}\s*$"), "'...' comment standing in for code"),
    (re.compile(r"throw new Error\(\s*['\"](not implemented|todo)", re.I), "not-implemented stub"),
    (re.compile(r"raise NotImplementedError"), "NotImplementedError stub"),
    (re.compile(r"\b(lorem ipsum)\b", re.I), "dummy text"),
]


@dataclass
class Finding:
    path: str
    line: int
    reason: str
    text: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.reason}: {self.text.strip()[:120]}"


def _python_stubs(path: str, text: str) -> list[Finding]:
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [Finding(path, e.lineno or 1, "Python syntax error", str(e.msg))]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None),
                                                                                       ast.Constant))]
            decos = {getattr(d, "id", getattr(d, "attr", "")) for d in node.decorator_list}
            if decos & {"abstractmethod", "overload"}:
                continue
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                out.append(Finding(path, node.lineno, "empty function (only 'pass')", f"def {node.name}"))
            elif len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and body[0].value.value is Ellipsis:
                out.append(Finding(path, node.lineno, "empty function (only '...')", f"def {node.name}"))
    return out


def scan_text(path: str, text: str) -> list[Finding]:
    if Path(path).suffix.lower() not in CODE_EXT:
        return []
    findings: list[Finding] = []
    for n, line in enumerate(text.split("\n"), 1):
        for rx, reason in PATTERNS:
            if rx.search(line):
                findings.append(Finding(path, n, reason, line))
                break
    if path.endswith(".py"):
        findings += _python_stubs(path, text)
    return findings


def scan_files(root: Path, paths: list[str], ignore: list[str] | None = None) -> list[Finding]:
    out: list[Finding] = []
    for rel in sorted(set(paths)):
        if ignore and any(Path(rel).match(g) for g in ignore):
            continue
        if "/tests/" in f"/{rel}" or Path(rel).name.startswith("test_"):
            continue  # test doubles legitimately contain stubs
        p = Path(root) / rel
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        out += scan_text(rel, text)
    return out
