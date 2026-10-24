"""iyzico subscription checkout form (Türkiye). The callback's token is verified server-to-server, which is
the source of truth. Implemented from iyzico's v2 API documentation: test it in the sandbox
(IYZICO_BASE_URL=https://sandbox-api.iyzipay.com) with your sandbox keys before going live."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

import httpx

from . import BillingEvent, Provider, WebhookError


class IyzicoProvider(Provider):
    name = "iyzico"

    def __init__(self, settings):
        self.settings = settings

    def _auth_headers(self, path: str, body: str) -> dict:
        rnd = f"{int(time.time() * 1000)}{secrets.token_hex(4)}"
        signature = hmac.new(self.settings.iyzico_secret_key.encode(), (rnd + path + body).encode(),
                             hashlib.sha256).hexdigest()
        auth = f"apiKey:{self.settings.iyzico_api_key}&randomKey:{rnd}&signature:{signature}"
        return {"Authorization": "IYZWSv2 " + base64.b64encode(auth.encode()).decode(), "x-iyzi-rnd": rnd,
                "Content-Type": "application/json"}

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) if payload is not None else ""
        r = httpx.request(method, self.settings.iyzico_base_url + path, content=body.encode() if body else None,
                          headers=self._auth_headers(path, body), timeout=30)
        data = r.json()
        if r.status_code >= 400 or data.get("status") == "failure":
            raise RuntimeError(f"iyzico error: {data.get('errorMessage') or r.text[:300]}")
        return data

    def checkout_url(self, org, plan_id, email, success_url, cancel_url) -> str:
        plan = self.settings.plan(plan_id)
        if not plan.iyzico_plan_code:
            raise RuntimeError(f"Set IYZICO_PLAN_{plan_id.upper()} to an iyzico pricing plan reference code.")
        data = self._call("POST", "/v2/subscription/checkoutform/initialize", {
            "locale": "tr", "conversationId": f"org-{org.id}",
            "callbackUrl": f"{self.settings.base_url}/billing/iyzico/callback?org={org.id}&plan={plan_id}",
            "pricingPlanReferenceCode": plan.iyzico_plan_code, "subscriptionInitialStatus": "ACTIVE",
            "customer": {"email": email, "name": org.name[:50] or "Musteri", "surname": "-",
                         "billingAddress": {"contactName": org.name[:50] or "Musteri", "city": "Istanbul",
                                            "country": "Turkey", "address": "-"}},
        })
        # iyzico returns a hosted page URL for the form.
        return data.get("paymentPageUrl") or data.get("checkoutFormContent", "")

    def retrieve(self, token: str, org_id: int, plan_id: str) -> list[BillingEvent]:
        data = self._call("GET", f"/v2/subscription/checkoutform/{token}")
        d = data.get("data") or {}
        status = (d.get("subscriptionStatus") or "").upper()
        if status != "ACTIVE":
            raise WebhookError(f"subscription not active: {status or 'unknown'}")
        return [BillingEvent("iyzico", f"checkout-{token}", org_id, "activated", plan_id, "active",
                             d.get("customerReferenceCode", ""), d.get("referenceCode", ""))]

    def parse_webhook(self, body: bytes, headers: dict) -> list[BillingEvent]:
        # iyzico subscription notifications are verified by re-reading the subscription from the API.
        d = json.loads(body or b"{}")
        ref = d.get("subscriptionReferenceCode")
        if not ref:
            raise WebhookError("missing subscriptionReferenceCode")
        sub = self._call("GET", f"/v2/subscription/subscriptions/{ref}").get("data") or {}
        status = {"ACTIVE": "active", "UNPAID": "past_due", "CANCELED": "canceled",
                  "EXPIRED": "canceled"}.get((sub.get("subscriptionStatus") or "").upper(), "active")
        kind = "canceled" if status == "canceled" else "updated"
        return [BillingEvent("iyzico", f"{ref}-{d.get('iyziEventTime', time.time())}", None, kind,
                             status=status, subscription_ref=ref)]

    def cancel(self, sub) -> None:
        self._call("POST", f"/v2/subscription/subscriptions/{sub.subscription_ref}/cancel", {})
        sub.cancel_at_period_end = True
