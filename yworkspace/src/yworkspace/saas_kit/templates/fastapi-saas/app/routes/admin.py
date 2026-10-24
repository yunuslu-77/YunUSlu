"""Back office for the people running the SaaS (SUPERADMIN_EMAILS)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import db, is_superadmin, render, require_user
from ..models import AuditLog, Organization, Subscription, User

router = APIRouter()


@router.get("/admin")
def admin(request: Request, user=Depends(require_user), s: Session = Depends(db)):
    if not is_superadmin(request, user):
        raise HTTPException(403)
    stats = {
        "users": s.scalar(select(func.count()).select_from(User)),
        "verified": s.scalar(select(func.count()).select_from(User).where(User.email_verified.is_(True))),
        "orgs": s.scalar(select(func.count()).select_from(Organization)),
        "paying": s.scalar(select(func.count()).select_from(Subscription).where(Subscription.plan != "free",
                                                                                 Subscription.status == "active")),
    }
    plans = {p.id: p.price_minor for p in request.app.state.settings.plans}
    paying = s.scalars(select(Subscription).where(Subscription.plan != "free", Subscription.status == "active")).all()
    mrr = sum(plans.get(x.plan, 0) for x in paying) / 100
    users = s.scalars(select(User).order_by(User.id.desc()).limit(50)).all()
    subs = s.scalars(select(Subscription).order_by(Subscription.id.desc()).limit(50)).all()
    logs = s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(100)).all()
    return render(request, "admin.html", user, stats=stats, mrr=mrr, users=users, subs=subs, logs=logs)
