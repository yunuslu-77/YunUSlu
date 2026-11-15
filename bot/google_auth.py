"""Google hesabı bağlama (OAuth). Sunucuda tarayıcı olmadığı için kopyala-yapıştır akışı kullanılır:

1. Bot sana bir bağlantı yollar → telefonda açıp izin verirsin.
2. Tarayıcı 'localhost' adresine yönlenir ve sayfa açılmaz (normal).
3. Adres çubuğundaki tam adresi kopyalayıp bota yapıştırırsın.
"""
from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]
REDIRECT = "http://localhost:8765/"


class GoogleAuth:
    def __init__(self, client_file: Path, token_file: Path):
        self.client_file = client_file
        self.token_file = token_file
        self._flow: Flow | None = None
        self._creds: Credentials | None = None

    def connected(self) -> bool:
        return self.credentials() is not None

    def credentials(self) -> Credentials | None:
        if self._creds and self._creds.valid:
            return self._creds
        if not self.token_file.exists():
            return None
        creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        if not creds.valid and creds.refresh_token:
            try:
                creds.refresh(Request())
                self.token_file.write_text(creds.to_json())
            except Exception:
                return None
        self._creds = creds if creds.valid else None
        return self._creds

    def start(self) -> str:
        if not self.client_file.exists():
            raise FileNotFoundError(
                f"{self.client_file} bulunamadı. Google Cloud Console → APIs & Services → Credentials → "
                "OAuth client ID (Desktop app) oluştur, JSON'u indirip bu adla kaydet.")
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")  # yalnızca localhost yönlendirmesi için
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
        self._flow = Flow.from_client_secrets_file(str(self.client_file), scopes=SCOPES, redirect_uri=REDIRECT)
        url, _ = self._flow.authorization_url(access_type="offline", prompt="consent")
        return url

    @property
    def waiting(self) -> bool:
        return self._flow is not None

    def finish(self, redirected_url: str) -> None:
        if not self._flow:
            raise RuntimeError("Önce /google komutunu çalıştır.")
        self._flow.fetch_token(authorization_response=redirected_url.strip())
        creds = self._flow.credentials
        self.token_file.write_text(creds.to_json())
        try:
            self.token_file.chmod(0o600)
        except OSError:
            pass
        self._creds = creds
        self._flow = None
