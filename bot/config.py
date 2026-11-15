"""YAi ayarları. Tüm değerler .env dosyasından okunur."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "evet", "yes", "on")


def _list(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


@dataclass
class Config:
    bot_name: str = "YAi"
    gemini_api_key: str = ""
    model_fast: str = "gemini-3.5-flash-lite"
    model_smart: str = "gemini-3.8-flash"
    model_tts: str = "gemini-3.8-flash-lite-tts"
    tts_voice: str = "Kore"
    telegram_token: str = ""
    owner_id: int = 0
    timezone: str = "Europe/Istanbul"
    data_dir: Path = Path("data")
    monthly_limit_usd: float = 9.0
    daily_limit_usd: float = 0.40
    history_limit: int = 20
    max_tool_steps: int = 12
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8080
    dashboard_token: str = ""
    public_url: str = ""
    phone_token: str = ""
    phone_notify_apps: list[str] = field(default_factory=list)
    phone_battery_threshold: int = 15
    proactive_email_minutes: int = 20
    proactive_calendar_minutes: int = 15
    learning_enabled: bool = True
    shell_enabled: bool = True
    browser_executable: str = ""

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "yai.db"

    @property
    def workspace(self) -> Path:
        return self.data_dir / "workspace"

    @property
    def google_client_file(self) -> Path:
        return self.data_dir / "google_client.json"

    @property
    def google_token_file(self) -> Path:
        return self.data_dir / "google_token.json"

    @classmethod
    def from_env(cls, env_file: str | None = ".env") -> "Config":
        if load_dotenv and env_file and Path(env_file).exists():
            load_dotenv(env_file)
        e = os.environ.get
        c = cls(
            bot_name=e("BOT_NAME", "YAi"),
            gemini_api_key=e("GEMINI_API_KEY", ""),
            model_fast=e("MODEL_FAST", cls.model_fast),
            model_smart=e("MODEL_SMART", cls.model_smart),
            model_tts=e("MODEL_TTS", cls.model_tts),
            tts_voice=e("TTS_VOICE", cls.tts_voice),
            telegram_token=e("TELEGRAM_TOKEN", ""),
            owner_id=int(e("TELEGRAM_OWNER_ID", "0") or 0),
            timezone=e("TIMEZONE", cls.timezone),
            data_dir=Path(e("DATA_DIR", "data")),
            monthly_limit_usd=float(e("MONTHLY_LIMIT_USD", "9.0")),
            daily_limit_usd=float(e("DAILY_LIMIT_USD", "0.40")),
            history_limit=int(e("HISTORY_LIMIT", "20")),
            max_tool_steps=int(e("MAX_TOOL_STEPS", "12")),
            dashboard_host=e("DASHBOARD_HOST", "0.0.0.0"),
            dashboard_port=int(e("DASHBOARD_PORT", "8080")),
            dashboard_token=e("DASHBOARD_TOKEN", ""),
            public_url=e("PUBLIC_URL", ""),
            phone_token=e("PHONE_TOKEN", ""),
            phone_notify_apps=_list(e("PHONE_NOTIFY_APPS", "com.whatsapp,com.google.android.gm")),
            phone_battery_threshold=int(e("PHONE_BATTERY_THRESHOLD", "15")),
            proactive_email_minutes=int(e("PROACTIVE_EMAIL_MINUTES", "20")),
            proactive_calendar_minutes=int(e("PROACTIVE_CALENDAR_MINUTES", "15")),
            learning_enabled=_bool(e("LEARNING_ENABLED"), True),
            shell_enabled=_bool(e("SHELL_ENABLED"), True),
            browser_executable=e("BROWSER_EXECUTABLE", ""),
        )
        c.data_dir.mkdir(parents=True, exist_ok=True)
        c.workspace.mkdir(parents=True, exist_ok=True)
        return c
