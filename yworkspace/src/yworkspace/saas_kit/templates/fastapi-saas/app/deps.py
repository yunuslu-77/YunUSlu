"""Request helpers: database session, current user/org, roles, CSRF, rendering, audit."""

from __future__ import annotations

import hmac
import re
from collections.abc import Iterator

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .i18n import t
from .models import AuditLog, Membership, Organization, User
from .security import csrf_token

EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLE_RANK = {"member": 0, "admin": 1, "owner": 2}


class LoginRequired(Exception):
    pass


def db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def session_data(request: Request) -> dict:
    raw = request.cookies.get("session")
    return (request.app.state.signer.loads(raw) or {}) if raw else {}


def current_user(request: Request, s: Session = Depends(db)) -> User | None:
    data = session_data(request)
    uid = data.get("uid")
    if not uid:
        return None
    user = s.get(User, uid)
    if user is None or user.session_version != data.get("v"):
        return None
    return user


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise LoginRequired()
    return user


def lang(request: Request, user: User | None = None) -> str:
    if user is not None:
        return user.lang
    code = request.cookies.get("lang") or request.app.state.settings.default_lang
    return code if code in ("tr", "en") else "tr"


def current_membership(request: Request, user: User = Depends(require_user), s: Session = Depends(db)) -> Membership:
    """The membership for the org selected in the session (or the user's first org). Tenant isolation lives here."""
    org_id = session_data(request).get("org")
    q = select(Membership).where(Membership.user_id == user.id)
    if org_id:
        m = s.scalar(q.where(Membership.org_id == org_id))
        if m:
            return m
    m = s.scalar(q.order_by(Membership.id))
    if m is None:
        raise HTTPException(403, t(user.lang, "forbidden"))
    return m


def require_role(m: Membership, minimum: str) -> None:
    if ROLE_RANK[m.role] < ROLE_RANK[minimum]:
        raise HTTPException(403, t(m.user.lang, "forbidden"))


def is_superadmin(request: Request, user: User | None) -> bool:
    return bool(user and user.email in request.app.state.settings.superadmin_emails)


def csrf_value(request: Request) -> str:
    seed = request.cookies.get("seed") or request.state.new_seed
    return csrf_token(request.app.state.settings.secret_key, seed)


def check_csrf(request: Request, csrf: str = Form("")) -> None:
    if not hmac.compare_digest(csrf, csrf_value(request)):
        raise HTTPException(400, "CSRF check failed. Reload the page and try again.")


def render(request: Request, template: str, user: User | None = None, status: int = 200, **ctx) -> HTMLResponse:
    lg = lang(request, user)
    msg = request.query_params.get("msg")
    ctx.update(request=request, user=user, lang=lg, t=lambda k: t(lg, k), csrf=csrf_value(request),
               app_name=request.app.state.settings.app_name, flash=t(lg, msg) if msg else None,
               is_superadmin=is_superadmin(request, user))
    return request.app.state.templates.TemplateResponse(request, template, ctx, status_code=status)


def redirect(url: str, msg: str | None = None) -> RedirectResponse:
    sep = "&" if "?" in url else "?"
    return RedirectResponse(url + (f"{sep}msg={msg}" if msg else ""), status_code=303)


def login_response(request: Request, user: User, url: str, msg: str | None = None, org_id: int | None = None):
    resp = redirect(url, msg)
    value = request.app.state.signer.dumps({"uid": user.id, "v": user.session_version, "org": org_id})
    resp.set_cookie("session", value, httponly=True, samesite="lax", secure=request.app.state.settings.secure_cookies,
                    max_age=60 * 60 * 24 * 30)
    return resp


def audit(s: Session, request: Request, action: str, user: User | None = None, org: Organization | None = None,
          detail: str = "") -> None:
    ip = request.client.host if request.client else ""
    s.add(AuditLog(user_id=user.id if user else None, org_id=org.id if org else None, action=action,
                   detail=detail[:2000], ip=ip))
