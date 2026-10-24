"""Deployment targets. Each target prepares the files it needs, lists exact commands, and verifies the result.

Deploy commands run on the user's computer (not in the sandbox) because they use the user's own logins and
SSH keys, and they always require explicit approval.
"""

from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

EXTRA: list = []  # plugins add targets here


@dataclass
class DeployPlan:
    target: str
    files: dict[str, str] = field(default_factory=dict)  # path -> content to write
    commands: list[str] = field(default_factory=list)  # run in the project folder, in order
    needs: list[str] = field(default_factory=list)  # human prerequisites (accounts, DNS, tokens)
    missing: list[str] = field(default_factory=list)  # tools/credentials not found on this computer
    url: str = ""  # where to verify afterwards
    notes: list[str] = field(default_factory=list)

    def text(self) -> str:
        out = [f"Deploy target: {self.target}"]
        if self.files:
            out.append("Files to write: " + ", ".join(self.files))
        if self.commands:
            out.append("Commands:\n" + "\n".join(f"  $ {c}" for c in self.commands))
        if self.needs:
            out.append("You need:\n" + "\n".join(f"  - {n}" for n in self.needs))
        if self.missing:
            out.append("MISSING on this computer:\n" + "\n".join(f"  - {m}" for m in self.missing))
        if self.url:
            out.append(f"Will verify: {self.url}")
        out += [f"Note: {n}" for n in self.notes]
        return "\n".join(out)


def _need_cli(plan: DeployPlan, exe: str, install: str) -> None:
    if not shutil.which(exe):
        plan.missing.append(f"`{exe}` command ({install})")


def _need_env(plan: DeployPlan, var: str, how: str) -> None:
    if not os.environ.get(var):
        plan.needs.append(f"{var} ({how}) - or log in with the CLI first")


class Target(ABC):
    name = ""
    description = ""

    @abstractmethod
    def plan(self, root: Path, opts: dict) -> DeployPlan:
        """Files to write, commands to run, prerequisites and the URL to verify."""


class Vps(Target):
    name = "vps"
    description = "Your own server (Ubuntu/Debian VPS): Docker Compose + Caddy (automatic HTTPS) + firewall"

    def plan(self, root: Path, opts: dict) -> DeployPlan:
        host, user = opts.get("host", ""), opts.get("user", "root")
        domain = opts.get("domain", "")
        port = int(opts.get("app_port", 8000))
        remote = opts.get("remote_dir", "/opt/app")
        p = DeployPlan(self.name, url=f"https://{domain}/health" if domain else "")
        if not host or not domain:
            p.needs.append("options host (server IP or name) and domain (e.g. app.example.com)")
        p.needs += [f"A DNS A record: {domain or '<domain>'} → {host or '<server IP>'}",
                    f"SSH access as {user}@{host or '<host>'} with your key",
                    ".env.production in the project (secrets for the server; never committed)"]
        _need_cli(p, "ssh", "OpenSSH client")
        _need_cli(p, "rsync", "rsync")
        app_service = opts.get("service", "app")
        p.files["deploy/Caddyfile"] = f"{domain or 'example.com'} {{\n    encode gzip\n    reverse_proxy {app_service}:{port}\n}}\n"
        p.files["docker-compose.prod.yml"] = (
            "# Production overrides: Caddy terminates HTTPS; the app is not exposed directly.\n"
            "services:\n"
            f"  {app_service}:\n    env_file: .env.production\n    restart: unless-stopped\n    ports: !reset []\n"
            "  caddy:\n    image: caddy:2\n    restart: unless-stopped\n    ports: [\"80:80\", \"443:443\"]\n"
            "    volumes:\n      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro\n      - caddy_data:/data\n"
            f"    depends_on: [{app_service}]\n"
            "volumes:\n  caddy_data:\n")
        p.files["deploy/server-setup.sh"] = (
            "#!/usr/bin/env bash\n# One-time server preparation (run by deploy.sh over SSH).\nset -euo pipefail\n"
            "command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh\n"
            "if command -v ufw >/dev/null; then ufw allow OpenSSH; ufw allow 80/tcp; ufw allow 443/tcp; "
            "ufw --force enable; fi\n"
            "apt-get install -y unattended-upgrades >/dev/null 2>&1 || true\n")
        target = f"{user}@{host}"
        p.files["deploy/deploy.sh"] = (
            "#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")/..\"\n"
            f"ssh {target} 'bash -s' < deploy/server-setup.sh\n"
            f"ssh {target} 'mkdir -p {remote}'\n"
            f"rsync -az --delete --exclude .git --exclude .yw --exclude node_modules --exclude .env ./ {target}:{remote}/\n"
            f"rsync -az .env.production {target}:{remote}/.env.production\n"
            f"ssh {target} 'chmod 600 {remote}/.env.production && cd {remote} && "
            "docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build'\n")
        p.commands = ["bash deploy/deploy.sh"]
        if not (root / ".env.production").exists():
            p.missing.append(".env.production (copy .env.example, fill real values, keep it out of git)")
        p.notes.append("Rollback: re-run deploy.sh from the previous git commit (git checkout <commit>).")
        return p


