"""Plugin system. A plugin is a folder with plugin.yaml and optionally plugin.py.

Two kinds of tools:
  * declarative (plugin.yaml `tools:` with a `command`): run inside the project's Docker sandbox → isolated.
  * python (plugin.py `register(api)`): full Python power, runs inside yWorkspace → install only trusted plugins.

Permissions a plugin may request: files (write files), shell (run commands), network (internet requests),
external (actions that leave the computer: deploy, send, pay). Tools above the granted permissions are refused.
"""

from __future__ import annotations

import importlib.util
import shlex
import shutil
import string
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..config import home
from ..core.errors import ToolError
from ..extensions import register
from ..tools.registry import DESTRUCTIVE, EXEC, EXTERNAL, SAFE, WRITE, Tool, obj

RISK_NEEDS = {SAFE: None, WRITE: "files", DESTRUCTIVE: "files", EXEC: "shell", EXTERNAL: "external"}
KNOWN_PERMISSIONS = {"files", "shell", "network", "external"}


def plugins_dir() -> Path:
    return home() / "plugins"


@dataclass
class PluginMeta:
    name: str
    version: str
    description: str
    author: str
    permissions: list[str]
    path: Path
    tools: list[dict] = field(default_factory=list)
    entry: str | None = None
    skills_dir: str | None = None
    enabled: bool = True

    @classmethod
    def load(cls, path: Path) -> PluginMeta:
        f = Path(path) / "plugin.yaml"
        if not f.exists():
            raise ToolError("bad_plugin", f"{path} has no plugin.yaml")
        d = yaml.safe_load(f.read_text("utf-8")) or {}
        for key in ("name", "version", "description"):
            if not d.get(key):
                raise ToolError("bad_plugin", f"plugin.yaml is missing '{key}'")
        perms = list(d.get("permissions") or [])
        unknown = set(perms) - KNOWN_PERMISSIONS
        if unknown:
            raise ToolError("bad_plugin", f"Unknown permissions: {', '.join(sorted(unknown))}")
        return cls(d["name"], str(d["version"]), d["description"], d.get("author", "?"), perms, Path(path),
                   d.get("tools") or [], d.get("entry"), d.get("skills"), not (Path(path) / ".disabled").exists())

    def summary(self) -> str:
        perms = ", ".join(self.permissions) or "none"
        kind = "python + declarative" if self.entry else "declarative (sandboxed)"
        return f"{self.name} {self.version} by {self.author} — {self.description}\n  permissions: {perms}; kind: {kind}"


class PluginAPI:
    """What a Python plugin's register(api) receives."""

    def __init__(self, meta: PluginMeta, session):
        self.meta = meta
        self.session = session
        self.workspace = session.workspace
        self.sandbox = session.sandbox

    def _allowed(self, risk: str) -> None:
        need = RISK_NEEDS.get(risk)
        if need and need not in self.meta.permissions:
            raise ToolError("permission", f"Plugin {self.meta.name} needs the '{need}' permission for a {risk} tool.")

    def tool(self, name: str, description: str, parameters: dict | None = None, risk: str = SAFE):
        def deco(fn):
            self._allowed(risk)
            self.session.registry.register(Tool(f"{self.meta.name}.{name}" if "." not in name else name, description,
                                                parameters or obj({}), fn, risk, f"plugin:{self.meta.name}"))
            return fn
        return deco

    def add_model_preset(self, profile) -> None:
        from ..models.profiles import PRESETS
        PRESETS[profile.id] = profile

    def add_skills(self, folder: str | Path) -> None:
        from .. import skills
        d = Path(self.meta.path) / folder
        if d not in skills.EXTRA_DIRS:
            skills.EXTRA_DIRS.append(d)

    def add_app_profile(self, path: str | Path) -> None:
        from ..bridge import desktop
        desktop.EXTRA_PROFILE_DIRS.append(Path(self.meta.path) / path)

    def add_gate(self, fn) -> None:
        if self.session.engine is not None:
            self.session.engine.extra_gates.append(fn)

    def add_recipe(self, recipe) -> None:
        from ..factory import recipes
        recipes.EXTRA.append(recipe)

    def add_deploy_target(self, target) -> None:
        from ..deploy import targets
        targets.EXTRA.append(target)


