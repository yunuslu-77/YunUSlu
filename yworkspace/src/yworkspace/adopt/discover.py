"""Understanding a project nobody explained: technologies, how to run it, its structure, its data model and its
health. Everything here reads files only; running the project happens in the sandbox (see tools.py)."""

from __future__ import annotations

import ast
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import tomllib

from ..labs.security.scanners import SKIP_DIRS

LANG_EXT = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".ts": "TypeScript",
            ".tsx": "TypeScript", ".kt": "Kotlin", ".kts": "Kotlin", ".java": "Java", ".go": "Go", ".rs": "Rust",
            ".rb": "Ruby", ".php": "PHP", ".dart": "Dart", ".swift": "Swift", ".cs": "C#", ".c": "C", ".h": "C",
            ".cpp": "C++", ".hpp": "C++", ".vue": "Vue", ".svelte": "Svelte", ".html": "HTML", ".css": "CSS",
            ".scss": "CSS", ".sql": "SQL", ".sh": "Shell"}

# manifest file -> (technology, install command, typical run/test commands)
MANIFESTS = {
    "pyproject.toml": ("Python package", "pip install -e .", []),
    "requirements.txt": ("Python", "pip install -r requirements.txt", []),
    "Pipfile": ("Python (pipenv)", "pipenv install", []),
    "manage.py": ("Django", "", ["python manage.py runserver", "python manage.py test"]),
    "package.json": ("Node.js", "npm install", []),
    "pnpm-lock.yaml": ("pnpm", "pnpm install", []),
    "yarn.lock": ("Yarn", "yarn install", []),
    "go.mod": ("Go", "go mod download", ["go build ./...", "go test ./..."]),
    "Cargo.toml": ("Rust", "cargo fetch", ["cargo build", "cargo test"]),
    "pom.xml": ("Java (Maven)", "mvn -q dependency:resolve", ["mvn test"]),
    "build.gradle": ("Gradle", "", ["./gradlew build", "./gradlew test"]),
    "build.gradle.kts": ("Gradle (Kotlin DSL)", "", ["./gradlew build", "./gradlew test"]),
    "settings.gradle": ("Gradle", "", []),
    "pubspec.yaml": ("Flutter/Dart", "flutter pub get", ["flutter test"]),
    "Gemfile": ("Ruby", "bundle install", []),
    "composer.json": ("PHP", "composer install", []),
    "Dockerfile": ("Docker", "", ["docker build ."]),
    "docker-compose.yml": ("Docker Compose", "", ["docker compose up"]),
    "compose.yaml": ("Docker Compose", "", ["docker compose up"]),
    "Makefile": ("Make", "", []),
    "AndroidManifest.xml": ("Android", "", []),
    "prisma/schema.prisma": ("Prisma", "", []),
    "next.config.js": ("Next.js", "", []),
    "next.config.mjs": ("Next.js", "", []),
    "vite.config.ts": ("Vite", "", []),
    "vite.config.js": ("Vite", "", []),
    "angular.json": ("Angular", "", []),
    "CMakeLists.txt": ("CMake", "", ["cmake -B build && cmake --build build"]),
}
FRAMEWORK_HINTS = {
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django", "sqlalchemy": "SQLAlchemy", "pytest": "pytest",
    "react": "React", "next": "Next.js", "vue": "Vue", "express": "Express", "@nestjs/core": "NestJS",
    "svelte": "Svelte", "jest": "Jest", "vitest": "Vitest", "prisma": "Prisma", "typeorm": "TypeORM",
    "mongoose": "MongoDB (Mongoose)", "tailwindcss": "Tailwind CSS", "electron": "Electron",
    "react-native": "React Native", "expo": "Expo", "celery": "Celery", "pandas": "pandas",
}
ENV_RX = re.compile(r"""(?:os\.environ(?:\.get)?\(?\[?|os\.getenv\(|process\.env\.|getenv\(|System\.getenv\(|"""
                    r"""env\(|ENV\[)\s*['"]?([A-Z][A-Z0-9_]{2,})""")


def walk(root: Path, limit: int = 20000):
    n = 0
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root).parts
        if any(part in SKIP_DIRS or part.startswith(".") and part not in (".github", ".env.example") for part in rel[:-1]):
            continue
        if p.is_file():
            n += 1
            if n > limit:
                return
            yield p


def _read(p: Path, limit: int = 400_000) -> str:
    try:
        return p.read_bytes()[:limit].decode("utf-8", "replace")
    except OSError:
        return ""


