"""Git helpers shared by the engine, parallel work and the git tools."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=64)
def _has_identity(root: str) -> bool:
    try:
        r = subprocess.run(["git", "config", "user.email"], cwd=root, capture_output=True, text=True, timeout=20)
        return bool(r.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def git_env(root: Path) -> dict:
    """Environment for git: commits and merges work even on a computer where git has no user configured.
    The user's own name and e-mail are kept when they exist."""
    env = dict(os.environ)
    if not _has_identity(str(root)):
        env.setdefault("GIT_AUTHOR_NAME", "yWorkspace")
        env.setdefault("GIT_AUTHOR_EMAIL", "yworkspace@localhost")
        env.setdefault("GIT_COMMITTER_NAME", "yWorkspace")
        env.setdefault("GIT_COMMITTER_EMAIL", "yworkspace@localhost")
    return env
