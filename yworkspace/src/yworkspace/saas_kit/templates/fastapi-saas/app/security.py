"""Passwords, one-time tokens, signed session cookies, CSRF and login rate limiting."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer

_ph = PasswordHasher()
COMMON_PASSWORDS = {"12345678", "123456789", "password", "password1", "qwerty123", "11111111", "iloveyou",
                    "sifre123", "parola123", "123123123", "abc12345"}


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_problem(password: str) -> str | None:
    if len(password) < 8:
        return "password_short"
    if password.lower() in COMMON_PASSWORDS:
        return "password_common"
    return None


def new_token() -> tuple[str, str]:
    """(token for the e-mail link, hash stored in the database)."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SessionSigner:
    def __init__(self, secret: str):
        self.s = URLSafeTimedSerializer(secret, salt="session")

    def dumps(self, data: dict) -> str:
        return self.s.dumps(data)

    def loads(self, value: str, max_age: int = 60 * 60 * 24 * 30) -> dict | None:
        try:
            return self.s.loads(value, max_age=max_age)
        except BadSignature:
            return None


def csrf_token(secret: str, session_value: str) -> str:
    return hmac.new(secret.encode(), ("csrf:" + session_value).encode(), hashlib.sha256).hexdigest()[:32]


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True
