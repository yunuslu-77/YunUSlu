- Layout: `app/main.py` (create_app), `app/api/<feature>.py` (routers), `app/models.py`, `app/schemas.py`,
  `app/db.py` (engine + session dependency), `app/settings.py` (pydantic-settings), `tests/`.
- Pydantic v2 schemas for input/output; never return ORM objects with secrets (password hashes).
- SQLAlchemy 2.0 style (`select()`, `Session.execute`), Alembic migrations for every schema change.
- Dependencies for DB session and current user; check authorization inside each endpoint.
- Passwords: `argon2` or `bcrypt` via passlib/argon2-cffi. Tokens: short-lived JWT or server sessions.
- Errors: raise `HTTPException` with clear messages; add a handler for unexpected errors that logs them.
- Tests: `TestClient` (or httpx AsyncClient), a temporary database per test, factories for data.
- Run: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` with start_process.
