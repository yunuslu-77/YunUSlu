"""The file engine: every file operation an AI needs, confined to one project folder."""

from __future__ import annotations

import difflib
import fnmatch
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import matching
from .errors import ToolError
from .outline import outline as build_outline
from .textfile import TextContent, atomic_write, decode, is_binary, sha256

STATE_DIR = ".yw"
IGNORED_DIRS = {".git", STATE_DIR, "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
                ".pytest_cache", ".ruff_cache", "dist", "build", ".next", ".gradle", ".dart_tool", "target"}
DEFAULT_DENY = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore",
                "id_rsa*", "id_ed25519*", "*.kdbx", "secrets.*", "credentials.json"]
DEFAULT_DENY_EXCEPTIONS = [".env.example", ".env.sample", ".env.template"]
MAX_LINE_CHARS = 2000


@dataclass
class Change:
    id: str
    time: float
    op: str  # create | edit | move | delete
    path: str
    before: str | None  # hash of content before (None = did not exist)
    after: str | None  # hash after (None = no longer exists)
    moved_to: str | None = None


@dataclass
class Workspace:
    root: Path
    deny: list[str] = field(default_factory=lambda: list(DEFAULT_DENY))
    deny_exceptions: list[str] = field(default_factory=lambda: list(DEFAULT_DENY_EXCEPTIONS))
    max_file_bytes: int = 5_000_000
    default_read_lines: int = 2000
    require_read_before_write: bool = True

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._seen: dict[str, str] = {}  # relative path -> sha256 at last read/write
        self._state = self.root / STATE_DIR
        (self._state / "history" / "blobs").mkdir(parents=True, exist_ok=True)
        (self._state / "trash").mkdir(parents=True, exist_ok=True)
        self._journal = self._state / "history" / "journal.jsonl"

    # ------------------------------------------------------------------ paths
    def resolve(self, path: str) -> Path:
        if not path or not str(path).strip():
            raise ToolError("bad_path", "Path is empty.")
        p = Path(path)
        full = (p if p.is_absolute() else self.root / p).resolve()
        if full != self.root and self.root not in full.parents:
            raise ToolError("outside_workspace", f"{path} is outside the project folder.",
                            "Use paths relative to the project root.")
        rel = self.rel(full)
        if rel.split("/")[0] == STATE_DIR and not rel.startswith(f"{STATE_DIR}/memory"):
            raise ToolError("protected", f"{path} is yWorkspace's internal folder.")
        return full

    def rel(self, full: Path) -> str:
        return full.relative_to(self.root).as_posix() if full != self.root else "."

    def is_denied(self, full: Path) -> bool:
        name = full.name
        if any(fnmatch.fnmatch(name, pat) for pat in self.deny_exceptions):
            return False
        return any(fnmatch.fnmatch(name, pat) for pat in self.deny)

    def _check_denied(self, full: Path, path: str) -> None:
        if self.is_denied(full):
            raise ToolError("denied", f"{path} may contain secrets and is protected.",
                            "Ask the user to provide the values you need, or use a *.example file.")

    # --------------------------------------------------------------- reading
    def _load(self, full: Path, path: str) -> tuple[bytes, TextContent]:
        if not full.exists():
            raise ToolError("not_found", f"{path} does not exist.", "Use list or glob to find the right path.")
        if full.is_dir():
            raise ToolError("is_directory", f"{path} is a folder, not a file.", "Use list to see its contents.")
        size = full.stat().st_size
        if size > self.max_file_bytes:
            raise ToolError("too_large", f"{path} is {size} bytes, over the {self.max_file_bytes} byte limit.")
        data = full.read_bytes()
        return data, decode(data, path)

    def read(self, path: str, offset: int = 1, limit: int | None = None) -> str:
        full = self.resolve(path)
        self._check_denied(full, path)
        data, content = self._load(full, path)
        self._seen[self.rel(full)] = sha256(data)
        lines = content.text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        total = len(lines)
        offset = max(1, int(offset))
        limit = int(limit) if limit else self.default_read_lines
        chunk = lines[offset - 1 : offset - 1 + limit]
        out = []
        for i, line in enumerate(chunk, offset):
            if len(line) > MAX_LINE_CHARS:
                line = line[:MAX_LINE_CHARS] + " …[line truncated]"
            out.append(f"{i:6}\t{line}")
        if total == 0:
            return f"[{path} is empty]"
        end = offset + len(chunk) - 1
        header = f"[{path}: lines {offset}-{end} of {total}]"
        if end < total:
            header += f" (more below: read with offset={end + 1})"
        return header + "\n" + "\n".join(out)

    def outline(self, path: str) -> str:
        full = self.resolve(path)
        self._check_denied(full, path)
        _, content = self._load(full, path)
        symbols = build_outline(path, content.text)
        total = content.text.count("\n") + (0 if content.text.endswith("\n") else 1)
        if not symbols:
            return f"[{path}: {total} lines, no outline available for this file type]"
        return f"[{path}: {total} lines]\n" + "\n".join(s.render() for s in symbols)

    # ------------------------------------------------------------- guards
    def _guard_write(self, full: Path, path: str) -> bytes | None:
        """Return current bytes (or None if new). Refuse blind overwrites and stale edits."""
        self._check_denied(full, path)
        if not full.exists():
            return None
        data = full.read_bytes()
        if not self.require_read_before_write:
            return data
        seen = self._seen.get(self.rel(full))
        if seen is None:
            raise ToolError("not_read", f"You must read {path} before changing it.",
                            f"Call read on {path} first.")
        if seen != sha256(data):
            raise ToolError("stale", f"{path} changed since you last read it.",
                            f"Read {path} again and redo your change on the current content.")
        return data

    # ------------------------------------------------------------- history
    def _blob(self, data: bytes) -> str:
        h = sha256(data)
        p = self._state / "history" / "blobs" / h
        if not p.exists():
            p.write_bytes(data)
        return h

    def _record(self, op: str, path: str, before: bytes | None, after: bytes | None,
                moved_to: str | None = None) -> Change:
        ch = Change(
            id=uuid.uuid4().hex[:10], time=time.time(), op=op, path=path,
            before=self._blob(before) if before is not None else None,
            after=self._blob(after) if after is not None else None, moved_to=moved_to,
        )
        with self._journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ch.__dict__) + "\n")
        return ch

    def history(self, limit: int = 20) -> list[Change]:
        if not self._journal.exists():
            return []
        rows = [json.loads(x) for x in self._journal.read_text("utf-8").splitlines() if x.strip()]
        undone = {r["undo_of"] for r in rows if r.get("op") == "undo"}
        changes = [Change(**r) for r in rows if r.get("op") != "undo" and r["id"] not in undone]
        return changes[-limit:][::-1]

    def history_text(self, limit: int = 20) -> str:
        items = self.history(limit)
        if not items:
            return "No changes yet."
        return "\n".join(
            f"{c.id}  {time.strftime('%H:%M:%S', time.localtime(c.time))}  {c.op:6}  {c.path}"
            + (f" -> {c.moved_to}" if c.moved_to else "") for c in items
        )

    def undo(self, change_id: str | None = None) -> str:
        items = self.history(10_000)
        if not items:
            raise ToolError("nothing_to_undo", "There are no changes to undo.")
        ch = items[0] if change_id is None else next((c for c in items if c.id == change_id), None)
        if ch is None:
            raise ToolError("not_found", f"No change with id {change_id}.", "Use history to list change ids.")
        blobs = self._state / "history" / "blobs"
        target = self.root / (ch.moved_to or ch.path)
        current = target.read_bytes() if target.exists() else None
        if (sha256(current) if current is not None else None) != ch.after:
            raise ToolError("conflict", f"{ch.moved_to or ch.path} changed after that edit, so it cannot be undone safely.",
                            "Undo the later changes first (see history).")
        if ch.op == "move":
            src = self.root / ch.path
            src.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, src)
        elif ch.before is None:
            target.unlink()
        else:
            atomic_write(self.root / ch.path, (blobs / ch.before).read_bytes())
        for p in {ch.path, ch.moved_to}:
            if p:
                self._seen.pop(p, None)
        with self._journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": uuid.uuid4().hex[:10], "op": "undo", "undo_of": ch.id, "time": time.time()}) + "\n")
        return f"Undid {ch.op} of {ch.path} ({ch.id})."

    # ------------------------------------------------------------- writing
    def _diff(self, path: str, before: str, after: str, context: int = 3) -> str:
        diff = difflib.unified_diff(before.splitlines(), after.splitlines(),
                                    f"a/{path}", f"b/{path}", lineterm="", n=context)
        text = "\n".join(diff)
        if len(text) > 6000:
            text = text[:6000] + "\n…[diff truncated]"
        return text

    def _commit(self, full: Path, path: str, op: str, before: bytes | None, content: TextContent) -> Change:
        data = content.encode()
        atomic_write(full, data)
        self._seen[self.rel(full)] = sha256(data)
        return self._record(op, self.rel(full), before, data)

    def create(self, path: str, content: str, overwrite: bool = False) -> str:
        full = self.resolve(path)
        if full.exists() and full.is_dir():
            raise ToolError("is_directory", f"{path} is a folder.")
        if full.exists() and not overwrite:
            raise ToolError("exists", f"{path} already exists.",
                            "Use edit to change part of it, or create with overwrite=true after reading it.")
        before = self._guard_write(full, path)
        if before is not None:
            old = decode(before, path)
            new = TextContent(content.replace("\r\n", "\n"), old.newline, old.encoding)
        else:
            new = TextContent(content.replace("\r\n", "\n"), "\n", "utf-8")
        ch = self._commit(full, path, "create" if before is None else "edit", before, new)
        lines = new.text.count("\n") + (0 if new.text.endswith("\n") or not new.text else 1)
        verb = "Created" if before is None else "Overwrote"
        return f"{verb} {self.rel(full)} ({lines} lines). change_id={ch.id}"

    def edit(self, path: str, find: str, replace: str, replace_all: bool = False) -> str:
        return self.multi_edit(path, [{"find": find, "replace": replace, "replace_all": replace_all}])

    def multi_edit(self, path: str, edits: list[dict]) -> str:
        full = self.resolve(path)
        before = self._guard_write(full, path)
        if before is None:
            raise ToolError("not_found", f"{path} does not exist.", "Use create to make a new file.")
        content = decode(before, path)
        text = content.text
        total = 0
        for n, e in enumerate(edits, 1):
            try:
                text, count = matching.apply_edit(text, e.get("find", ""), e.get("replace", ""),
                                                  bool(e.get("replace_all", False)), path)
            except ToolError as err:
                if len(edits) > 1:
                    err.message = f"Edit {n} of {len(edits)} failed, so no edits were applied. {err.message}"
                raise
            total += count
        ch = self._commit(full, path, "edit", before, TextContent(text, content.newline, content.encoding))
        return (f"Edited {self.rel(full)}: {total} replacement(s). change_id={ch.id}\n"
                + self._diff(self.rel(full), content.text, text))

    def move(self, src: str, dst: str) -> str:
        s, d = self.resolve(src), self.resolve(dst)
        if not s.exists():
            raise ToolError("not_found", f"{src} does not exist.")
        if s.is_dir():
            raise ToolError("is_directory", "Moving folders is not supported; move files one by one.")
        if d.exists():
            raise ToolError("exists", f"{dst} already exists.")
        self._check_denied(s, src)
        self._check_denied(d, dst)
        data = s.read_bytes()
        d.parent.mkdir(parents=True, exist_ok=True)
        os.replace(s, d)
        self._seen.pop(self.rel(s), None)
        self._seen[self.rel(d)] = sha256(data)
        ch = self._record("move", self.rel(s), data, data, moved_to=self.rel(d))
        return f"Moved {self.rel(s)} -> {self.rel(d)}. change_id={ch.id}"

    def delete(self, path: str) -> str:
        full = self.resolve(path)
        if full == self.root:
            raise ToolError("protected", "Refusing to delete the project root.")
        if not full.exists():
            raise ToolError("not_found", f"{path} does not exist.")
        if full.is_dir():
            if any(full.iterdir()):
                raise ToolError("not_empty", f"{path} is a folder that is not empty.",
                                "Delete the files inside first, so each deletion can be undone.")
            full.rmdir()
            return f"Deleted empty folder {self.rel(full)}."
        before = self._guard_write(full, path)
        trash = self._state / "trash" / f"{uuid.uuid4().hex[:8]}-{full.name}"
        shutil.copy2(full, trash)
        full.unlink()
        self._seen.pop(self.rel(full), None)
        ch = self._record("delete", self.rel(full), before, None)
        return f"Deleted {self.rel(full)} (recoverable with undo). change_id={ch.id}"

    # ------------------------------------------------------------- browsing
    def _walk(self, base: Path):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
            for f in sorted(filenames):
                yield Path(dirpath) / f

    def list(self, path: str = ".", depth: int = 2, limit: int = 500) -> str:
        base = self.resolve(path)
        if not base.is_dir():
            raise ToolError("not_directory", f"{path} is not a folder.")
        lines: list[str] = []

        def visit(d: Path, level: int) -> None:
            try:
                entries = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return
            for e in entries:
                if len(lines) >= limit:
                    return
                if e.is_dir():
                    if e.name in IGNORED_DIRS:
                        continue
                    lines.append(f"{'  ' * level}{e.name}/")
                    if level + 1 < depth:
                        visit(e, level + 1)
                else:
                    size = e.stat().st_size
                    lines.append(f"{'  ' * level}{e.name}  ({size} B)")

        visit(base, 0)
        if not lines:
            return f"[{path} is empty]"
        if len(lines) >= limit:
            lines.append(f"…[stopped at {limit} entries]")
        return "\n".join(lines)

    def glob(self, pattern: str, limit: int = 500) -> str:
        found = []
        for f in self._walk(self.root):
            rel = self.rel(f)
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(f.name, pattern):
                found.append(rel)
                if len(found) >= limit:
                    break
        return "\n".join(found) if found else f"No files match {pattern}."

    def search(self, pattern: str, path: str = ".", file_glob: str | None = None,
               ignore_case: bool = False, limit: int = 200) -> str:
        try:
            rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as e:
            raise ToolError("bad_regex", f"Invalid regular expression: {e}",
                            "Escape special characters such as ( ) [ ] . * + ? with a backslash.") from e
        base = self.resolve(path)
        files = [base] if base.is_file() else self._walk(base)
        hits: list[str] = []
        for f in files:
            if self.is_denied(f) or (file_glob and not fnmatch.fnmatch(f.name, file_glob)):
                continue
            try:
                if f.stat().st_size > self.max_file_bytes:
                    continue
                data = f.read_bytes()
            except OSError:
                continue
            if is_binary(data):
                continue
            for n, line in enumerate(decode(data).text.split("\n"), 1):
                if rx.search(line):
                    hits.append(f"{self.rel(f)}:{n}: {line[:300]}")
                    if len(hits) >= limit:
                        return "\n".join(hits) + f"\n…[stopped at {limit} matches]"
        return "\n".join(hits) if hits else f"No matches for {pattern}."

    def diff(self, change_id: str | None = None) -> str:
        items = self.history(10_000)
        if not items:
            return "No changes yet."
        ch = items[0] if change_id is None else next((c for c in items if c.id == change_id), None)
        if ch is None:
            raise ToolError("not_found", f"No change with id {change_id}.")
        blobs = self._state / "history" / "blobs"
        before = decode((blobs / ch.before).read_bytes()).text if ch.before else ""
        after = decode((blobs / ch.after).read_bytes()).text if ch.after else ""
        return self._diff(ch.moved_to or ch.path, before, after) or f"{ch.op} {ch.path}: no text difference."
