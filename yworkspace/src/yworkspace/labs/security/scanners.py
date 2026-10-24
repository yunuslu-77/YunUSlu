"""Built-in security scanners. They need nothing installed, so every project gets a baseline check.
External scanners (semgrep, bandit, pip-audit, npm audit, gitleaks, trivy) are added on top when available."""

from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
SKIP_DIRS = {".git", ".yw", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", "target"}
TEXT_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".yml", ".yaml", ".toml", ".env", ".ini",
            ".cfg", ".kt", ".java", ".go", ".rb", ".php", ".dart", ".sh", ".tf", ".properties", ".xml", ".html", ".txt",
            ".md", ""}


@dataclass
class Finding:
    severity: str
    rule: str
    path: str
    line: int
    message: str
    fix: str

    def render(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"[{self.severity.upper()}] {self.rule} — {loc}\n  {self.message}\n  Fix: {self.fix}"


def iter_files(root: Path, exts: set[str] | None = None):
    for p in Path(root).rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts[:-1]) or not p.is_file():
            continue
        if exts is not None and p.suffix.lower() not in exts and not p.name.startswith(".env"):
            continue
        if p.stat().st_size > 1_500_000:
            continue
        yield p


# ----------------------------------------------------------------------------- secrets
SECRET_RULES = [
    ("aws-access-key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), "critical"),
    ("private-key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "critical"),
    ("stripe-live-key", re.compile(r"\b(sk|rk)_live_[0-9a-zA-Z]{20,}\b"), "critical"),
    ("github-token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}\b"), "critical"),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"), "high"),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "high"),
    ("anthropic-key", re.compile(r"\bsk-ant-[0-9A-Za-z_\-]{20,}\b"), "critical"),
    ("openai-key", re.compile(r"\bsk-(proj-)?[A-Za-z0-9]{32,}\b"), "high"),
    ("generic-secret-assignment",
     re.compile(r"""(?i)\b(secret|secret_key|api_key|apikey|access_token|auth_token|password|passwd|private_key)\b"""
                r"""\s*[:=]\s*['"]([^'"\s]{12,})['"]"""), "high"),
]
PLACEHOLDER_RX = re.compile(r"(?i)(example|changeme|change-me|your[_-]|xxx|dummy|placeholder|test|fake|dev-only|"
                            r"<|\$\{|\{\{|os\.environ|getenv|process\.env)")


def scan_secrets(root: Path, include_history: bool = True) -> list[Finding]:
    out: list[Finding] = []
    for p in iter_files(root, TEXT_EXT):
        rel = p.relative_to(root).as_posix()
        if p.name in (".env.example", ".env.sample", ".env.template"):
            continue
        try:
            lines = p.read_text("utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for rule, rx, sev in SECRET_RULES:
                m = rx.search(line)
                if not m:
                    continue
                if rule == "generic-secret-assignment" and (PLACEHOLDER_RX.search(m.group(2)) or "/tests/" in f"/{rel}"
                                                            or p.name.startswith("test_")):
                    continue
                out.append(Finding(sev, f"secret:{rule}", rel, n, "A secret appears to be written in the code.",
                                   "Move it to an environment variable / secret store, and ROTATE it (assume it leaked)."))
                break
    if (Path(root) / ".git").exists():
        tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True).stdout.split()
        for f in tracked:
            name = Path(f).name
            if name == ".env" or (name.startswith(".env.") and name not in (".env.example", ".env.sample",
                                                                              ".env.template")):
                out.append(Finding("critical", "secret:env-committed", f, 0, f"{f} is tracked by git.",
                                   f"git rm --cached {f}, add it to .gitignore, rotate the values."))
        if include_history:
            log = subprocess.run(["git", "log", "-p", "--all", "-n", "200", "--no-color"], cwd=root,
                                 capture_output=True, text=True, errors="ignore").stdout
            for rule, rx, sev in SECRET_RULES[:7]:
                if rx.search(log):
                    current = any(f.rule == f"secret:{rule}" for f in out)
                    if not current:
                        out.append(Finding(sev, f"secret:{rule}-in-history", "(git history)", 0,
                                           "A secret was committed in the past and is still in git history.",
                                           "Rotate the secret; rewriting history alone is not enough."))
    return out


# ----------------------------------------------------------------------------- python
def _src(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def scan_python(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for p in iter_files(root, {".py"}):
        rel = p.relative_to(root).as_posix()
        is_test = "/tests/" in f"/{rel}" or p.name.startswith("test_")
        try:
            tree = ast.parse(p.read_text("utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = _src(node.func)
                kw = {k.arg: k.value for k in node.keywords}
                args = node.args
                if fn in ("eval", "exec") and args and not isinstance(args[0], ast.Constant):
                    out.append(Finding("high", "py:eval", rel, node.lineno, f"{fn}() on dynamic input runs arbitrary code.",
                                       "Parse the input explicitly (json.loads, ast.literal_eval) instead."))
                if fn in ("os.system", "os.popen") and args and not isinstance(args[0], ast.Constant):
                    out.append(Finding("high", "py:shell-injection", rel, node.lineno, f"{fn} with a built string.",
                                       "Use subprocess.run([...]) with a list and no shell."))
                if fn.startswith("subprocess.") and "shell" in kw and _src(kw["shell"]) == "True" and args and \
                        not isinstance(args[0], ast.Constant):
                    out.append(Finding("high", "py:shell-injection", rel, node.lineno,
                                       "subprocess with shell=True and a built command.",
                                       "Pass a list of arguments and drop shell=True (or shlex.quote every part)."))
                if fn in ("pickle.loads", "pickle.load", "marshal.loads"):
                    out.append(Finding("high", "py:unsafe-deserialization", rel, node.lineno,
                                       f"{fn} can execute code from untrusted data.", "Use JSON for untrusted data."))
                if fn == "yaml.load" and "Loader" not in kw:
                    out.append(Finding("high", "py:yaml-load", rel, node.lineno, "yaml.load without a safe loader.",
                                       "Use yaml.safe_load."))
                if fn.endswith((".execute", ".executemany", ".raw", "text")) and args and \
                        isinstance(args[0], (ast.JoinedStr, ast.BinOp)) and not is_test:
                    s = _src(args[0]).lower()
                    if any(w in s for w in ("select", "insert", "update", "delete", "where")):
                        out.append(Finding("critical", "py:sql-injection", rel, node.lineno,
                                           "SQL built with string formatting.",
                                           "Use parameters: execute('... WHERE id = :id', {'id': value}) or the ORM."))
                if "verify" in kw and _src(kw["verify"]) == "False" and not is_test:
                    out.append(Finding("medium", "py:tls-verify-off", rel, node.lineno, "TLS certificate check disabled.",
                                       "Remove verify=False; fix the certificate instead."))
                if fn in ("hashlib.md5", "hashlib.sha1") and "password" in _src(node).lower():
                    out.append(Finding("high", "py:weak-password-hash", rel, node.lineno, f"{fn} used for passwords.",
                                       "Use argon2 or bcrypt."))
                if fn.endswith("add_middleware") and "CORSMiddleware" in _src(node) and '"*"' in _src(node) and \
                        "allow_credentials=True" in _src(node):
                    out.append(Finding("high", "py:cors-wildcard-credentials", rel, node.lineno,
                                       "CORS allows any origin together with credentials.",
                                       "List the allowed origins explicitly."))
                if fn in ("Environment", "jinja2.Environment") and "autoescape" in kw and _src(kw["autoescape"]) == "False":
                    out.append(Finding("high", "py:xss-autoescape-off", rel, node.lineno, "Jinja autoescape disabled.",
                                       "Enable autoescape (select_autoescape)."))
            if isinstance(node, ast.Assign) and not is_test:
                target = _src(node.targets[0])
                if target == "DEBUG" and _src(node.value) == "True" and p.name in ("settings.py", "config.py"):
                    out.append(Finding("medium", "py:debug-on", rel, node.lineno, "DEBUG = True in settings.",
                                       "Read DEBUG from the environment and default to False."))
    return out


# ----------------------------------------------------------------------------- javascript
JS_RULES = [
    ("js:eval", re.compile(r"(?<![\w.])eval\s*\(|new Function\s*\("), "high", "Dynamic code execution.",
     "Avoid eval/new Function; parse data with JSON.parse."),
    ("js:xss-innerhtml", re.compile(r"\.innerHTML\s*=(?!\s*['\"`]\s*['\"`])|dangerouslySetInnerHTML"), "medium",
     "HTML injected from a variable can run attacker scripts.", "Use textContent, or sanitize with DOMPurify."),
    ("js:child-process", re.compile(r"(child_process\.)?exec(Sync)?\s*\(\s*`[^`]*\$\{"), "high",
     "Shell command built from a template string.", "Use execFile/spawn with an argument array."),
    ("js:sql-injection", re.compile(r"(query|execute|raw)\s*\(\s*`[^`]*(select|insert|update|delete)[^`]*\$\{", re.I),
     "critical", "SQL built from a template string.", "Use parameterized queries or the ORM."),
    ("js:jwt-none", re.compile(r"algorithms\s*:\s*\[\s*['\"]none['\"]"), "critical", "JWT 'none' algorithm accepted.",
     "Allow only the algorithm you sign with (e.g. HS256/RS256)."),
]


def scan_js(root: Path) -> list[Finding]:
    out = []
    for p in iter_files(root, {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}):
        rel = p.relative_to(root).as_posix()
        if ".min." in p.name:
            continue
        for n, line in enumerate(p.read_text("utf-8", errors="ignore").splitlines(), 1):
            for rule, rx, sev, msg, fix in JS_RULES:
                if rx.search(line):
                    out.append(Finding(sev, rule, rel, n, msg, fix))
    return out


# ----------------------------------------------------------------------------- configuration
def scan_config(root: Path) -> list[Finding]:
    out = []
    root = Path(root)
    for df in [*root.glob("Dockerfile"), *root.glob("**/Dockerfile")]:
        if any(part in SKIP_DIRS for part in df.relative_to(root).parts):
            continue
        text = df.read_text("utf-8", errors="ignore")
        rel = df.relative_to(root).as_posix()
        if not re.search(r"^\s*USER\s+(?!root)\S+", text, re.M):
            out.append(Finding("medium", "docker:runs-as-root", rel, 0, "The container runs as root.",
                               "Create a user and add `USER appuser` before CMD."))
        if re.search(r"^\s*FROM\s+\S+:latest\b|^\s*FROM\s+[^:\s]+\s*$", text, re.M):
            out.append(Finding("low", "docker:unpinned-base", rel, 0, "Base image is not pinned to a version.",
                               "Use a specific tag, e.g. python:3.12-slim."))
    gi = root / ".gitignore"
    if (root / ".env").exists() and (not gi.exists() or ".env" not in gi.read_text("utf-8", errors="ignore")):
        out.append(Finding("high", "config:env-not-ignored", ".gitignore", 0, ".env exists but is not git-ignored.",
                           "Add .env to .gitignore."))
    for f in iter_files(root, {".py", ".js", ".ts", ".yml", ".yaml", ".json", ".toml"}):
        text = f.read_text("utf-8", errors="ignore")
        if re.search(r"""(?i)(cookie|session)[^\n]{0,80}secure\s*[=:]\s*(false|False)""", text):
            out.append(Finding("medium", "config:insecure-cookie", f.relative_to(root).as_posix(), 0,
                               "A cookie is explicitly not Secure.", "Set Secure (HTTPS) and HttpOnly on session cookies."))
    return out


def sort_findings(items: list[Finding]) -> list[Finding]:
    seen, out = set(), []
    for f in sorted(items, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.path, f.line)):
        key = (f.rule, f.path, f.line)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out
