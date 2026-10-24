"""Application factory. Run: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from .db import Database
from .deps import LoginRequired
from .security import RateLimiter, SessionSigner
from .settings import Settings

HERE = Path(__file__).parent
log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if settings.secret_key == "dev-only-change-me" and settings.base_url.startswith("https://"):
        raise RuntimeError("Set SECRET_KEY before running in production.")
    app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.db.create_all()
    app.state.signer = SessionSigner(settings.secret_key)
    app.state.templates = Jinja2Templates(directory=str(HERE / "templates"))
    app.state.login_limiter = RateLimiter(settings.login_rate_per_minute)
    from .billing import get_provider
    app.state.billing = get_provider(settings)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        request.state.new_seed = request.cookies.get("seed") or secrets.token_urlsafe(16)
        response = await call_next(request)
        if not request.cookies.get("seed"):
            response.set_cookie("seed", request.state.new_seed, httponly=True, samesite="lax",
                                secure=settings.secure_cookies)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy",
                                    "default-src 'self'; style-src 'self'; frame-ancestors 'none'; form-action 'self' "
                                    "https://checkout.stripe.com https://*.iyzipay.com")
        if settings.secure_cookies:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    @app.exception_handler(LoginRequired)
    async def to_login(request: Request, exc: LoginRequired):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"error": {"code": "unauthenticated", "message": "Log in first."}}, 401)
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)

    @app.get("/health", response_class=PlainTextResponse)
    def health():
        return "ok"

    @app.get("/ready")
    def ready():
        with app.state.db.engine.connect() as c:
            c.execute(text("select 1"))
        return {"ready": True}

    from .routes import account, admin, auth, billing, orgs
    for r in (auth.router, orgs.router, billing.router, account.router, admin.router):
        app.include_router(r)

    @app.get("/")
    def home(request: Request):
        from .deps import session_data
        return RedirectResponse("/dashboard" if session_data(request).get("uid") else "/login", status_code=303)

    return app

