"""SaaS Kit tools: start a project from a tested template, and list the modules each stack offers."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..core.errors import ToolError
from ..extensions import register
from ..tools.registry import SAFE, WRITE, Tool, obj

TEMPLATES = Path(__file__).parent / "templates"

CATALOG = {
    "fastapi-saas": {
        "stack": "Python · FastAPI · SQLAlchemy · Jinja (server-rendered) · PostgreSQL",
        "modules": ["auth (signup, login, verify e-mail, reset password)", "teams + invitations + roles",
                    "billing: test mode, Stripe, iyzico", "admin panel + audit log", "KVKK/GDPR export + delete",
                    "TR/EN", "Docker + compose (Postgres, Mailpit)", "tests (15)"],
        "status": "ready, tested",
    },
}
RECIPES = {
    "nextjs-saas": "Next.js App Router + Auth.js + Prisma + Stripe: build with the nextjs, auth, payments, "
                   "database skills (no bundled template yet).",
    "django-saas": "Django + allauth + dj-stripe or webhooks: build with the python-django, auth, payments skills.",
    "nestjs-react": "NestJS API + React (Vite) frontend: build with the node-api, react-frontend, auth skills.",
    "flutter-client": "Flutter app talking to the SaaS API: flutter + api-design skills.",
    "kotlin-client": "Kotlin/Compose Android app talking to the SaaS API: kotlin-android + api-design skills.",
}


def copy_template(name: str, dest: Path, project_name: str) -> list[str]:
    src = TEMPLATES / name
    if not src.is_dir():
        raise ToolError("no_template", f"No template {name}.", f"Available: {', '.join(CATALOG)}")
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for f in sorted(src.rglob("*")):
        if f.is_dir() or "__pycache__" in f.parts or f.suffix in (".pyc", ".db"):
            continue
        rel = f.relative_to(src)
        target = dest / rel
        if target.exists():
            raise ToolError("exists", f"{rel} already exists in the project.", "Use an empty project folder.")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = f.read_text("utf-8")
            target.write_text(text.replace("{{project_name}}", project_name), "utf-8")
        except UnicodeDecodeError:
            shutil.copy2(f, target)
        written.append(rel.as_posix())
    return written


@register
def install(session) -> None:
    reg, ws = session.registry, session.workspace

    def saas_templates() -> str:
        lines = ["Ready templates:"]
        for k, v in CATALOG.items():
            lines.append(f"- {k} [{v['status']}]: {v['stack']}\n    modules: " + "; ".join(v["modules"]))
        lines.append("\nRecipes (built with skills, no bundled template):")
        lines += [f"- {k}: {v}" for k, v in RECIPES.items()]
        return "\n".join(lines)

    def saas_new(template: str, project_name: str, folder: str = ".") -> str:
        dest = ws.resolve(folder)
        files = copy_template(template, dest, project_name)
        for f in files:  # let the AI edit them without re-reading every file first
            ws._seen.pop(f, None)
        return (f"Created {len(files)} files from {template} in {folder}.\nNext: install requirements with "
                "`pip install -r requirements.txt`, run `python -m pytest -q`, then start it with start_process: "
                "`uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`.\n" + "\n".join(files))

    reg.register(Tool("saas_templates", "List SaaS starter templates and stack recipes.", obj({}), saas_templates,
                      SAFE, "saas"))
    reg.register(Tool("saas_new", "Start a SaaS from a tested template (auth, teams, billing, admin, KVKK...).",
                      obj({"template": {"type": "string"}, "project_name": {"type": "string"},
                           "folder": {"type": "string"}}, ["template", "project_name"]), saas_new, WRITE, "saas"))