@dataclass
class Discovery:
    languages: dict[str, int] = field(default_factory=dict)  # language -> lines
    technologies: list[str] = field(default_factory=list)
    install: list[str] = field(default_factory=list)
    run: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    tests_found: int = 0
    has_ci: bool = False
    has_readme: bool = False
    has_license: bool = False
    files: int = 0

    def text(self) -> str:
        langs = ", ".join(f"{k} ({v} lines)" for k, v in sorted(self.languages.items(), key=lambda x: -x[1])[:8])
        rows = [f"Files: {self.files}", f"Languages: {langs or 'none found'}",
                f"Technologies: {', '.join(self.technologies) or 'unknown'}",
                f"Install: {' && '.join(self.install) or 'nothing detected'}",
                f"Run: {'; '.join(self.run) or 'not detected - look for a main file or ask the owner'}",
                f"Tests: {'; '.join(self.test) or 'no test command'} ({self.tests_found} test files)",
                f"Entry points: {', '.join(self.entrypoints[:10]) or 'none found'}",
                f"Environment variables used: {', '.join(self.env_vars[:40]) or 'none'}",
                f"CI: {'yes' if self.has_ci else 'no'} | README: {'yes' if self.has_readme else 'no'} | "
                f"License: {'yes' if self.has_license else 'no'}"]
        return "\n".join(rows)


def discover(root: Path) -> Discovery:
    root = Path(root)
    d = Discovery()
    langs: Counter = Counter()
    tech: list[str] = []
    env: set[str] = set()

    def add(t):
        if t and t not in tech:
            tech.append(t)

    for p in walk(root):
        d.files += 1
        rel = p.relative_to(root).as_posix()
        lang = LANG_EXT.get(p.suffix.lower())
        name = p.name.lower()
        if lang:
            text = _read(p)
            langs[lang] += text.count("\n") + 1
            env.update(ENV_RX.findall(text))
            if re.search(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+\.py$|_test\.(py|go)$|\.(test|spec)\.[jt]sx?$",
                         rel):
                d.tests_found += 1
            if (lang == "Python" and 'if __name__ == "__main__"' in text) or name in ("main.py", "app.py", "wsgi.py",
                                                                                     "asgi.py", "main.go",
                                                                                     "index.js", "server.js",
                                                                                     "main.kt", "main.dart"):
                d.entrypoints.append(rel)
        if rel in MANIFESTS or (p.name in MANIFESTS and p.name == "AndroidManifest.xml"):
            t, inst, cmds = MANIFESTS[rel if rel in MANIFESTS else p.name]
            add(t)
            if inst and inst not in d.install:
                d.install.append(inst)
            for c in cmds:
                (d.test if "test" in c else d.run).append(c)
        if name.startswith(("readme",)) and "/" not in rel:
            d.has_readme = True
        if name.startswith(("license", "licence", "copying")) and "/" not in rel:
            d.has_license = True
        if rel.startswith(".github/workflows/") or name in (".gitlab-ci.yml", "jenkinsfile", ".travis.yml"):
            d.has_ci = True
        if name.startswith(".env") and name != ".env":
            env.update(re.findall(r"^([A-Z][A-Z0-9_]+)=", _read(p), re.M))
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(_read(pkg))
        except json.JSONDecodeError:
            data = {}
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for k, v in FRAMEWORK_HINTS.items():
            if k in deps:
                add(v)
        scripts = data.get("scripts", {})
        for s in ("dev", "start", "build"):
            if s in scripts:
                d.run.append(f"npm run {s}")
        if "test" in scripts and "no test specified" not in scripts["test"]:
            d.test.append("npm test")
    py_deps = ""
    for f in ("requirements.txt", "pyproject.toml", "Pipfile"):
        if (root / f).exists():
            py_deps += _read(root / f).lower()
    for k, v in FRAMEWORK_HINTS.items():
        if re.search(rf"(^|[\s\"'\[,]){re.escape(k)}([\s\"'<>=~\[,;]|$)", py_deps, re.M):
            add(v)
    if "Python" in langs and d.tests_found and not any("pytest" in t for t in d.test) and "Django" not in tech:
        d.test.append("python -m pytest -q")
    if "FastAPI" in tech:
        for e in d.entrypoints:
            if "FastAPI(" in _read(root / e):
                d.run.append(f"uvicorn {e[:-3].replace('/', '.')}:app --reload")
                break
    d.languages = dict(langs)
    d.technologies = tech
    d.env_vars = sorted(env)
    return d


# ----------------------------------------------------------------------------- the map
def python_imports(root: Path) -> dict[str, set[str]]:
    """module -> internal modules it imports."""
    root = Path(root)
    modules = {}
    for p in walk(root):
        if p.suffix == ".py":
            rel = p.relative_to(root).with_suffix("")
            parts = [x for x in rel.parts if x not in ("src",)]
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if parts:
                modules[".".join(parts)] = p
    graph: dict[str, set[str]] = defaultdict(set)
    for mod, p in modules.items():
        try:
            tree = ast.parse(_read(p))
        except SyntaxError:
            continue
        pkg = mod.split(".")[:-1] if not p.name == "__init__.py" else mod.split(".")
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    up = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                    base = ".".join([*up, base]) if base else ".".join(up)
                names = [base] + [f"{base}.{a.name}" for a in node.names]
            for n in names:
                while n and n not in modules:
                    n = n.rpartition(".")[0]
                if n and n != mod:
                    graph[mod].add(n)
        graph.setdefault(mod, set())
    return dict(graph)


