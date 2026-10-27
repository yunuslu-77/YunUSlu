"""Build Factory tools: detect outputs, build a matrix, verify, package, sign, upload to stores."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ..core.errors import ToolError
from ..extensions import register
from ..sandbox.local import shell_args, utf8_env
from ..tools.registry import EXTERNAL, SAFE, WRITE, Tool, obj
from . import packaging, signing, stores, verify
from .recipes import Recipe, applicable, by_id

SAFE_OPT = re.compile(r"^[\w.@:/+=,-]{0,200}$")
HOST_TOOLS = {"go-windows-exe": "go", "go-macos-bin": "go", "go-linux-bin": "go", "rust-windows-exe": None}
S = {"type": "string"}


def _check_opts(opts: dict) -> dict:
    for k, v in opts.items():
        if not isinstance(v, (str, int, float, bool)) or not SAFE_OPT.match(str(v)):
            raise ToolError("bad_option", f"Option {k!r} has characters that are not allowed: {v!r}")
    return opts


def _where(recipe: Recipe) -> str:
    tool = HOST_TOOLS.get(recipe.id)
    if tool and shutil.which(tool):
        return "host"
    if recipe.builder == "mac":
        return "host" if sys.platform == "darwin" else "mac"
    if recipe.builder == "windows":
        return "host" if sys.platform == "win32" else "windows"
    return recipe.builder


def _docker_cmd(root: Path, image: str, script: str, recipe: Recipe, env: dict) -> list[str]:
    args = ["docker", "run", "--rm", "-v", f"{root}:/src", "-w", "/src"]
    if recipe.network:
        args += ["--network", "host"]
        for var in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy"):
            if os.environ.get(var):
                args += ["-e", f"{var}={os.environ[var]}"]
    if recipe.id == "linux-iso":
        args.append("--privileged")
    sign_dir = env.pop("_signing_dir", None)
    if sign_dir:
        args += ["-v", f"{sign_dir}:/signing:ro"]
    for k, v in env.items():
        args += ["-e", f"{k}={v}"]
    owner = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else ""
    fix_owner = f" ; chown -R {owner} /src 2>/dev/null || true" if owner else ""
    return args + [image, "sh", "-c", f"({script}){fix_owner}"]


def run_recipe(root: Path, recipe: Recipe, opts: dict, env: dict | None = None,
               runner=None) -> tuple[bool, str, list[Path]]:
    def default_runner(cmd, cwd, shell):
        if shell:  # bash on every system (Git Bash on Windows)
            cmd, shell = shell_args(cmd)
        return subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=7200,
                              encoding="utf-8", errors="replace", env=utf8_env())
    runner = runner or default_runner
    where = _where(recipe)
    cmds = recipe.commands(root, opts)
    if where in ("mac", "windows"):
        need = "a Mac (or a macOS CI runner / rented Mac)" if where == "mac" else "Windows (or a Windows CI runner)"
        return False, f"{recipe.title} must be built on {need}. Commands to run there:\n" + "\n".join(
            f"  $ {c}" for c in cmds), []
    start = time.time() - 2
    log = []
    if cmds:
        script = " && ".join(cmds)
        if where == "host":
            r = runner(script, root, True)
        else:
            image = where.split(":", 1)[1]
            r = runner(_docker_cmd(root, image, script, recipe, dict(env or {})), root, False)
        log.append((r.stdout or "") + (r.stderr or ""))
        if r.returncode != 0:
            return False, f"Build failed ({recipe.id}):\n" + log[-1][-6000:], []
    found = []
    for pattern in recipe.artifacts:
        for p in root.glob(pattern):
            if p.is_file() and p.stat().st_mtime >= start:
                found.append(p)
    return True, "\n".join(log)[-3000:], sorted(set(found))


@register
def install(session) -> None:
    reg, ws = session.registry, session.workspace
    root = ws.root
    project = root.name

    def factory_detect() -> str:
        items = applicable(root)
        if not items:
            return "No build recipe applies to this project yet."
        lines = []
        for r in items:
            where = _where(r)
            flags = [where] + (["needs: " + "; ".join(r.needs)] if r.needs else []) + (
                ["tested by yWorkspace"] if r.tested_here else [])
            lines.append(f"- {r.id} → .{r.output} [{r.category}] {r.title} ({', '.join(flags)})")
        return "Possible outputs for this project:\n" + "\n".join(lines)

    def factory_build(recipes: list[str], options: dict | None = None) -> str:
        opts = _check_opts(options or {})
        table = by_id()
        out = []
        for rid in recipes:
            recipe = table.get(rid)
            if recipe is None:
                out.append(f"✗ {rid}: unknown recipe")
                continue
            env = {}
            if recipe.output in ("apk", "aab") and signing.list_keys(project):
                env = signing.gradle_signing_env(project)
                env["_signing_dir"] = str(signing.store_dir(project))
            if recipe.id == "deb":
                out.append(_deb(opts))
                continue
            ok, log, files = run_recipe(root, recipe, opts, env)
            if not ok:
                out.append(f"✗ {rid}: {log}")
                continue
            if recipe.verify == "docker":
                tag = f"{opts.get('name') or project.lower()}:{opts.get('version', '0.1.0')}"
                vok, vmsg = verify.check_docker_image(tag, int(opts["port"]) if opts.get("port") else None)
                out.append(f"{'✓' if vok else '✗'} {rid}: image {tag} — {vmsg}")
                continue
            if not files:
                out.append(f"✗ {rid}: build finished but no output matched {recipe.artifacts}")
                continue
            for f in files:
                vok, vmsg = verify.check(recipe.verify, f) if recipe.verify else (True, "")
                size = f.stat().st_size / 1024
                out.append(f"{'✓' if vok else '✗'} {rid}: {f.relative_to(root).as_posix()} ({size:.0f} KB) — {vmsg}")
        return "\n".join(out)

    def _deb(opts: dict) -> str:
        binary = opts.get("binary")
        if not binary:
            cands = [p for p in (root / "dist").glob("*linux-amd64*") if p.is_file()] if (root / "dist").exists() else []
            if not cands:
                return "✗ deb: give options.binary (a built Linux binary in dist/)."
            binary = cands[0].relative_to(root).as_posix()
        name = opts.get("name") or project.lower()
        deb = packaging.build_deb(root, name, str(opts.get("version", "0.1.0")), ws.resolve(binary),
                                  opts.get("description", name), opts.get("maintainer", "YunUSlu <noreply@example.com>"))
        ok, msg = verify.check("deb", deb)
        return f"{'✓' if ok else '✗'} deb: {deb.relative_to(root).as_posix()} — {msg}"

    def factory_verify(path: str, kind: str) -> str:
        ok, msg = verify.check(kind, ws.resolve(path))
        return f"{'PASS' if ok else 'FAIL'}: {msg}"

    def package_manifests(kind: str, version: str, url: str, artifact: str = "", description: str = "",
                          homepage: str = "", license: str = "PolyForm-Noncommercial-1.0.0",
                          publisher: str = "YunUSlu") -> str:
        sha = packaging.sha256_file(ws.resolve(artifact)) if artifact else "<fill sha256 of the released file>"
        name = project.lower()
        if kind == "winget":
            files = packaging.winget_manifest(root, publisher, name, version, url, sha, description, license)
        elif kind == "homebrew":
            files = [packaging.homebrew_formula(root, name, version, url, sha, description, homepage, license)]
        elif kind == "aur":
            files = [packaging.aur_pkgbuild(root, name, version, url, sha, description, homepage, license,
                                            f"{publisher} <noreply@example.com>")]
        else:
            raise ToolError("bad_kind", "kind must be winget, homebrew or aur")
        return "Wrote:\n" + "\n".join(f.relative_to(root).as_posix() for f in files)

    def signing_list() -> str:
        keys = signing.list_keys(project)
        if not keys:
            return "No signing keys for this project yet."
        return "\n".join(f"- {k['type']} alias={k['alias']} sha256={k.get('sha256', '')}" for k in keys) + \
            "\n(Key files and passwords are kept outside the project and are never shown.)"

    def signing_create_android(alias: str = "upload") -> str:
        info = signing.create_android_keystore(project, alias)
        return (f"Created Android keystore alias={info['alias']} sha256={info['sha256']}.\n{signing.BACKUP_WARNING}\n"
                "Release builds now receive YW_KEYSTORE, YW_KEYSTORE_PASSWORD, YW_KEY_ALIAS, YW_KEY_PASSWORD; "
                "reference them in the Gradle signingConfig.")

    def store_upload(store: str, fields: dict) -> str:
        if store not in stores.STORES:
            raise ToolError("bad_store", f"Unknown store {store}.", f"Use one of: {', '.join(stores.STORES)}")
        _check_opts(fields)
        cmd = stores.upload_command(store, **fields)
        if not cmd:
            return "This store has no command-line upload:\n" + "\n".join(stores.STORES[store]["needs"])
        args, use_shell = shell_args(cmd)
        r = subprocess.run(args, shell=use_shell, cwd=root, capture_output=True, text=True, timeout=3600,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise ToolError("upload_failed", (r.stdout + r.stderr)[-4000:],
                            "Prerequisites: " + "; ".join(stores.STORES[store]["needs"]))
        return f"Uploaded to {stores.STORES[store]['title']}.\n{(r.stdout + r.stderr)[-2000:]}"

    for t in [
        Tool("factory_detect", "List every installable/distributable output this project can be built into "
             "(APK, EXE, DMG, DEB, ISO, Docker, extensions, packages, games, firmware...).", obj({}), factory_detect,
             SAFE, "factory"),
        Tool("factory_build", "Build one or more outputs (recipe ids from factory_detect) and verify each result. "
             "options: name, version, port (docker health check), binary (deb), main (go), mac_host...",
             obj({"recipes": {"type": "array", "items": S}, "options": {"type": "object"}}, ["recipes"]),
             factory_build, "exec", "factory"),
        Tool("factory_verify", "Verify a built file. kind: pe, elf, macho, apk, zip, extension, web, targz, wheel, npm, "
             "deb, iso, pdf.", obj({"path": S, "kind": S}, ["path", "kind"]), factory_verify, "exec", "factory"),
        Tool("package_manifests", "Write winget / homebrew / aur manifests for a released file.",
             obj({"kind": S, "version": S, "url": S, "artifact": S, "description": S, "homepage": S, "license": S,
                  "publisher": S}, ["kind", "version", "url"]), package_manifests, WRITE, "factory"),
        Tool("signing_list", "List this project's signing keys (names and fingerprints only).", obj({}), signing_list,
             SAFE, "factory"),
        Tool("signing_create_android", "Create an Android upload keystore, stored outside the project.",
             obj({"alias": S}), signing_create_android, EXTERNAL, "factory"),
        Tool("store_upload", "Upload a build to a store (Google Play, App Store, Microsoft Store, Snap, Chrome Web "
             "Store, Firefox Add-ons, PyPI, npm, Docker Hub, GitHub Releases). Always asks first.",
             obj({"store": S, "fields": {"type": "object"}}, ["store", "fields"]), store_upload, EXTERNAL, "factory"),
    ]:
        reg.register(t)
