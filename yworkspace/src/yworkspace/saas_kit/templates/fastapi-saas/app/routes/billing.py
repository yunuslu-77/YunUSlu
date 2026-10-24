"""Plans, checkout, provider webhooks, cancellation. Test mode (fake provider) needs no external account."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..billing import WebhookError, apply_event
from ..deps import audit, check_csrf, current_membership, db, redirect, render, require_role, require_user
from ..models import Membership

router = APIRouter()


@router.get("/billing")
def billing(request: Request, user=Depends(require_user), m: Membership = Depends(current_membership)):
    st = request.app.state.settings
    return render(request, "billing.html", user, membership=m, sub=m.org.subscription, plans=st.plans,
                  provider=request.app.state.billing.name)


@router.post("/billing/checkout/{plan_id}", dependencies=[Depends(check_csrf)])
def checkout(plan_id: str, request: Request, user=Depends(require_user), m: Membership = Depends(current_membership),
             s: Session = Depends(db)):
    require_role(m, "admin")
    st = request.app.state.settings
    try:
        plan = st.plan(plan_id)
    except KeyError as e:
        raise HTTPException(404) from e
    if plan.price_minor == 0:
        return redirect("/billing")
    url = request.app.state.billing.checkout_url(m.org, plan_id, user.email, f"{st.base_url}/billing?msg=paid",
                                                 f"{st.base_url}/billing")
    audit(s, request, "checkout_started", user, m.org, plan_id)
    s.commit()
    return redirect(url)


@router.get("/billing/fake-pay")
def fake_pay_page(request: Request, user=Depends(require_user), m: Membership = Depends(current_membership)):
    if request.app.state.billing.name != "fake":
        raise HTTPException(404)
    return render(request, "fake_pay.html", user, plan=request.query_params.get("plan", "pro"), org=m.org)


@router.post("/billing/fake-pay", dependencies=[Depends(check_csrf)])
def fake_pay(request: Request, plan: str = Form("pro"), user=Depends(require_user),
             m: Membership = Depends(current_membership), s: Session = Depends(db)):
    provider = request.app.state.billing
    if provider.name != "fake":
        raise HTTPException(404)
    require_role(m, "admin")
    body, headers = provider.make_event(m.org_id, plan)
    for ev in provider.parse_webhook(body, headers):
        apply_event(s, ev)
    return redirect("/billing", "paid")


@router.post("/billing/webhook/{provider_name}")
async def webhook(provider_name: str, request: Request, s: Session = Depends(db)):
    provider = request.app.state.billing
    if provider_name != provider.name:
        return JSONResponse({"error": "unknown provider"}, 404)
    body = await request.body()
    try:
        events = provider.parse_webhook(body, {k.lower(): v for k, v in request.headers.items()})
    except WebhookError as e:
        return JSONResponse({"error": str(e)}, 400)
    applied = sum(apply_event(s, ev) for ev in events)
    return {"received": len(events), "applied": applied}


@router.api_route("/billing/iyzico/callback", methods=["GET", "POST"])
async def iyzico_callback(request: Request, s: Session = Depends(db)):
    provider = request.app.state.billing
    if provider.name != "iyzico":
        raise HTTPException(404)
    form = await request.form()
    token = form.get("token") or request.query_params.get("token", "")
    org_id = int(request.query_params.get("org", "0"))
    plan = request.query_params.get("plan", "pro")
    try:
        for ev in provider.retrieve(token, org_id, plan):
            apply_event(s, ev)
    except (WebhookError, RuntimeError):
        return redirect("/billing", "link_invalid")
    return redirect("/billing", "paid")


@router.post("/billing/cancel", dependencies=[Depends(check_csrf)])
def cancel(request: Request, user=Depends(require_user), m: Membership = Depends(current_membership),
           s: Session = Depends(db)):
    require_role(m, "owner")
    sub = m.org.subscription
    if sub is None or sub.plan == "free":
        return redirect("/billing")
    request.app.state.billing.cancel(sub)
    audit(s, request, "subscription_cancel", user, m.org)
    s.add(sub)
    s.commit()
    return redirect("/billing", "canceled")
