"""Reading and writing text files while preserving encoding and line endings."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import ToolError

BINARY_SNIFF_BYTES = 8192


@dataclass
class TextContent:
    text: str  # always uses "\n" line endings
    newline: str  # original line ending: "\n" or "\r\n"
    encoding: str  # "utf-8", "utf-8-sig" or "latin-1"

    def encode(self) -> bytes:
        text = self.text.replace("\n", self.newline) if self.newline != "\n" else self.text
        return text.encode(self.encoding)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:BINARY_SNIFF_BYTES]


def decode(data: bytes, path: str = "") -> TextContent:
    if is_binary(data):
        raise ToolError("binary_file", f"{path} looks like a binary file and cannot be handled as text.")
    if data.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
        raw = data.decode("utf-8-sig")
    else:
        try:
            raw = data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            raw = data.decode("latin-1")
            encoding = "latin-1"
    crlf = raw.count("\r\n")
    lf = raw.count("\n") - crlf
    newline = "\r\n" if crlf > lf else "\n"
    return TextContent(text=raw.replace("\r\n", "\n"), newline=newline, encoding=encoding)


def atomic_write(path: Path, data: bytes) -> None:
    """Write via a temp file in the same directory, then rename, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else None
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".yw-tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