class Vercel(Target):
    name = "vercel"
    description = "Vercel (Next.js and static frontends)"

    def plan(self, root, opts):
        p = DeployPlan(self.name, commands=["npx --yes vercel@latest deploy --prod --yes"])
        _need_cli(p, "npx", "Node.js")
        _need_env(p, "VERCEL_TOKEN", "vercel.com → Account Settings → Tokens")
        p.notes.append("Set environment variables in the Vercel project settings (or `vercel env add`).")
        p.url = opts.get("url", "")
        return p


class Netlify(Target):
    name = "netlify"
    description = "Netlify (static sites and frontends)"

    def plan(self, root, opts):
        d = opts.get("dir", "dist")
        p = DeployPlan(self.name, commands=[f"npx --yes netlify-cli deploy --prod --dir {d}"], url=opts.get("url", ""))
        _need_cli(p, "npx", "Node.js")
        _need_env(p, "NETLIFY_AUTH_TOKEN", "app.netlify.com → User settings → Applications")
        return p


class Railway(Target):
    name = "railway"
    description = "Railway (containers + managed PostgreSQL)"

    def plan(self, root, opts):
        p = DeployPlan(self.name, commands=["railway up --detach"], url=opts.get("url", ""))
        _need_cli(p, "railway", "npm i -g @railway/cli")
        _need_env(p, "RAILWAY_TOKEN", "railway.app → Project → Settings → Tokens")
        return p


class Render(Target):
    name = "render"
    description = "Render (deploys from your Git repository using render.yaml)"

    def plan(self, root, opts):
        name = opts.get("service", root.name.lower())
        p = DeployPlan(self.name, url=opts.get("url", ""))
        p.files["render.yaml"] = (
            "services:\n"
            f"  - type: web\n    name: {name}\n    runtime: docker\n    healthCheckPath: /health\n"
            "    envVars:\n      - key: DATABASE_URL\n        fromDatabase: {name: db, property: connectionString}\n"
            "      - key: SECRET_KEY\n        generateValue: true\n"
            "databases:\n  - name: db\n    plan: free\n")
        p.commands = ["git add render.yaml", "git commit -m 'Add Render blueprint'", "git push"]
        p.needs.append("A Render account connected to this Git repository (New → Blueprint)")
        return p


class Fly(Target):
    name = "fly"
    description = "Fly.io (containers close to users)"

    def plan(self, root, opts):
        p = DeployPlan(self.name, url=opts.get("url", ""))
        if not (root / "fly.toml").exists():
            p.commands.append("fly launch --no-deploy --copy-config --yes")
        p.commands.append("fly deploy")
        _need_cli(p, "fly", "https://fly.io/docs/flyctl/install/")
        _need_env(p, "FLY_API_TOKEN", "fly auth token")
        return p


class CloudflarePages(Target):
    name = "cloudflare-pages"
    description = "Cloudflare Pages (static sites)"

    def plan(self, root, opts):
        d = opts.get("dir", "dist")
        project = opts.get("project", root.name.lower())
        p = DeployPlan(self.name, commands=[f"npx --yes wrangler pages deploy {d} --project-name {project}"],
                       url=opts.get("url", ""))
        _need_cli(p, "npx", "Node.js")
        _need_env(p, "CLOUDFLARE_API_TOKEN", "dash.cloudflare.com → My Profile → API Tokens")
        return p


def all_targets() -> dict[str, Target]:
    items = [Vps(), Vercel(), Netlify(), Railway(), Render(), Fly(), CloudflarePages(), *EXTRA]
    return {t.name: t for t in items}
