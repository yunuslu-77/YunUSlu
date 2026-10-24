"""All configuration comes from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class Plan:
    id: str
    name_tr: str
    name_en: str
    price_minor: int  # kuruş / cents per month
    currency: str
    features: list[str]
    stripe_price_id: str = ""
    iyzico_plan_code: str = ""


@dataclass
class Settings:
    app_name: str = field(default_factory=lambda: _env("APP_NAME", "{{project_name}}"))
    base_url: str = field(default_factory=lambda: _env("BASE_URL", "http://127.0.0.1:8000"))
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", "dev-only-change-me"))
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///./dev.db"))
    default_lang: str = field(default_factory=lambda: _env("DEFAULT_LANG", "tr"))
    # E-mail: SMTP_HOST empty → e-mails are printed to the log (development).
    smtp_host: str = field(default_factory=lambda: _env("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(_env("SMTP_PORT", "1025")))
    smtp_user: str = field(default_factory=lambda: _env("SMTP_USER"))
    smtp_password: str = field(default_factory=lambda: _env("SMTP_PASSWORD"))
    mail_from: str = field(default_factory=lambda: _env("MAIL_FROM", "no-reply@example.com"))
    # Billing: fake (test mode, default) | stripe | iyzico
    billing_provider: str = field(default_factory=lambda: _env("BILLING_PROVIDER", "fake"))
    stripe_secret_key: str = field(default_factory=lambda: _env("STRIPE_SECRET_KEY"))
    stripe_webhook_secret: str = field(default_factory=lambda: _env("STRIPE_WEBHOOK_SECRET"))
    iyzico_api_key: str = field(default_factory=lambda: _env("IYZICO_API_KEY"))
    iyzico_secret_key: str = field(default_factory=lambda: _env("IYZICO_SECRET_KEY"))
    iyzico_base_url: str = field(default_factory=lambda: _env("IYZICO_BASE_URL", "https://sandbox-api.iyzipay.com"))
    superadmin_emails: list[str] = field(default_factory=lambda: [e.strip().lower() for e in
                                                                  _env("SUPERADMIN_EMAILS").split(",") if e.strip()])
    login_rate_per_minute: int = 5
    plans: list[Plan] = field(default_factory=lambda: [
        Plan("free", "Ücretsiz", "Free", 0, "TRY", ["1 ekip / 1 team", "3 üye / 3 members"]),
        Plan("pro", "Pro", "Pro", 29900, "TRY", ["Sınırsız üye / unlimited members", "Öncelikli destek / priority support"],
             stripe_price_id=_env("STRIPE_PRICE_PRO"), iyzico_plan_code=_env("IYZICO_PLAN_PRO")),
    ])

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")

    def plan(self, plan_id: str) -> Plan:
        for p in self.plans:
            if p.id == plan_id:
                return p
        raise KeyError(plan_id)
