"""Adopting an existing project: discover, map, run, document, protect with characterization tests,
report its health, and plan a migration step by step."""

from __future__ import annotations

import json

from ..core.errors import ToolError
from ..extensions import register
from ..tools.registry import EXEC, SAFE, WRITE, Tool, obj
from . import discover as dsc
from . import golden

S = {"type": "string"}


@register
def install(session) -> None:
    reg, ws = session.registry, session.workspace

    def write(path: str, content: str) -> None:
        full = ws.root / path
        if full.exists():
            if full.read_text("utf-8", "replace") == content:
                return
            ws.read(path)
        ws.create(path, content, overwrite=full.exists())

    def save_internal(name: str, data) -> None:
        d = ws.root / ".yw" / "adopt"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=list), "utf-8")

    def adopt_discover() -> str:
        d = dsc.discover(ws.root)
        save_internal("discovery.json", d.__dict__)
        return (d.text() + "\n\nNext: adopt_map (structure), adopt_run (make it run in the sandbox), "
                "adopt_golden (record current behaviour), adopt_health, then adopt_docs.")

    def adopt_map(depth: int = 2) -> str:
        parts = []
        py = dsc.python_imports(ws.root)
        js = dsc.js_imports(ws.root)
        for label, graph, sep in (("Python modules", py, "."), ("JS/TS files", js, "/")):
            if not graph:
                continue
            grouped = dsc.group_graph(graph, depth, sep)
            parts.append(f"## {label} ({len(graph)}; grouped to {len(grouped)})\n```mermaid\n"
                         f"{dsc.mermaid(grouped)}\n```")
            fan_in: dict[str, int] = {}
            for deps in graph.values():
                for b in deps:
                    fan_in[b] = fan_in.get(b, 0) + 1
            hubs = sorted(fan_in.items(), key=lambda x: -x[1])[:8]
            if hubs:
                parts.append("Most depended-on: " + ", ".join(f"{k} ({v})" for k, v in hubs))
            cyc = dsc.cycles(graph)
            if cyc:
                parts.append("Import cycles: " + "; ".join(" -> ".join(c) for c in cyc))
        tables = dsc.data_model(ws.root)
        if tables:
            parts.append(f"## Data model ({len(tables)} tables/models)\n```mermaid\n{dsc.er_mermaid(tables)}\n```")
        if not parts:
            return "No source structure found (no Python/JS imports, no schema files)."
        text = "\n\n".join(parts)
        save_internal("map.json", {"python": py, "js": js, "tables": tables})
        return text + "\n\nUse this in docs/ARCHITECTURE.md (adopt_docs writes a first version)."

    def adopt_run(install: bool = True, timeout: int = 900) -> str:
        d = dsc.discover(ws.root)
        sb = session.sandbox
        out = []
        ok = True
        for cmd in d.install if install else []:
            r = sb.run(cmd, timeout=timeout)
            out.append(f"$ {cmd}\n{r.to_text()[-3000:]}")
            ok = ok and r.exit_code == 0
        for cmd in d.test:
            r = sb.run(cmd, timeout=timeout)
            out.append(f"$ {cmd}\n{r.to_text()[-4000:]}")
            ok = ok and r.exit_code == 0
        env_file = ws.root / ".env"
        have = env_file.read_text("utf-8", "replace") if env_file.exists() else ""
        missing = [v for v in d.env_vars if f"{v}=" not in have]
        if missing:
            out.append("Environment variables the code reads that .env does not set (never put them in code): "
                       + ", ".join(missing[:30]))
        if not d.install and not d.test:
            out.append("Nothing to install or test was detected. Find the run instructions (README, Makefile, "
                       "Dockerfile) and use run_command.")
        head = "RUNS" if ok and (d.install or d.test) else "DOES NOT RUN YET"
        return f"{head}\n" + "\n\n".join(out) + (
            "" if ok else "\n\nFix the first error (missing dependency, wrong version, missing setting) and retry.")

    def adopt_golden(name: str, command: str, masks: list[str] | None = None, include_stderr: bool = True) -> str:
        r = session.sandbox.run(command, timeout=600)
        try:
            files = golden.record(ws.root, name, command, r.exit_code, r.output, "", masks, include_stderr)
        except ValueError as e:
            raise ToolError("bad_name", str(e)) from e
        for path, content in files.items():
            write(path, content)
        warn = (f"WARNING: the command failed (exit {r.exit_code}); a failing run was recorded. Make sure that is the "
                "behaviour you want to protect (e.g. an error case) - otherwise fix the setup and record again.\n"
                if r.exit_code else "")
        return warn + (f"Recorded today's behaviour of `{command}` (exit {r.exit_code}) as tests/golden/{name}.out.\n"
                "Check it at any time with adopt_golden_check. Record many cases: main commands, typical inputs, "
                "edge cases, error cases, key HTTP endpoints (curl).")

    def adopt_golden_check() -> str:
        cs = golden.cases(ws.root)
        if not cs:
            raise ToolError("no_golden", "No golden cases recorded yet.", "Use adopt_golden first.")
        changed = []
        for c in cs:
            r = session.sandbox.run(c["command"], timeout=c.get("timeout", 600))
            got = golden.normalize(f"exit={r.exit_code}\n{r.output}\n", c["masks"])
            want = (ws.root / "tests" / "golden" / f"{c['name']}.out").read_text("utf-8")
            if got != want:
                import difflib
                diff = "\n".join(difflib.unified_diff(want.splitlines(), got.splitlines(), "recorded", "now",
                                                      lineterm="", n=2))
                changed.append(f"CHANGED {c['name']}:\n{diff[:3000]}")
        if changed:
            return ("BEHAVIOUR CHANGED in " + f"{len(changed)}/{len(cs)} cases.\n" + "\n\n".join(changed) +
                    "\n\nIf the change was intended, re-record that case with adopt_golden; otherwise fix the code.")
        return f"All {len(cs)} golden cases behave exactly as recorded."

    def adopt_health(security: bool = True) -> str:
        found = []
        if security:
            from ..labs.security.scanners import scan_config, scan_js, scan_python, scan_secrets
            found = scan_secrets(ws.root, include_history=False) + scan_python(ws.root) + scan_js(ws.root) + \
                scan_config(ws.root)
        h = dsc.health(ws.root, security=found)
        save_internal("health.json", {"score": h.score, "items": h.items})
        return h.text() + "\n\nFix HIGH items first. Write characterization tests before refactoring."

    def adopt_docs() -> str:
        d = dsc.discover(ws.root)
        py, js = dsc.python_imports(ws.root), dsc.js_imports(ws.root)
        tables = dsc.data_model(ws.root)
        name = ws.root.name
        arch = [f"# {name} — Architecture", "",
                "> First version written by yWorkspace from the code. Every section marked TODO(describe) must be "
                "completed by reading the code; do not guess.", "",
                "## Technologies", ", ".join(d.technologies) or "TODO(describe)", "",
                "## How it is organised"]
        for label, graph, sep in (("Python", py, "."), ("JS/TS", js, "/")):
            if graph:
                arch += [f"### {label}", "```mermaid", dsc.mermaid(dsc.group_graph(graph, 2, sep)), "```", ""]
        arch += ["TODO(describe): what each part is responsible for.", ""]
        if tables:
            arch += ["## Data model", "```mermaid", dsc.er_mermaid(tables), "```", ""]
        arch += ["## Configuration", "Environment variables: " + (", ".join(f"`{v}`" for v in d.env_vars) or "none"),
                 "", "## Request / data flow", "TODO(describe): follow one typical user action from entry point to "
                 "storage and back.", ""]
        write("docs/ARCHITECTURE.md", "\n".join(arch))
        written = ["docs/ARCHITECTURE.md"]
        if not d.has_readme:
            readme = [f"# {name}", "", "TODO(describe): what it does and for whom.", "", "## Setup", "```",
                      *(d.install or ["TODO(describe)"]), "```", "", "## Run", "```", *(d.run or ["TODO(describe)"]),
                      "```", "", "## Tests", "```", *(d.test or ["TODO(describe)"]), "```", "",
                      "## Configuration", *(f"- `{v}`" for v in d.env_vars), ""]
            write("README.md", "\n".join(readme))
            written.append("README.md")
        if d.env_vars and not (ws.root / ".env.example").exists():
            write(".env.example", "".join(f"{v}=\n" for v in d.env_vars))
            written.append(".env.example")
        return ("Wrote " + ", ".join(written) + ". Now replace every TODO(describe) by reading the code. "
                "The done gate's laziness check will flag any TODO left behind.")

    def adopt_migration(goal: str, steps: list[str]) -> str:
        if not steps:
            raise ToolError("no_steps", "List the migration steps (small, each one leaves the project working).")
        lines = [f"# Migration: {goal}", "", "Rules: one small step at a time; after each step the golden master "
                 "check and all tests must pass; commit after every green step.", ""]
        lines += [f"{i}. [ ] {s}" for i, s in enumerate(steps, 1)]
        write("docs/MIGRATION.md", "\n".join(lines) + "\n")
        eng = session.engine
        added = []
        if eng is not None:
            prev = None
            for s in steps:
                t = eng.state.add_task(f"Migration: {s}", description=goal,
                                       acceptance=["golden master check passes", "all tests pass"],
                                       verify="adopt_golden_check", depends_on=[prev] if prev else [])
                prev = t.id
                added.append(t.id)
            eng.state.save()
        return f"Wrote docs/MIGRATION.md with {len(steps)} steps." + (
            f" Added tasks {', '.join(added)} (each one depends on the previous)." if added else "")

    tools = [
        Tool("adopt_discover", "Existing project: detect languages, frameworks, how to install/run/test it, entry "
             "points, environment variables, CI/README/license.", obj({}), adopt_discover, SAFE, "adopt"),
        Tool("adopt_map", "Existing project: module dependency diagram (Mermaid), most-used modules, import cycles, "
             "database schema from migrations/models.", obj({"depth": {"type": "integer"}}), adopt_map, SAFE, "adopt"),
        Tool("adopt_run", "Existing project: install dependencies and run its tests in the sandbox; reports what "
             "breaks.", obj({"install": {"type": "boolean"}, "timeout": {"type": "integer"}}), adopt_run, EXEC,
             "adopt"),
        Tool("adopt_golden", "Record the current behaviour of a command (CLI run, script, curl to an endpoint) as a "
             "characterization test before changing anything. Changing parts (dates, ids, timings) are masked.",
             obj({"name": S, "command": S, "masks": {"type": "array", "items": S},
                  "include_stderr": {"type": "boolean"}}, ["name", "command"]), adopt_golden, EXEC, "adopt"),
        Tool("adopt_golden_check", "Re-run every recorded golden case and show any behaviour change.", obj({}),
             adopt_golden_check, EXEC, "adopt"),
        Tool("adopt_health", "Existing project health report: score, missing tests/docs/CI, big files, long "
             "functions, TODOs, dependency and security problems, in priority order.",
             obj({"security": {"type": "boolean"}}), adopt_health, SAFE, "adopt"),
        Tool("adopt_docs", "Write docs/ARCHITECTURE.md (and README.md / .env.example when missing) from the code, "
             "with TODO(describe) where a human explanation is needed.", obj({}), adopt_docs, WRITE, "adopt"),
        Tool("adopt_migration", "Plan a migration (e.g. Java→Kotlin, old Android APIs, Python 2→3) as small steps; "
             "writes docs/MIGRATION.md and adds dependent tasks verified by the golden master check.",
             obj({"goal": S, "steps": {"type": "array", "items": S}}, ["goal", "steps"]), adopt_migration, WRITE,
             "adopt"),
    ]
    for t in tools:
        reg.register(t)
