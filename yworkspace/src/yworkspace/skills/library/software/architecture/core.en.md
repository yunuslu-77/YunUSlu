Default to boring, proven choices; complexity must earn its place.
- Small/medium SaaS: one monolith + one PostgreSQL database + a background job queue. No microservices.
- Full-stack TypeScript: Next.js (App Router) + Prisma or Drizzle + PostgreSQL.
- Python: FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL (API-first), or Django (admin-heavy, CRUD).
- Mobile: Flutter (one codebase) or Kotlin + Jetpack Compose (Android-only, native feel).
- Development DB may be SQLite only if production stays compatible; prefer PostgreSQL in Docker.
Structure by feature (users/, bookings/, billing/), not by layer only. Keep config in environment
variables, provide `.env.example`, and a one-command start (`docker compose up` or `npm run dev`).
Record every decision and its reason with memory_note.
