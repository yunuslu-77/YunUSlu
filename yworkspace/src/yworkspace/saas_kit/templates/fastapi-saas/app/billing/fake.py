"""Test-mode provider: no real money, no external service. The 'payment page' is served by this app and
produces a signed event exactly like a real provider's webhook would."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from . import BillingEvent, Provider, WebhookError


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, settings):
        self.settings = settings

    def sign(self, body: bytes) -> str:
        return hmac.new(self.settings.secret_key.encode(), body, hashlib.sha256).hexdigest()

    def checkout_url(self, org, plan_id, email, success_url, cancel_url) -> str:
        session = secrets.token_urlsafe(12)
        return f"/billing/fake-pay?session={session}&org={org.id}&plan={plan_id}"

    def make_event(self, org_id: int, plan_id: str, kind: str = "activated") -> tuple[bytes, dict]:
        payload = {"id": "evt_" + secrets.token_hex(8), "org_id": org_id, "plan": plan_id, "kind": kind,
                   "subscription": f"fake_sub_{org_id}", "customer": f"fake_cus_{org_id}",
                   "period_end": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
        body = json.dumps(payload).encode()
        return body, {"x-fake-signature": self.sign(body)}

    def parse_webhook(self, body: bytes, headers: dict) -> list[BillingEvent]:
        sig = headers.get("x-fake-signature", "")
        if not hmac.compare_digest(sig, self.sign(body)):
            raise WebhookError("bad signature")
        d = json.loads(body)
        status = {"activated": "active", "payment_failed": "past_due", "canceled": "canceled"}.get(d["kind"], "active")
        return [BillingEvent("fake", d["id"], d["org_id"], d["kind"], d["plan"], status, d["customer"],
                             d["subscription"], datetime.fromisoformat(d["period_end"]))]

    def cancel(self, sub) -> None:
        sub.cancel_at_period_end = True
