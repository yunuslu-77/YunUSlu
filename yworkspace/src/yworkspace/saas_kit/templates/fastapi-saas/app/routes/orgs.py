"""Dashboard, team members, invitations, roles, switching teams."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import emails
from ..deps import (
    EMAIL_RX,
    audit,
    check_csrf,
    current_membership,
    current_user,
    db,
    login_response,
    redirect,
    render,
    require_role,
    require_user,
)
from ..i18n import t
from ..models import ROLES, Invite, Membership, User
from ..security import new_token, token_hash

router = APIRouter()


@router.get("/dashboard")
def dashboard(request: Request, user=Depends(require_user), m: Membership = Depends(current_membership),
              s: Session = Depends(db)):
    orgs = s.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    return render(request, "dashboard.html", user, membership=m, org=m.org, memberships=orgs)


@router.get("/orgs/switch/{org_id}")
def switch(org_id: int, request: Request, user=Depends(require_user), s: Session = Depends(db)):
    m = s.scalar(select(Membership).where(Membership.user_id == user.id, Membership.org_id == org_id))
    if m is None:
        raise HTTPException(403, t(user.lang, "forbidden"))
    return login_response(request, user, "/dashboard", org_id=org_id)


@router.get("/members")
def members(request: Request, user=Depends(require_user), m: Membership = Depends(current_membership),
            s: Session = Depends(db)):
    rows = s.scalars(select(Membership).where(Membership.org_id == m.org_id).order_by(Membership.id)).all()
    invites = s.scalars(select(Invite).where(Invite.org_id == m.org_id, Invite.accepted.is_(False))).all()
    return render(request, "members.html", user, membership=m, rows=rows, invites=invites, roles=ROLES)


@router.post("/members/invite", dependencies=[Depends(check_csrf)])
def invite(request: Request, email: str = Form(""), role: str = Form("member"), user=Depends(require_user),
           m: Membership = Depends(current_membership), s: Session = Depends(db)):
    require_role(m, "admin")
    email = email.strip().lower()
    if not EMAIL_RX.match(email) or role not in ROLES or (role == "owner" and m.role != "owner"):
        return redirect("/members", "bad_email")
    token, hashed = new_token()
    s.add(Invite(org_id=m.org_id, email=email, role=role, token_hash=hashed,
                 expires_at=datetime.now(timezone.utc) + timedelta(days=7)))
    audit(s, request, "invite", user, m.org, email)
    s.commit()
    base = request.app.state.settings.base_url
    emails.send(request.app.state.settings, email, f"{m.org.name}: {t(user.lang, 'invite')}",
                f"{base}/invite/accept?token={token}")
    return redirect("/members", "invite_sent")


@router.get("/invite/accept")
def accept(request: Request, token: str = "", user=Depends(current_user), s: Session = Depends(db)):
    if user is None:
        return redirect(f"/login?next=/invite/accept?token={token}")
    inv = s.scalar(select(Invite).where(Invite.token_hash == token_hash(token)))
    expires = inv.expires_at if inv and inv.expires_at.tzinfo else (inv.expires_at.replace(tzinfo=timezone.utc)
                                                                    if inv else None)
    if inv is None or inv.accepted or expires < datetime.now(timezone.utc) or inv.email != user.email:
        return redirect("/dashboard", "link_invalid")
    exists = s.scalar(select(Membership).where(Membership.user_id == user.id, Membership.org_id == inv.org_id))
    if not exists:
        s.add(Membership(user_id=user.id, org_id=inv.org_id, role=inv.role))
    inv.accepted = True
    audit(s, request, "invite_accepted", user, detail=str(inv.org_id))
    s.commit()
    return login_response(request, user, "/dashboard", "invite_accepted", inv.org_id)


def _owners(s: Session, org_id: int) -> int:
    return s.scalar(select(func.count()).select_from(Membership).where(Membership.org_id == org_id,
                                                                       Membership.role == "owner"))


@router.post("/members/{member_id}/role", dependencies=[Depends(check_csrf)])
def change_role(member_id: int, request: Request, role: str = Form(...), user=Depends(require_user),
                m: Membership = Depends(current_membership), s: Session = Depends(db)):
    require_role(m, "owner")
    target = s.get(Membership, member_id)
    if target is None or target.org_id != m.org_id or role not in ROLES:
        raise HTTPException(404)
    if target.role == "owner" and role != "owner" and _owners(s, m.org_id) <= 1:
        return redirect("/members", "last_owner")
    target.role = role
    audit(s, request, "role_changed", user, m.org, f"{target.user.email} -> {role}")
    s.commit()
    return redirect("/members")


@router.post("/members/{member_id}/remove", dependencies=[Depends(check_csrf)])
def remove(member_id: int, request: Request, user=Depends(require_user), m: Membership = Depends(current_membership),
           s: Session = Depends(db)):
    target = s.get(Membership, member_id)
    if target is None or target.org_id != m.org_id:
        raise HTTPException(404)
    if target.user_id != user.id:
        require_role(m, "admin")
    if target.role == "owner" and _owners(s, m.org_id) <= 1:
        return redirect("/members", "last_owner")
    audit(s, request, "member_removed", user, m.org, s.get(User, target.user_id).email)
    s.delete(target)
    s.commit()
    return redirect("/members")
