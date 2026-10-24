"""Sign up, log in/out, e-mail verification and password reset."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import emails
from ..deps import EMAIL_RX, audit, check_csrf, current_user, db, lang, login_response, redirect, render
from ..i18n import t
from ..models import Membership, OneTimeToken, Organization, Subscription, User
from ..security import hash_password, new_token, password_problem, token_hash, verify_password

router = APIRouter()


def _send_token(request: Request, s: Session, user: User, purpose: str) -> None:
    token, hashed = new_token()
    hours = 48 if purpose == "verify" else 1
    s.add(OneTimeToken(user_id=user.id, purpose=purpose, token_hash=hashed,
                       expires_at=datetime.now(timezone.utc) + timedelta(hours=hours)))
    s.commit()
    base = request.app.state.settings.base_url
    path = "verify" if purpose == "verify" else "reset"
    subject = t(user.lang, "check_email")
    emails.send(request.app.state.settings, user.email, subject, f"{base}/{path}?token={token}")


def _use_token(s: Session, token: str, purpose: str) -> OneTimeToken | None:
    row = s.scalar(select(OneTimeToken).where(OneTimeToken.token_hash == token_hash(token),
                                              OneTimeToken.purpose == purpose))
    if row is None or row.used:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    row.used = True
    return row


@router.get("/signup")
def signup_form(request: Request, user=Depends(current_user)):
    return render(request, "signup.html", user)


@router.post("/signup", dependencies=[Depends(check_csrf)])
def signup(request: Request, name: str = Form(""), email: str = Form(""), password: str = Form(""),
           org_name: str = Form(""), s: Session = Depends(db)):
    lg = lang(request)
    email = email.strip().lower()
    error = None
    if not EMAIL_RX.match(email):
        error = "bad_email"
    elif s.scalar(select(func.count()).select_from(User).where(User.email == email)):
        error = "email_taken"
    else:
        error = password_problem(password)
    if error:
        return render(request, "signup.html", status=400, error=t(lg, error), form={"name": name, "email": email,
                                                                                    "org_name": org_name})
    user = User(email=email, name=name.strip()[:120], password_hash=hash_password(password), lang=lg)
    org = Organization(name=(org_name.strip() or name.strip() or email.split("@")[0])[:120])
    s.add_all([user, org])
    s.flush()
    s.add_all([Membership(user_id=user.id, org_id=org.id, role="owner"), Subscription(org_id=org.id, plan="free")])
    audit(s, request, "signup", user, org)
    s.commit()
    _send_token(request, s, user, "verify")
    return login_response(request, user, "/dashboard", "verify_sent", org.id)


@router.get("/login")
def login_form(request: Request, user=Depends(current_user)):
    return render(request, "login.html", user, next=request.query_params.get("next", "/dashboard"))


@router.post("/login", dependencies=[Depends(check_csrf)])
def login(request: Request, email: str = Form(""), password: str = Form(""), next: str = Form("/dashboard"),
          s: Session = Depends(db)):
    lg = lang(request)
    email = email.strip().lower()
    ip = request.client.host if request.client else "?"
    if not request.app.state.login_limiter.allow(f"{ip}|{email}"):
        return render(request, "login.html", status=429, error=t(lg, "too_many"), next=next)
    user = s.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        audit(s, request, "login_failed", user, detail=email)
        s.commit()
        return render(request, "login.html", status=400, error=t(lg, "bad_login"), next=next)
    audit(s, request, "login", user)
    s.commit()
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/dashboard"
    return login_response(request, user, safe_next)


@router.post("/logout", dependencies=[Depends(check_csrf)])
def logout(request: Request):
    resp = redirect("/login")
    resp.delete_cookie("session")
    return resp


@router.get("/verify")
def verify(request: Request, token: str = "", s: Session = Depends(db), user=Depends(current_user)):
    row = _use_token(s, token, "verify")
    if row is None:
        return redirect("/dashboard" if user else "/login", "link_invalid")
    u = s.get(User, row.user_id)
    u.email_verified = True
    audit(s, request, "email_verified", u)
    s.commit()
    return redirect("/dashboard" if user else "/login", "verified")


@router.post("/verify/resend", dependencies=[Depends(check_csrf)])
def resend(request: Request, s: Session = Depends(db), user=Depends(current_user)):
    if user is None:
        return redirect("/login")
    if not user.email_verified:
        _send_token(request, s, s.get(User, user.id), "verify")
    return redirect("/dashboard", "verify_sent")


@router.get("/forgot")
def forgot_form(request: Request):
    return render(request, "forgot.html")


@router.post("/forgot", dependencies=[Depends(check_csrf)])
def forgot(request: Request, email: str = Form(""), s: Session = Depends(db)):
    user = s.scalar(select(User).where(User.email == email.strip().lower()))
    if user is not None:
        _send_token(request, s, user, "reset")
    return redirect("/login", "reset_sent")  # same answer whether or not the address exists


@router.get("/reset")
def reset_form(request: Request, token: str = ""):
    return render(request, "reset.html", token=token)


@router.post("/reset", dependencies=[Depends(check_csrf)])
def reset(request: Request, token: str = Form(""), password: str = Form(""), s: Session = Depends(db)):
    lg = lang(request)
    problem = password_problem(password)
    if problem:
        return render(request, "reset.html", status=400, token=token, error=t(lg, problem))
    row = _use_token(s, token, "reset")
    if row is None:
        return redirect("/forgot", "link_invalid")
    user = s.get(User, row.user_id)
    user.password_hash = hash_password(password)
    user.session_version += 1  # log out every other session
    audit(s, request, "password_reset", user)
    s.commit()
    return redirect("/login", "reset_done")


@router.get("/lang/{code}")
def set_lang(code: str, request: Request, s: Session = Depends(db), user=Depends(current_user)):
    code = code if code in ("tr", "en") else "tr"
    if user is not None:
        s.get(User, user.id).lang = code
        s.commit()
    back = request.headers.get("referer") or "/"
    resp = redirect(back if back.startswith(request.app.state.settings.base_url) or back.startswith("/") else "/")
    resp.set_cookie("lang", code, samesite="lax")
    return resp
