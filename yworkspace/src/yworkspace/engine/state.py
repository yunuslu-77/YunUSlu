"""Project memory on disk (.yw/): spec, task tree, notes and progress log. Survives restarts."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

TODO, DOING, DONE, BLOCKED, DROPPED = "todo", "doing", "done", "blocked", "dropped"
OPEN_STATES = {TODO, DOING, BLOCKED}


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    acceptance: list[str] = field(default_factory=list)
    verify: str = ""  # how to prove it works (test name, command, UI journey)
    status: str = TODO
    depends_on: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    attempts: int = 0
    branch: str = ""  # independent branch label for parallel work
    hard: bool = False

    def line(self) -> str:
        mark = {TODO: "[ ]", DOING: "[~]", DONE: "[x]", BLOCKED: "[!]", DROPPED: "[-]"}[self.status]
        deps = f" (after {', '.join(self.depends_on)})" if self.depends_on else ""
        return f"{mark} {self.id}: {self.title}{deps}"


@dataclass
class ProjectState:
    root: Path
    goal: str = ""
    spec: str = ""
    tasks: list[Task] = field(default_factory=list)
    phase: str = "new"  # new | spec | plan | build | verify | done
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    started: float = field(default_factory=time.time)
    review_approved: bool = False
    cost_by_model: dict = field(default_factory=dict)  # preset -> {"in", "out", "usd"}
    start_commit: str = ""  # git commit when the run started (finds every changed file, also from branches)

    @property
    def dir(self) -> Path:
        return Path(self.root) / ".yw"

    # ---------------------------------------------------------------- io
    @classmethod
    def load(cls, root: Path) -> ProjectState:
        d = Path(root) / ".yw"
        f = d / "state.json"
        st = cls(Path(root))
        if f.exists():
            data = json.loads(f.read_text("utf-8"))
            tasks = [Task(**t) for t in data.pop("tasks", [])]
            for k, v in data.items():
                if k in cls.__dataclass_fields__ and k != "root":
                    setattr(st, k, v)
            st.tasks = tasks
        spec = d / "SPEC.md"
        if spec.exists():
            st.spec = spec.read_text("utf-8")
        return st

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data.pop("root")
        data.pop("spec")
        (self.dir / "state.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        (self.dir / "SPEC.md").write_text(self.spec, "utf-8")
        (self.dir / "TASKS.md").write_text(self.tasks_text() + "\n", "utf-8")

    def log(self, text: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with (self.dir / "progress.md").open("a", encoding="utf-8") as f:
            f.write(f"- {stamp} {text}\n")

    def note(self, text: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with (self.dir / "NOTES.md").open("a", encoding="utf-8") as f:
            f.write(f"- {text.strip()}\n")

    def notes(self) -> str:
        p = self.dir / "NOTES.md"
        return p.read_text("utf-8") if p.exists() else ""

    def progress(self, last: int = 30) -> str:
        p = self.dir / "progress.md"
        return "\n".join(p.read_text("utf-8").splitlines()[-last:]) if p.exists() else ""

    # ------------------------------------------------------------- tasks
    def task(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    def add_task(self, title: str, **kw) -> Task:
        n = len(self.tasks) + 1
        tid = kw.pop("id", None) or f"T{n}"
        while self.task(tid):
            n += 1
            tid = f"T{n}"
        t = Task(tid, title, **kw)
        self.tasks.append(t)
        return t

    def next_task(self) -> Task | None:
        done = {t.id for t in self.tasks if t.status in (DONE, DROPPED)}
        for t in self.tasks:
            if t.status in (TODO, DOING) and all(d in done for d in t.depends_on):
                return t
        return None

    def ready_tasks(self) -> list[Task]:
        done = {t.id for t in self.tasks if t.status in (DONE, DROPPED)}
        return [t for t in self.tasks if t.status == TODO and all(d in done for d in t.depends_on)]

    def open_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status in OPEN_STATES]

    def tasks_text(self) -> str:
        if not self.tasks:
            return "(no tasks yet)"
        out = []
        for t in self.tasks:
            out.append(t.line())
            for a in t.acceptance:
                out.append(f"      - accept: {a}")
            if t.verify:
                out.append(f"      - verify: {t.verify}")
        return "\n".join(out)

    def summary(self) -> str:
        done = sum(t.status == DONE for t in self.tasks)
        return f"{done}/{len(self.tasks)} tasks done, phase={self.phase}, cost=${self.cost_usd:.3f}"
