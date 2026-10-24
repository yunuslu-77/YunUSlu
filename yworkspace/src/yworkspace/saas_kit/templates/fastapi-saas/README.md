# {{project_name}}

Built from the yWorkspace FastAPI SaaS starter.

## What is inside
- Sign up, log in, e-mail verification, password reset (single-use, expiring tokens; other sessions logged out)
- Teams (multi-tenant), invitations, roles (owner/admin/member), team switching
- Subscriptions: test mode (no real money), Stripe (hosted Checkout + signed webhooks), iyzico (subscription
  checkout form, verified server-to-server - test in the sandbox first). Webhooks are idempotent.
- Admin panel (users, teams, subscriptions, MRR, audit log) for `SUPERADMIN_EMAILS`
- KVKK/GDPR: download my data, delete my account
- Turkish / English, mobile friendly, dark mode, CSRF protection, Argon2 passwords, security headers,
  login rate limiting, `/health` and `/ready`

## Run
```
pip install -r requirements.txt
uvicorn app.main:create_app --factory --reload --port 8000
pytest -q
```
With Docker: `cp .env.example .env` (fill SECRET_KEY), then `docker compose up --build`.

## Going live
Switch `BILLING_PROVIDER` to `stripe` or `iyzico`, set the keys and price/plan ids, point the provider's webhook to
`https://your-domain/billing/webhook/stripe` (or the iyzico notification URL to `/billing/webhook/iyzico`).
Legal texts (privacy policy, KVKK disclosure, terms) must be prepared and reviewed for your business.
