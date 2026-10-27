"""Phone pairing. The phone never gets the main session token: it gets its own device token (stored hashed),
after the user shows a one-time code (QR) on the computer. Devices can be listed and revoked."""

from __future__ import annotations

import hashlib
import json
import secrets
import socket
import time
from pathlib import Path

from ..config import home

CODE_TTL = 300
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def lan_ip() -> str:
    """This computer's address on the local network (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Devices:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else home() / "devices.json"
        self.codes: dict[str, float] = {}  # one-time pairing codes (memory only) -> expiry
        self.failures: list[float] = []

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text("utf-8"))

    def _save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=2), "utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    def new_code(self) -> str:
        now = time.time()
        self.codes = {c: t for c, t in self.codes.items() if t > now}
        code = "".join(secrets.choice(ALPHABET) for _ in range(4)) + "-" + \
            "".join(secrets.choice(ALPHABET) for _ in range(4))
        self.codes[code] = now + CODE_TTL
        return code

    def claim(self, code: str, name: str) -> tuple[str, dict] | None:
        now = time.time()
        self.failures = [t for t in self.failures if t > now - 60]
        if len(self.failures) >= 10:  # brute force protection
            return None
        code = (code or "").strip().upper()
        exp = self.codes.pop(code, None)
        if exp is None or exp < now:
            self.failures.append(now)
            return None
        token = secrets.token_urlsafe(32)
        dev = {"id": secrets.token_hex(4), "name": (name or "Telefon")[:40], "hash": _h(token), "created": now,
               "last_seen": now}
        items = self._load()
        items.append(dev)
        self._save(items)
        return token, {k: v for k, v in dev.items() if k != "hash"}

    def check(self, token: str | None) -> dict | None:
        if not token:
            return None
        h = _h(token)
        items = self._load()
        for d in items:
            if secrets.compare_digest(d["hash"], h):
                if time.time() - d.get("last_seen", 0) > 60:
                    d["last_seen"] = time.time()
                    self._save(items)
                return d
        return None

    def list(self) -> list[dict]:
        return [{k: v for k, v in d.items() if k != "hash"} for d in self._load()]

    def revoke(self, device_id: str) -> bool:
        items = self._load()
        kept = [d for d in items if d["id"] != device_id]
        self._save(kept)
        return len(kept) != len(items)