def _declarative_tool(meta: PluginMeta, spec: dict, session) -> Tool:
    name = f"{meta.name}.{spec['name']}"
    params = spec.get("parameters") or {}
    props = {k: {"type": v.get("type", "string"), "description": v.get("description", "")} for k, v in params.items()}
    required = [k for k, v in params.items() if v.get("required")]
    template = string.Template(spec["command"])
    risk = spec.get("risk", EXEC)
    need = RISK_NEEDS.get(risk)
    if need and need not in meta.permissions:
        raise ToolError("permission", f"{name} needs the '{need}' permission.")

    def handler(**kw) -> str:
        values = {k: shlex.quote(str(v)) for k, v in kw.items()}
        for k in props:
            values.setdefault(k, "''")
        cmd = template.safe_substitute(values)
        return session.sandbox.run(cmd, timeout=int(spec.get("timeout", 300))).to_text()

    return Tool(name, spec.get("description", name), obj(props, required), handler, risk, f"plugin:{meta.name}")


def installed() -> list[PluginMeta]:
    d = plugins_dir()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.iterdir()):
        if (p / "plugin.yaml").exists():
            try:
                out.append(PluginMeta.load(p))
            except ToolError:
                continue
    return out


def load_into(session, meta: PluginMeta) -> list[str]:
    before = set(session.registry.names())
    for spec in meta.tools:
        session.registry.register(_declarative_tool(meta, spec, session))
    if meta.skills_dir:
        from .. import skills
        d = meta.path / meta.skills_dir
        if d not in skills.EXTRA_DIRS:
            skills.EXTRA_DIRS.append(d)
    if meta.entry:
        spec = importlib.util.spec_from_file_location(f"yw_plugin_{meta.name.replace('-', '_')}", meta.path / meta.entry)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.register(PluginAPI(meta, session))
    return sorted(set(session.registry.names()) - before)


@register
def install(session) -> None:
    for meta in installed():
        if meta.enabled:
            try:
                load_into(session, meta)
            except Exception as e:  # a broken plugin must not break yWorkspace
                session.plugin_errors = getattr(session, "plugin_errors", []) + [f"{meta.name}: {e}"]


# ------------------------------------------------------------------ management
def install_plugin(source: str, approve) -> PluginMeta:
    """source: a folder or a git URL. approve(meta) -> bool shows permissions to the user."""
    src = Path(source)
    tmp = None
    if not src.exists():
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        r = subprocess.run(["git", "clone", "--depth", "1", source, str(tmp / "p")], capture_output=True, text=True)
        if r.returncode != 0:
            raise ToolError("clone_failed", r.stderr[-800:])
        src = tmp / "p"
    meta = PluginMeta.load(src)
    if not approve(meta):
        raise ToolError("denied", "Installation cancelled by the user.")
    dest = plugins_dir() / meta.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    return PluginMeta.load(dest)


def remove_plugin(name: str) -> None:
    dest = plugins_dir() / name
    if not dest.exists():
        raise ToolError("not_found", f"No plugin {name}")
    shutil.rmtree(dest)


def set_enabled(name: str, enabled: bool) -> None:
    flag = plugins_dir() / name / ".disabled"
    if enabled:
        flag.unlink(missing_ok=True)
    else:
        flag.write_text("", encoding="utf-8")


SCAFFOLD_YAML = """name: {name}
version: 0.1.0
description: {description}
author: {author}
# files | shell | network | external  (ask only for what you need)
permissions: [shell]
# Declarative tools run in the project's Docker sandbox. $param is replaced (shell-quoted).
tools:
  - name: word_count
    description: Count words in a file.
    command: wc -w $path
    risk: exec
    parameters:
      path: {{type: string, required: true, description: file to count}}
# Optional Python entry point (trusted code): def register(api): ...
entry: plugin.py
# Optional skills folder (same layout as the built-in library)
skills: skills
"""

SCAFFOLD_PY = '''"""Python part of the plugin. `api` is yworkspace.sdk.loader.PluginAPI."""


def register(api):
    @api.tool("hello", "Say hello (example tool).", {{"type": "object", "properties": {{"name": {{"type": "string"}}}},
                                                    "required": ["name"], "additionalProperties": False}})
    def hello(name: str) -> str:
        return f"Merhaba {{name}}, from {name}!"
'''


def scaffold(folder: Path, name: str, description: str = "My yWorkspace plugin", author: str = "you") -> Path:
    d = Path(folder) / name
    (d / "skills").mkdir(parents=True, exist_ok=True)
    (d / "plugin.yaml").write_text(SCAFFOLD_YAML.format(name=name, description=description, author=author), "utf-8")
    (d / "plugin.py").write_text(SCAFFOLD_PY.format(name=name), "utf-8")
    (d / "README.md").write_text(f"# {name}\n\n{description}\n\nInstall: `yw plugin install {d}`\n", "utf-8")
    return d
