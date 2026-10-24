"""My account: language, KVKK/GDPR data export, account deletion; JSON /api/me."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import audit, check_csrf, db, redirect, render, require_user
from ..i18n import t
from ..models import AuditLog, Membership, Organization, User

router = APIRouter()


@router.get("/account")
def account(request: Request, user=Depends(require_user)):
    return render(request, "account.html", user)


@router.get("/account/export")
def export(request: Request, user=Depends(require_user), s: Session = Depends(db)):
    memberships = s.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    logs = s.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.id)).all()
    data = {
        "user": {"email": user.email, "name": user.name, "language": user.lang, "email_verified": user.email_verified,
                 "created_at": user.created_at.isoformat()},
        "teams": [{"team": m.org.name, "role": m.role} for m in memberships],
        "activity": [{"at": a.at.isoformat(), "action": a.action, "ip": a.ip} for a in logs],
    }
    audit(s, request, "data_export", user)
    s.commit()
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=my-data.json"})


@router.post("/account/delete", dependencies=[Depends(check_csrf)])
def delete(request: Request, confirm: str = Form(""), user=Depends(require_user), s: Session = Depends(db)):
    if confirm.strip().lower() != user.email:
        return render(request, "account.html", user, status=400, error=t(user.lang, "confirm_delete"))
    u = s.get(User, user.id)
    for m in list(u.memberships):
        org = s.get(Organization, m.org_id)
        others = s.scalar(select(func.count()).select_from(Membership).where(Membership.org_id == org.id,
                                                                             Membership.user_id != u.id))
        if not others:
            s.delete(org)  # the user was the only member: the team goes too
        elif m.role == "owner":
            heir = s.scalar(select(Membership).where(Membership.org_id == org.id, Membership.user_id != u.id)
                            .order_by(Membership.id))
            heir.role = "owner"
    audit(s, request, "account_deleted", None, detail=f"user {u.id}")
    s.delete(u)
    s.commit()
    resp = redirect("/login", "deleted")
    resp.delete_cookie("session")
    return resp


@router.get("/api/me")
def me(user=Depends(require_user)):
    return {"email": user.email, "name": user.name, "language": user.lang, "email_verified": user.email_verified}
