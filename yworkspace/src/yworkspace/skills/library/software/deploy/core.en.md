- Deployment always needs the user's explicit approval. Show what will be created/changed and what it costs.
- VPS: Docker Compose + Caddy (automatic HTTPS) behind a firewall (ufw: 22, 80, 443 only), a non-root
  deploy user, SSH keys only, unattended security upgrades.
- Platforms: Vercel/Netlify (frontends, Next.js), Railway/Render/Fly.io (containers + managed Postgres).
- Secrets go to the platform's secret store or a server-side `.env` with 600 permissions - never into git.
- Database: managed Postgres (Neon, Supabase) or Postgres on the VPS with automated off-site backups.
- After deploying: open the live URL, walk the main journey, check logs and `/health`.
- Keep a rollback: previous image tag / previous deployment, and migrations that can be reversed.