JS_IMPORT = re.compile(r"""(?:import\s[^'"]*?from\s*|import\s*\(|require\s*\()\s*['"](\.[^'"]+)['"]""")


def js_imports(root: Path) -> dict[str, set[str]]:
    root = Path(root)
    files = {p.relative_to(root).as_posix(): p for p in walk(root)
             if p.suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".vue", ".svelte")}
    graph: dict[str, set[str]] = {}
    for rel, p in files.items():
        deps = set()
        for spec in JS_IMPORT.findall(_read(p)):
            target = (Path(rel).parent / spec).as_posix()
            target = str(Path(target)).replace("\\", "/")
            parts = []
            for part in target.split("/"):
                if part == "..":
                    if parts:
                        parts.pop()
                elif part != ".":
                    parts.append(part)
            target = "/".join(parts)
            for cand in (target, *(target + e for e in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".svelte")),
                         *(f"{target}/index{e}" for e in (".ts", ".tsx", ".js", ".jsx"))):
                if cand in files:
                    deps.add(cand)
                    break
        graph[rel] = deps
    return graph


def group_graph(graph: dict[str, set[str]], depth: int = 2, sep: str = ".") -> dict[str, set[str]]:
    """Collapse a file/module graph to packages (first `depth` parts) so the diagram stays readable."""
    def key(n):
        parts = n.split(sep)
        return sep.join(parts[:depth]) if len(parts) > depth else n
    out: dict[str, set[str]] = defaultdict(set)
    for a, bs in graph.items():
        out[key(a)]
        for b in bs:
            if key(a) != key(b):
                out[key(a)].add(key(b))
    return dict(out)


def mermaid(graph: dict[str, set[str]], limit: int = 60) -> str:
    ids = {}

    def nid(n):
        if n not in ids:
            ids[n] = f"n{len(ids)}"
        return ids[n]
    lines = ["graph LR"]
    for a in sorted(graph)[:limit]:
        lines.append(f'  {nid(a)}["{a}"]')
    for a in sorted(graph)[:limit]:
        for b in sorted(graph[a]):
            if b in ids:
                lines.append(f"  {nid(a)} --> {nid(b)}")
    return "\n".join(lines)


def cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    seen, stack, found = set(), [], []
    on = set()

    def dfs(n):
        seen.add(n)
        stack.append(n)
        on.add(n)
        for m in graph.get(n, ()):
            if m in on:
                cyc = stack[stack.index(m):] + [m]
                if len(found) < 10 and sorted(cyc) not in [sorted(c) for c in found]:
                    found.append(cyc)
            elif m not in seen:
                dfs(m)
        stack.pop()
        on.discard(n)
    for n in sorted(graph):
        if n not in seen:
            dfs(n)
    return found


# ----------------------------------------------------------------------------- data model
SQL_TABLE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?[`\"\[]?(\w+)[`\"\]]?\s*\((.*?)\);", re.I | re.S)


def data_model(root: Path) -> dict[str, list[str]]:
    """table/model -> fields, from SQL migrations, SQLAlchemy/Django models, Prisma schemas."""
    root = Path(root)
    tables: dict[str, list[str]] = {}
    for p in walk(root):
        if p.suffix.lower() == ".sql":
            for name, body in SQL_TABLE.findall(_read(p)):
                cols = [ln.strip().split()[0].strip('`"[]') for ln in re.split(r",\s*(?![^()]*\))", body)
                        if ln.strip() and not re.match(r"(?i)\s*(primary|foreign|unique|constraint|check|key|index)\b",
                                                       ln.strip())]
                tables[name] = cols
        elif p.suffix == ".prisma":
            for name, body in re.findall(r"model\s+(\w+)\s*\{(.*?)\}", _read(p), re.S):
                tables[name] = [ln.split()[0] for ln in body.splitlines() if ln.strip() and
                                not ln.strip().startswith(("@@", "//"))]
        elif p.suffix == ".py":
            text = _read(p)
            if "Column(" not in text and "models.Model" not in text and "mapped_column(" not in text:
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                fields = []
                tablename = node.name
                for st in node.body:
                    if isinstance(st, (ast.Assign, ast.AnnAssign)):
                        target = st.targets[0] if isinstance(st, ast.Assign) else st.target
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id == "__tablename__" and isinstance(st.value, ast.Constant):
                            tablename = st.value.value
                            continue
                        src = ast.unparse(st.value) if st.value is not None else ""
                        ann = ast.unparse(st.annotation) if isinstance(st, ast.AnnAssign) else ""
                        if re.search(r"Column\(|mapped_column\(|models\.\w+Field\(|ForeignKey\(|relationship\(",
                                     src) or "Mapped[" in ann:
                            fields.append(target.id)
                if fields:
                    tables[tablename] = fields
    return tables


