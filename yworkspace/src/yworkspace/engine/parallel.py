"""Parallel work: independent task branches are built at the same time, each in its own git worktree and
sandbox, then merged back by the Merger role.

Isolation: one git worktree + one branch + one workspace (+ one Docker container, keyed by folder) per branch.
Contract: the shared interfaces are decided before splitting (the architect's plan and notes travel along).
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import replace
from pathlib import Path

from ..core.gitutil import git_env
from ..core.workspace import Workspace
from .state import DONE, ProjectState


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=120, env=git_env(root),
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:500]}")
    return r


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=yWorkspace", "-c", "user.email=yworkspace@localhost", "commit", "-q",
         "--allow-empty", "-m", message, check=False)


def parallel_groups(state: ProjectState, max_attempts: int = 3) -> dict[str, list]:
    """Ready tasks grouped by branch label; only branches whose tasks do not depend on each other."""
    groups: dict[str, list] = {}
    for t in state.ready_tasks():
        if t.branch and t.attempts < max_attempts:
            groups.setdefault(t.branch, []).append(t)
    if len(groups) < 2:
        return {}
    # Pull in later tasks of the same branch whose dependencies are inside the branch or already done.
    done = {t.id for t in state.tasks if t.status == DONE}
    for branch, items in groups.items():
        ids = {t.id for t in items}
        for t in state.tasks:
            if t.branch == branch and t.status == "todo" and t.id not in ids and t.attempts < max_attempts and \
                    all(d in done or d in ids for d in t.depends_on):
                items.append(t)
                ids.add(t.id)
    return groups


class ParallelRunner:
    def __init__(self, engine, make_sandbox, max_workers: int = 3):
        self.engine = engine
        self.make_sandbox = make_sandbox  # (root) -> sandbox
        self.max_workers = max_workers

    def run(self, groups: dict[str, list]) -> dict[str, str]:
        eng = self.engine
        root = eng.root
        if not (root / ".git").exists():
            _git(root, "init", "-q")
        _commit_all(root, "yWorkspace: before parallel work")
        base = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        wt_root = root / ".yw" / "worktrees"
        wt_root.mkdir(parents=True, exist_ok=True)
        results: dict[str, str] = {}
        sem = threading.Semaphore(self.max_workers)

        def work(branch: str, tasks: list) -> None:
            with sem:
                path = wt_root / branch
                if path.exists():
                    _git(root, "worktree", "remove", "--force", str(path), check=False)
                    shutil.rmtree(path, ignore_errors=True)
                _git(root, "worktree", "add", "-q", "-B", f"yw/{branch}", str(path), base)
                try:
                    sub = self._sub_engine(path, tasks)
                    for t in sub.state.tasks:
                        if (limit := eng.over_limits()):
                            results[branch] = limit
                            break
                        sub.build_task(t)
                    _commit_all(path, f"yWorkspace: branch {branch}")
                    for t in sub.state.tasks:  # copy results back to the main task tree
                        main_t = eng.state.task(t.id)
                        if main_t:
                            main_t.status, main_t.evidence, main_t.notes = t.status, t.evidence, t.notes
                            main_t.attempts = t.attempts
                    results.setdefault(branch, "built")
                except Exception as e:
                    results[branch] = f"error: {e}"

        threads = [threading.Thread(target=work, args=(b, ts), daemon=True) for b, ts in groups.items()]
        eng._emit("info", f"parallel: {len(threads)} branches: {', '.join(groups)}")
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        eng.state.save()
        self._merge(list(groups), base)
        for b in groups:
            _git(root, "worktree", "remove", "--force", str(wt_root / b), check=False)
        return results

    def _sub_engine(self, path: Path, tasks: list):
        from ..tools.builtin import build_registry
        from .engine import AUTO, Engine
        eng = self.engine
        ws = Workspace(path)
        sb = self.make_sandbox(path)
        reg = build_registry(ws, sb)
        sub = Engine(ws, reg, eng.provider_for, eng.profile_for, sandbox=sb, approver=eng.approver, autonomy=AUTO
                     if eng.autonomy == AUTO else eng.autonomy, quality=eng.quality, lang=eng.lang,
                     budget_usd=None, max_minutes=eng.max_minutes, skills_for=eng.skills_for,
                     on_event=eng.on_event, git=False, router=eng.router)
        sub.state.goal, sub.state.spec = eng.state.goal, eng.state.spec
        sub.state.tasks = [replace(t, depends_on=[d for d in t.depends_on if d in {x.id for x in tasks}])
                           for t in tasks]
        notes = eng.state.notes()
        if notes:
            sub.state.note("Notes from the main plan:\n" + notes)
        sub.state.save()
        return sub

    def _merge(self, branches: list[str], base: str) -> None:
        eng = self.engine
        root = eng.root
        conflicts = []
        for b in branches:
            r = _git(root, "merge", "--no-ff", "-q", "-m", f"yWorkspace: merge {b}", f"yw/{b}", check=False)
            if r.returncode != 0:
                files = _git(root, "diff", "--name-only", "--diff-filter=U", check=False).stdout.split()
                conflicts.append((b, files))
                # Keep the conflict markers in the files for the merger, and finish the merge commit later.
                _commit_all(root, f"yWorkspace: merge {b} (conflicts to resolve)")
        if conflicts:
            detail = "\n".join(f"- branch {b}: {', '.join(f) or 'see git status'}" for b, f in conflicts)
            eng.run_role("merger", "These merges left conflict markers (<<<<<<<, =======, >>>>>>>) in files:\n"
                         f"{detail}\nResolve every conflict keeping both sides' behaviour, then run all checks.")
            _commit_all(root, "yWorkspace: conflicts resolved")
        eng.state.log(f"merged branches: {', '.join(branches)}" + (f" ({len(conflicts)} with conflicts)"
                                                                   if conflicts else ""))
