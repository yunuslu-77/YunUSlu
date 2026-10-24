"""Stripe: hosted Checkout for subscriptions, webhook signature verification (no SDK needed)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import httpx

from . import BillingEvent, Provider, WebhookError

API = "https://api.stripe.com/v1"
TOLERANCE = 300  # seconds


class StripeProvider(Provider):
    name = "stripe"

    def __init__(self, settings):
        self.settings = settings

    def _post(self, path: str, data: dict) -> dict:
        r = httpx.post(f"{API}{path}", data=data, auth=(self.settings.stripe_secret_key, ""), timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"Stripe error {r.status_code}: {r.text[:500]}")
        return r.json()

    def checkout_url(self, org, plan_id, email, success_url, cancel_url) -> str:
        plan = self.settings.plan(plan_id)
        if not plan.stripe_price_id:
            raise RuntimeError(f"Set STRIPE_PRICE_{plan_id.upper()} to a Stripe price id.")
        session = self._post("/checkout/sessions", {
            "mode": "subscription", "line_items[0][price]": plan.stripe_price_id, "line_items[0][quantity]": 1,
            "success_url": success_url, "cancel_url": cancel_url, "client_reference_id": str(org.id),
            "customer_email": email, "metadata[org_id]": str(org.id), "metadata[plan]": plan_id,
            "subscription_data[metadata][org_id]": str(org.id), "subscription_data[metadata][plan]": plan_id,
        })
        return session["url"]

    def verify(self, body: bytes, header: str) -> None:
        parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
        ts = parts.get("t")
        sigs = [v for k, v in (p.split("=", 1) for p in header.split(",") if "=" in p) if k == "v1"]
        if not ts or not sigs:
            raise WebhookError("missing signature")
        if abs(time.time() - int(ts)) > TOLERANCE:
            raise WebhookError("timestamp outside tolerance")
        expected = hmac.new(self.settings.stripe_webhook_secret.encode(), f"{ts}.".encode() + body,
                            hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, s) for s in sigs):
            raise WebhookError("bad signature")

    def parse_webhook(self, body: bytes, headers: dict) -> list[BillingEvent]:
        self.verify(body, headers.get("stripe-signature", ""))
        ev = json.loads(body)
        obj = ev["data"]["object"]
        t = ev["type"]

        def period_end(o) -> datetime | None:
            end = o.get("current_period_end") or (o.get("items", {}).get("data") or [{}])[0].get("current_period_end")
            return datetime.fromtimestamp(end, timezone.utc) if end else None

        meta = obj.get("metadata") or {}
        org_id = int(meta["org_id"]) if meta.get("org_id") else (
            int(obj["client_reference_id"]) if obj.get("client_reference_id") else None)
        if t == "checkout.session.completed":
            return [BillingEvent("stripe", ev["id"], org_id, "activated", meta.get("plan"), "active",
                                 obj.get("customer") or "", obj.get("subscription") or "")]
        if t in ("customer.subscription.updated", "customer.subscription.created"):
            status = {"active": "active", "trialing": "trialing", "past_due": "past_due", "unpaid": "past_due",
                      "canceled": "canceled", "incomplete": "past_due"}.get(obj.get("status"), "active")
            return [BillingEvent("stripe", ev["id"], org_id, "updated", meta.get("plan"), status,
                                 obj.get("customer") or "", obj.get("id") or "", period_end(obj),
                                 bool(obj.get("cancel_at_period_end")))]
        if t == "customer.subscription.deleted":
            return [BillingEvent("stripe", ev["id"], org_id, "canceled", subscription_ref=obj.get("id") or "")]
        if t == "invoice.payment_failed":
            return [BillingEvent("stripe", ev["id"], None, "payment_failed", status="past_due",
                                 subscription_ref=obj.get("subscription") or "")]
        return []

    def cancel(self, sub) -> None:
        self._post(f"/subscriptions/{sub.subscription_ref}", {"cancel_at_period_end": "true"})
        sub.cancel_at_period_end = True
