"""Find and run a project's own checks (tests, lint, type check, build)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Check:
    name: str
    command: str
    kind: str  # test | lint | typecheck | build | custom
    timeout: int = 900


@dataclass
class CheckResult:
    check: Check
    passed: bool
    output: str


def detect(root: Path) -> list[Check]:
    root = Path(root)
    checks: list[Check] = []
    custom = root / ".yw" / "checks.json"
    if custom.exists():
        for c in json.loads(custom.read_text("utf-8")):
            checks.append(Check(c["name"], c["command"], c.get("kind", "custom"), c.get("timeout", 900)))
        return checks
    pkg = root / "package.json"
    if pkg.exists():
        try:
            scripts = json.loads(pkg.read_text("utf-8")).get("scripts", {})
        except json.JSONDecodeError:
            scripts = {}
        runner = "pnpm" if (root / "pnpm-lock.yaml").exists() else "npm"
        for key, kind in (("lint", "lint"), ("typecheck", "typecheck"), ("test", "test"), ("build", "build")):
            if key in scripts and "no test specified" not in scripts[key]:
                cmd = f"{runner} test" if key == "test" else f"{runner} run {key}"
                checks.append(Check(f"npm:{key}", cmd + (" -- --watch=false" if key == "test" and "vitest" in
                                                           scripts[key] else ""), kind))
    py_files = [p for p in root.rglob("*.py") if ".yw" not in p.parts and "node_modules" not in p.parts]
    if py_files:
        pyproject = root / "pyproject.toml"
        text = pyproject.read_text("utf-8") if pyproject.exists() else ""
        if "ruff" in text:
            checks.append(Check("ruff", "ruff check .", "lint"))
        tests = [p for p in py_files if p.name.startswith("test_") or p.name.endswith("_test.py")]
        if tests:
            checks.append(Check("pytest", "python -m pytest -q", "test"))
        else:
            checks.append(Check("python-compile", "python -m compileall -q .", "build"))
    if (root / "gradlew").exists():
        checks.append(Check("gradle:test", "./gradlew test --console=plain", "test", 1800))
    if (root / "pubspec.yaml").exists():
        checks.append(Check("flutter:test", "flutter test", "test", 1800))
    if (root / "go.mod").exists():
        checks.append(Check("go:test", "go test ./...", "test"))
    if (root / "Cargo.toml").exists():
        checks.append(Check("cargo:test", "cargo test", "test", 1800))
    return checks


def has_tests(checks: list[Check]) -> bool:
    return any(c.kind == "test" for c in checks)


def run_checks(sandbox, checks: list[Check]) -> list[CheckResult]:
    results = []
    for c in checks:
        r = sandbox.run(c.command, timeout=c.timeout)
        out = r.output
        # pytest exit code 5 = no tests collected
        passed = r.exit_code == 0
        results.append(CheckResult(c, passed, out))
    return results
