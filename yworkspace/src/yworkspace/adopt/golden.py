"""Characterization ("golden master") tests: record what the project does today, before anyone changes it.
Works for any language, because it records the output of commands (CLI runs, HTTP calls, scripts)."""

from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_MASKS = [
    r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:?\d\d)?",  # timestamps
    r"0x[0-9a-fA-F]{6,}",  # memory addresses
    r"\b\d+(?:\.\d+)?\s?(?:ms|s|sec|seconds)\b",  # durations
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",  # UUIDs
    r"/tmp/[\w./-]+",
]

CHECK_SCRIPT = '''#!/usr/bin/env python3
"""Golden master check written by yWorkspace: re-runs each recorded command and compares its output.
Run: python tests/golden/check.py   (exit code 1 = behaviour changed)"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def shell(command):
    """bash everywhere (Git Bash on Windows), like yWorkspace itself."""
    if sys.platform == "win32":
        bash = os.path.join(os.environ.get("ProgramFiles", r"C:\\Program Files"), "Git", "bin", "bash.exe")
        bash = bash if os.path.exists(bash) else shutil.which("bash")
        if bash and "system32" not in bash.lower():
            return [bash, "-c", command], False
    return command, True


def normalize(text, masks):
    for m in masks:
        text = re.sub(m, "<MASKED>", text)
    return "\\n".join(line.rstrip() for line in text.strip().splitlines())


def main():
    cases = json.loads((HERE / "golden.json").read_text("utf-8"))
    failed = 0
    for c in cases:
        args, use_shell = shell(c["command"])
        r = subprocess.run(args, shell=use_shell, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=c.get("timeout", 300))
        got = normalize(f"exit={r.returncode}\\n{r.stdout}\\n{r.stderr if c.get('stderr', True) else ''}", c["masks"])
        want = (HERE / f"{c['name']}.out").read_text("utf-8")
        if got != want:
            failed += 1
            print(f"CHANGED: {c['name']} ({c['command']})")
            import difflib
            print("\\n".join(difflib.unified_diff(want.splitlines(), got.splitlines(), "recorded", "now", lineterm="", n=2)))
        else:
            print(f"same: {c['name']}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
'''

PYTEST_FILE = '''"""Runs the golden master check (yWorkspace characterization tests)."""
import subprocess
import sys
from pathlib import Path


def test_behaviour_unchanged():
    script = Path(__file__).resolve().parent / "golden" / "check.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
'''


def normalize(text: str, masks: list[str]) -> str:
    for m in masks:
        text = re.sub(m, "<MASKED>", text)
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def record(root: Path, name: str, command: str, exit_code: int, stdout: str, stderr: str = "",
           masks: list[str] | None = None, include_stderr: bool = True) -> dict[str, str]:
    """Returns the files to write (relative path -> content); the caller writes them through the workspace."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise ValueError("golden case names may use letters, digits, _ . - only")
    masks = DEFAULT_MASKS + [m for m in (masks or []) if m not in DEFAULT_MASKS]
    existing = [c for c in cases(root) if c["name"] != name]
    index = [*existing, {"name": name, "command": command, "masks": masks, "stderr": include_stderr}]
    files = {f"tests/golden/{name}.out": normalize(f"exit={exit_code}\n{stdout}\n{stderr if include_stderr else ''}",
                                                   masks),
             "tests/golden/golden.json": json.dumps(index, indent=2, ensure_ascii=False),
             "tests/golden/check.py": CHECK_SCRIPT}
    if (Path(root) / "pyproject.toml").exists() or (Path(root) / "requirements.txt").exists() or \
            any(Path(root).glob("tests/test_*.py")):
        files.setdefault("tests/test_golden_master.py", PYTEST_FILE)
    return files


def cases(root: Path) -> list[dict]:
    index = Path(root) / "tests" / "golden" / "golden.json"
    return json.loads(index.read_text("utf-8")) if index.exists() else []
