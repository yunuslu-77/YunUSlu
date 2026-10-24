"""Sending e-mail. Without SMTP settings, mails are written to the log (and kept in OUTBOX for tests)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from .settings import Settings

log = logging.getLogger("app.mail")
OUTBOX: list[EmailMessage] = []


def send(settings: Settings, to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.mail_from, to, subject
    msg.set_content(body)
    OUTBOX.append(msg)
    if not settings.smtp_host:
        log.info("E-mail to %s: %s\n%s", to, subject, body)
        return
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
        if settings.smtp_user:
            s.starttls()
            s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)
