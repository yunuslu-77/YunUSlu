- Dockerfile: small official base image, non-root user, multi-stage build, pinned versions, `.dockerignore`,
  HEALTHCHECK. docker-compose for app + database + cache in development.
- CI (GitHub Actions): install → lint → typecheck → test → build on every push/PR; cache dependencies.
- Config via environment; twelve-factor style; one command to start locally.
- Logging: structured (JSON) logs with request ids; errors to an error tracker (Sentry-compatible, self-hosted ok).
- Health: `/health` (process up) and `/ready` (DB reachable).
- Backups: automated daily database backups, kept off the server, and a TESTED restore procedure.
- Zero-downtime deploys: run migrations before switching traffic; keep the previous version to roll back.