def er_mermaid(tables: dict[str, list[str]]) -> str:
    lines = ["erDiagram"]
    for t, cols in sorted(tables.items()):
        lines.append(f"  {re.sub(r'[^A-Za-z0-9_]', '_', t)} {{")
        lines += [f"    field {re.sub(r'[^A-Za-z0-9_]', '_', c)}" for c in cols[:30]]
        lines.append("  }")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- health
@dataclass
class Health:
    score: int
    items: list[tuple[str, str, str]]  # (priority, area, text)

    def text(self) -> str:
        order = {"high": 0, "medium": 1, "low": 2}
        rows = [f"Health score: {self.score}/100", ""]
        for pr, area, t in sorted(self.items, key=lambda x: order[x[0]]):
            rows.append(f"[{pr.upper()}] {area}: {t}")
        return "\n".join(rows)


def health(root: Path, disc: Discovery | None = None, security: list | None = None) -> Health:
    root = Path(root)
    disc = disc or discover(root)
    items: list[tuple[str, str, str]] = []
    todo = 0
    big_files, long_funcs = [], []
    for p in walk(root):
        if p.suffix.lower() not in LANG_EXT or p.suffix.lower() in (".html", ".css", ".scss", ".sql"):
            continue
        text = _read(p)
        rel = p.relative_to(root).as_posix()
        todo += len(re.findall(r"\b(TODO|FIXME|HACK|XXX)\b", text))
        lines = text.count("\n")
        if lines > 800:
            big_files.append(f"{rel} ({lines} lines)")
        if p.suffix == ".py":
            try:
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        n = (node.end_lineno or node.lineno) - node.lineno
                        if n > 80:
                            long_funcs.append(f"{rel}:{node.lineno} {node.name} ({n} lines)")
            except SyntaxError:
                items.append(("high", "code", f"{rel} does not parse (syntax error)"))
    if not disc.tests_found:
        items.append(("high", "tests", "No tests. Write characterization tests before changing anything."))
    if not disc.has_readme:
        items.append(("medium", "docs", "No README: nobody knows how to run it."))
    if not disc.has_ci:
        items.append(("medium", "ci", "No CI: tests do not run automatically."))
    if not disc.has_license:
        items.append(("low", "legal", "No LICENSE file."))
    if todo:
        items.append(("low" if todo < 20 else "medium", "debt", f"{todo} TODO/FIXME/HACK markers."))
    for b in big_files[:10]:
        items.append(("medium", "structure", f"Very large file {b}: split by responsibility."))
    for f in long_funcs[:10]:
        items.append(("low", "structure", f"Long function {f}."))
    for dep_issue in _dependency_issues(root):
        items.append(dep_issue)
    for f in security or []:
        if f.severity in ("critical", "high"):
            items.append(("high", "security", f"{f.rule} at {f.path}:{f.line} - {f.message}"))
    penalty = {"high": 15, "medium": 6, "low": 2}
    score = max(0, 100 - sum(penalty[i[0]] for i in items))
    return Health(score, items)


def _dependency_issues(root: Path) -> list[tuple[str, str, str]]:
    out = []
    req = root / "requirements.txt"
    if req.exists():
        loose = [ln.strip() for ln in _read(req).splitlines()
                 if ln.strip() and not ln.startswith(("#", "-")) and not re.search(r"[=<>~]", ln)]
        if loose:
            out.append(("medium", "dependencies", f"Unpinned Python dependencies: {', '.join(loose[:8])} "
                        "(builds are not reproducible)."))
    pkg = root / "package.json"
    if pkg.exists() and not any((root / f).exists() for f in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")):
        out.append(("medium", "dependencies", "package.json without a lock file."))
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            req_py = tomllib.loads(_read(pyproject)).get("project", {}).get("requires-python", "")
            m = re.search(r"(\d+)\.(\d+)", req_py)
            if m and (int(m.group(1)), int(m.group(2))) < (3, 9):
                out.append(("medium", "runtime", f"requires-python {req_py}: that Python is end-of-life."))
        except tomllib.TOMLDecodeError:
            out.append(("high", "config", "pyproject.toml is not valid TOML."))
    gradle = "".join(_read(p) for p in (root / "app/build.gradle", root / "app/build.gradle.kts") if p.exists())
    m = re.search(r"targetSdk(?:Version)?\s*=?\s*(\d+)", gradle)
    if m and int(m.group(1)) < 34:
        out.append(("high", "android", f"targetSdk {m.group(1)}: Google Play requires a recent target SDK."))
    return out
