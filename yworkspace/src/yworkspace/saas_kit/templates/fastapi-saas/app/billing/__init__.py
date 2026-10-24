"""Billing providers behind one interface. The provider's webhook / server-side check is the source of truth."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Organization, ProcessedEvent, Subscription
from ..settings import Settings


@dataclass
class BillingEvent:
    """Normalized event: what happened to which organization's subscription."""
    provider: str
    event_id: str
    org_id: int | None
    kind: str  # activated | updated | canceled | payment_failed
    plan: str | None = None
    status: str | None = None
    customer_ref: str = ""
    subscription_ref: str = ""
    current_period_end: datetime | None = None
    cancel_at_period_end: bool | None = None


class WebhookError(Exception):
    pass


class Provider(ABC):
    name = "base"

    @abstractmethod
    def checkout_url(self, org: Organization, plan_id: str, email: str, success_url: str, cancel_url: str) -> str:
        """URL of the provider's hosted payment page for this organization and plan."""

    @abstractmethod
    def parse_webhook(self, body: bytes, headers: dict) -> list[BillingEvent]:
        """Verify a webhook (signature or server-side re-read) and turn it into normalized events."""

    @abstractmethod
    def cancel(self, sub: Subscription) -> None:
        """Cancel at the end of the current period."""


def get_provider(settings: Settings) -> Provider:
    if settings.billing_provider == "stripe":
        from .stripe import StripeProvider
        return StripeProvider(settings)
    if settings.billing_provider == "iyzico":
        from .iyzico import IyzicoProvider
        return IyzicoProvider(settings)
    from .fake import FakeProvider
    return FakeProvider(settings)


def apply_event(s: Session, ev: BillingEvent) -> bool:
    """Apply an event once. Returns False if it was already processed."""
    try:
        s.add(ProcessedEvent(provider=ev.provider, event_id=ev.event_id))
        s.flush()
    except IntegrityError:
        s.rollback()
        return False
    sub = None
    if ev.org_id is not None:
        sub = s.scalar(select(Subscription).where(Subscription.org_id == ev.org_id))
    if sub is None and ev.subscription_ref:
        sub = s.scalar(select(Subscription).where(Subscription.subscription_ref == ev.subscription_ref))
    if sub is None:
        s.commit()
        return True
    sub.provider = ev.provider
    if ev.customer_ref:
        sub.customer_ref = ev.customer_ref
    if ev.subscription_ref:
        sub.subscription_ref = ev.subscription_ref
    if ev.plan:
        sub.plan = ev.plan
    if ev.status:
        sub.status = ev.status
    if ev.current_period_end:
        sub.current_period_end = ev.current_period_end
    if ev.cancel_at_period_end is not None:
        sub.cancel_at_period_end = ev.cancel_at_period_end
    if ev.kind == "canceled":
        sub.plan, sub.status = "free", "canceled"
    s.commit()
    return True


def has_plan(org: Organization, plan_id: str) -> bool:
    sub = org.subscription
    return bool(sub and sub.plan == plan_id and sub.status in ("active", "trialing"))
