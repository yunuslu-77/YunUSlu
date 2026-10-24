"""The Deep Work Engine: understand → plan → build → verify → review → fix → record, until the done gates pass."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..core.workspace import Workspace
from ..models.base import Message, Provider, Usage
from ..models.profiles import ModelProfile
from ..tools.registry import DESTRUCTIVE, EXEC, EXTERNAL, WRITE, Tool, ToolRegistry, obj
from . import checks as checks_mod
from . import laziness
from .loop import AgentLoop, LoopEvent
from .roles import ROLES, Role, system_prompt
from .state import BLOCKED, DONE, TODO, ProjectState

STEPS, MILESTONES, AUTO = "steps", "milestones", "auto"
ECONOMY, BALANCED, MAX = "economy", "balanced", "max"


class Approver:
    """How the engine asks the user. Interfaces (CLI, web, phone) subclass this."""

    def approve(self, kind: str, summary: str) -> tuple[bool, str]:
        return True, ""

    def question(self, text: str) -> str | None:
        return None

    def notify(self, text: str) -> None:
        pass


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class EngineReport:
    finished: bool
    reason: str
    gates: list[GateResult]
    state: ProjectState
    usage: Usage

    def text(self) -> str:
        lines = [f"Result: {'DONE' if self.finished else 'NOT DONE'} ({self.reason})", self.state.summary(), "",
                 "Done gates:"]
        lines += [f"  [{'x' if g.passed else ' '}] {g.name}" + (f" — {g.detail[:300]}" if g.detail and not g.passed
                                                                 else "") for g in self.gates]
        lines += ["", "Tasks:", self.state.tasks_text()]
        return "\n".join(lines)


def estimate_tokens(messages: list[Message]) -> int:
    return sum(len(m.content) + sum(len(str(c.arguments)) for c in m.tool_calls) for m in messages) // 4 + 1


@dataclass
class Engine:
    workspace: Workspace
    registry: ToolRegistry
    provider_for: Callable[[str], Provider]  # role -> provider (the router plugs in here)
    profile_for: Callable[[str], ModelProfile | None] = lambda role: None
    sandbox: object | None = None
    approver: Approver = field(default_factory=Approver)
    autonomy: str = MILESTONES
    quality: str = BALANCED
    lang: str = "tr"
    budget_usd: float | None = 5.0
    max_minutes: float = 240
    max_rounds: int = 6
    max_task_attempts: int = 3
    require_tests: bool = True
    extra_gates: list[Callable[[Engine], GateResult]] = field(default_factory=list)
    pre_gate_hooks: list[Callable[[Engine], None]] = field(default_factory=list)  # e.g. walk UI journeys
    skills_for: Callable[[str, str], str] = lambda role, text: ""
    on_event: Callable[[LoopEvent], None] | None = None
    git: bool = True

    def __post_init__(self) -> None:
        self.root = self.workspace.root
        self.state = ProjectState.load(self.root)
        self.usage = Usage()
        self._current_task: str | None = None
        self._verdict: tuple[bool, str] | None = None
        self._stop = False
        self._start = time.time()
        self._install_engine_tools()
        self._install_approval_hook()

    # ================================================================ tools
    def _install_engine_tools(self) -> None:
        r = self.registry
        st = self.state

        def plan_set_spec(spec: str) -> str:
            st.spec = spec
            st.save()
            return "Spec saved to .yw/SPEC.md."

        def plan_add_tasks(tasks: list[dict]) -> str:
            added = []
            for t in tasks:
                title = t.get("title") or t.get("name")
                if not title:
                    continue
                task = st.add_task(title, description=t.get("description", ""),
                                   acceptance=list(t.get("acceptance") or []), verify=t.get("verify", ""),
                                   depends_on=list(t.get("depends_on") or []), branch=t.get("branch", ""),
                                   hard=bool(t.get("hard", False)), **({"id": t["id"]} if t.get("id") else {}))
                added.append(task.id)
            st.save()
            return f"Added {len(added)} tasks: {', '.join(added)}\n\n{st.tasks_text()}"

        def plan_update(task_id: str | None = None, status: str | None = None, evidence: str | None = None,
                        note: str | None = None) -> str:
            tid = task_id or self._current_task
            task = st.task(tid) if tid else None
            if task is None:
                return f"ERROR [not_found]: no task {tid}. Tasks:\n{st.tasks_text()}"
            if note:
                task.notes.append(note)
            if evidence:
                task.evidence.append(evidence)
            if status:
                if status not in (TODO, "doing", DONE, BLOCKED):
                    return "ERROR [bad_status]: status must be todo, doing, done or blocked."
                if status == DONE and not task.evidence:
                    st.save()
                    return ("ERROR [no_evidence]: a task can only be done with evidence. Run the verify command and "
                            "call plan_update again with evidence (the command and its passing output).")
                task.status = status
            st.save()
            st.log(f"{task.id} -> {task.status}" + (f": {note}" if note else ""))
            return f"{task.line()}"

        def plan_show() -> str:
            return f"{st.summary()}\n\n{st.tasks_text()}"

        def memory_note(text: str) -> str:
            st.note(text)
            return "Noted in .yw/NOTES.md."

        def memory_read() -> str:
            return st.notes() or "(no notes yet)"

        def ask_user(question: str) -> str:
            if self.autonomy == AUTO:
                return ("The user is not available in automatic mode. Make the most sensible assumption, record it "
                        "with memory_note, and continue.")
            answer = self.approver.question(question)
            return answer or "No answer. Make a sensible assumption, record it with memory_note, and continue."

        def review_verdict(approved: bool, issues: str = "") -> str:
            self._verdict = (bool(approved), issues)
            return "Verdict recorded."

        S = {"type": "string"}
        task_schema = obj({"id": S, "title": S, "description": S, "acceptance": {"type": "array", "items": S},
                           "verify": S, "depends_on": {"type": "array", "items": S}, "branch": S,
                           "hard": {"type": "boolean"}}, ["title"])
        for t in [
            Tool("plan_set_spec", "Save the project specification (Markdown).", obj({"spec": S}, ["spec"]),
                 plan_set_spec, WRITE, "plan", "spec"),
            Tool("plan_add_tasks", "Add tasks to the task tree, in order.",
                 obj({"tasks": {"type": "array", "items": task_schema}}, ["tasks"]), plan_add_tasks, WRITE, "plan"),
            Tool("plan_update", "Update a task: status (todo|doing|done|blocked), evidence, note. "
                                "'done' requires evidence from a real command.",
                 obj({"task_id": S, "status": S, "evidence": S, "note": S}), plan_update, WRITE, "plan"),
            Tool("plan_show", "Show the task tree and progress.", obj({}), plan_show, "safe", "plan"),
            Tool("memory_note", "Save a decision, assumption or lesson to the project notes.",
                 obj({"text": S}, ["text"]), memory_note, WRITE, "plan", "text"),
            Tool("memory_read", "Read the project notes.", obj({}), memory_read, "safe", "plan"),
            Tool("ask_user", "Ask the user a question (only if you truly cannot decide yourself).",
                 obj({"question": S}, ["question"]), ask_user, "safe", "plan"),
            Tool("review_verdict", "Reviewer only: give the final verdict.",
                 obj({"approved": {"type": "boolean"}, "issues": S}, ["approved"]), review_verdict, "safe", "plan"),
        ]:
            r.register(t)

    def _install_approval_hook(self) -> None:
        def hook(tool: Tool, args: dict) -> str | None:
            needs = (
                tool.risk == EXTERNAL
                or (self.autonomy == STEPS and tool.risk in (WRITE, EXEC, DESTRUCTIVE))
                or (self.autonomy == MILESTONES and tool.risk == DESTRUCTIVE)
            )
            if tool.category == "plan" or not needs:
                return None
            shown = {k: (v if len(str(v)) < 300 else str(v)[:300] + "…") for k, v in args.items()}
            ok, feedback = self.approver.approve("tool", f"{tool.name} {shown}")
            if ok:
                return None
            return f"ERROR [denied]: The user did not approve this {tool.name} call." + (
                f" User says: {feedback}" if feedback else " Choose another way.")
        self.registry.before_call.append(hook)

    # ============================================================ helpers
    def _emit(self, kind: str, text: str = "", **data) -> None:
        if self.on_event:
            self.on_event(LoopEvent(kind, text, data))

    def _account(self, role: str, usage: Usage) -> None:
        self.usage.add(usage)
        prof = self.profile_for(role)
        st = self.state
        st.tokens_in += usage.input_tokens
        st.tokens_out += usage.output_tokens
        if prof and prof.price_in is not None and prof.price_out is not None:
            st.cost_usd += (usage.input_tokens * prof.price_in + usage.output_tokens * prof.price_out) / 1e6
        st.save()

    def over_limits(self) -> str | None:
        if self._stop:
            return "stopped by user"
        if self.budget_usd is not None and self.state.cost_usd >= self.budget_usd:
            return f"budget of ${self.budget_usd} reached"
        if (time.time() - self._start) / 60 >= self.max_minutes:
            return f"time limit of {self.max_minutes} minutes reached"
        return None

    def stop(self) -> None:
        self._stop = True

    def changed_files(self) -> list[str]:
        files = set()
        for ch in self.workspace.history(100_000):
            if ch.time >= self.state.started:
                files.add(ch.moved_to or ch.path)
        return sorted(f for f in files if (self.root / f).exists())

    def _brief(self, extra: str = "") -> str:
        st = self.state
        parts = [f"# Goal\n{st.goal}"]
        if st.spec:
            spec = st.spec if len(st.spec) < 12000 else st.spec[:12000] + "\n…(spec truncated, read .yw/SPEC.md)"
            parts.append(f"# Spec\n{spec}")
        if st.tasks:
            parts.append(f"# Task tree\n{st.tasks_text()}")
        notes = st.notes()
        if notes:
            parts.append(f"# Project notes\n{notes[-4000:]}")
        listing = self.workspace.list(".", depth=3, limit=150)
        parts.append(f"# Project files\n{listing}")
        if extra:
            parts.append(extra)
        return "\n\n".join(parts)

    def _compactor(self, role: str, provider: Provider):
        prof = self.profile_for(role)
        window = prof.context_window if prof else 128_000
        limit = int(window * 0.6)

        def compact(messages: list[Message]) -> None:
            if estimate_tokens(messages) < limit or len(messages) < 8:
                return
            head = messages[:2]
            tail = messages[-6:]
            while tail and tail[0].role == "tool":  # never start with orphaned tool results
                tail = tail[1:]
            middle = messages[2:len(messages) - len(tail)]
            touched = sorted({str(c.arguments.get("path")) for m in middle for c in m.tool_calls
                              if c.arguments.get("path")})
            summary = (f"[Earlier work was compacted to save context. {len(middle)} messages removed. "
                       f"Files you touched: {', '.join(touched) or 'none'}. Current task tree:\n"
                       f"{self.state.tasks_text()}\nRe-read files before editing them again.]")
            messages[:] = head + [Message("user", summary)] + tail
            self._emit("info", "context compacted")
        return compact

    def run_role(self, role_name: str, assignment: str, max_steps: int | None = None,
                 on_idle: Callable[[list[Message]], str | None] | None = None) -> str:
        role: Role = ROLES[role_name]
        provider = self.provider_for(role_name)
        prof = self.profile_for(role_name)
        reg = self.registry if role.tools is None else self.registry.subset(names=role.tools + ["plan_show"])
        if role.tools is None:
            reg = self.registry.subset(names=[n for n in self.registry.names() if n != "review_verdict"])
        sys = system_prompt(role, self.lang, prof.notes if prof else None,
                            self.skills_for(role_name, assignment))
        msgs = [Message("system", sys), Message("user", self._brief(assignment))]
        compact = self._compactor(role_name, provider)

        def stop_check() -> bool:
            compact(msgs)
            return self.over_limits() is not None

        loop = AgentLoop(provider, reg, max_steps=max_steps or role.max_steps, on_event=self.on_event,
                         on_idle=on_idle, should_stop=stop_check)
        if prof and prof.tool_calling == "text":
            loop.mode = "text"
        self._emit("info", f"role:{role_name}", role=role_name)
        res = loop.run(msgs)
        self._account(role_name, res.usage)
        return res.final_text

    # ========================================================== phases
    def understand(self) -> None:
        st = self.state
        if st.spec.strip():
            return
        st.phase = "spec"
        self.run_role("analyst", "Write the specification for the goal above.")
        if not st.spec.strip():
            st.spec = f"# Goal\n{st.goal}\n"
        if self.autonomy in (STEPS, MILESTONES):
            ok, feedback = self.approver.approve("spec", st.spec)
            if not ok and feedback:
                self.run_role("analyst", f"The user wants changes to the spec: {feedback}\n"
                                         "Call plan_set_spec with the corrected full spec.")
        st.save()

    def plan(self) -> None:
        st = self.state
        if st.tasks:
            return
        st.phase = "plan"
        self.run_role("architect", "Create the task plan for this spec.")
        if not st.tasks:
            st.add_task("Implement the goal", description=st.goal, acceptance=["The goal in the spec works"],
                        verify="the project's tests")
        if self.autonomy in (STEPS, MILESTONES):
            ok, feedback = self.approver.approve("plan", st.tasks_text())
            if not ok and feedback:
                st.tasks.clear()
                self.run_role("architect", f"The user rejected the plan: {feedback}\nCreate a new plan.")
        st.save()

    def _git_commit(self, message: str) -> None:
        if not self.git or not (self.root / ".git").exists():
            return
        try:
            subprocess.run(["git", "add", "-A"], cwd=self.root, capture_output=True, timeout=60)
            subprocess.run(["git", "-c", "user.name=yWorkspace", "-c", "user.email=yworkspace@localhost",
                            "commit", "-q", "-m", message], cwd=self.root, capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _run_checks(self) -> list[checks_mod.CheckResult]:
        if self.sandbox is None:
            return []
        return checks_mod.run_checks(self.sandbox, checks_mod.detect(self.root))

    def build_task(self, task) -> None:
        st = self.state
        self._current_task = task.id
        task.status = "doing"
        task.attempts += 1
        st.save()
        assignment = (f"# Your task: {task.id} — {task.title}\n{task.description}\n\nAcceptance criteria:\n"
                      + "\n".join(f"- {a}" for a in task.acceptance)
                      + (f"\n\nVerify with: {task.verify}" if task.verify else ""))
        nudges = {"n": 0}

        def on_idle(_msgs) -> str | None:
            if task.status in (DONE, BLOCKED) or nudges["n"] >= 4:
                return None
            nudges["n"] += 1
            lazy = laziness.scan_files(self.root, self.changed_files())
            msg = (f"Task {task.id} is not marked done yet. Continue working on it. When every acceptance criterion "
                   "is met and verified, call plan_update with status 'done' and evidence.")
            if lazy:
                msg += "\nUnfinished code was found:\n" + "\n".join(f.render() for f in lazy[:15])
            return msg

        self.run_role("developer", assignment, on_idle=on_idle)
        self._emit("info", f"task {task.id}: {task.status}")
        if task.status != DONE:
            return
        # Verify independently of what the model said.
        failing = [r for r in self._run_checks() if not r.passed]
        lazy = laziness.scan_files(self.root, self.changed_files())
        if failing or lazy:
            task.status = TODO
            problem = "\n\n".join(f"## {r.check.name} failed\n{r.output[-4000:]}" for r in failing)
            if lazy:
                problem += "\n\n## Unfinished code\n" + "\n".join(f.render() for f in lazy[:20])
            task.notes.append("Verification failed after the developer marked it done.")
            st.save()
            self.run_role("debugger", f"# Task {task.id}: {task.title}\n{problem}")
            failing = [r for r in self._run_checks() if not r.passed]
            lazy = laziness.scan_files(self.root, self.changed_files())
            if not failing and not lazy:
                task.status = DONE
                task.evidence.append("yWorkspace re-ran all checks after debugging: passed")
            st.save()
            if task.status != DONE:
                return
        if self.quality in (BALANCED, MAX):
            self.review(task)
        if task.status == DONE:
            self._git_commit(f"{task.id}: {task.title}")
            st.log(f"{task.id} done")

    def review(self, task) -> None:
        rounds = 2 if self.quality == MAX else 1
        for _ in range(rounds + 1):
            self._verdict = None
            files = "\n".join(self.changed_files()[:80])
            self.run_role("reviewer", f"# Review task {task.id}: {task.title}\nAcceptance:\n"
                          + "\n".join(f"- {a}" for a in task.acceptance) + f"\n\nChanged files:\n{files}")
            if self._verdict is None or self._verdict[0]:
                return
            issues = self._verdict[1]
            task.notes.append(f"Review issues: {issues[:1000]}")
            task.status = "doing"
            self.state.save()
            self.run_role("developer", f"# Fix review issues for task {task.id}: {task.title}\n{issues}\n\n"
                          "Fix every issue, run the checks, then call plan_update with status done and evidence.")
            if task.status != DONE:
                return

    # ============================================================== gates
    def gates(self) -> list[GateResult]:
        st = self.state
        out: list[GateResult] = []
        open_tasks = st.open_tasks()
        out.append(GateResult("all tasks closed", not open_tasks, ", ".join(t.id for t in open_tasks)))
        no_ev = [t.id for t in st.tasks if t.status == DONE and not t.evidence]
        out.append(GateResult("evidence for every done task", not no_ev, ", ".join(no_ev)))
        detected = checks_mod.detect(self.root)
        if self.sandbox is None:
            out.append(GateResult("checks pass", False, "No sandbox: checks could not be run."))
        else:
            results = checks_mod.run_checks(self.sandbox, detected)
            bad = [r for r in results if not r.passed]
            out.append(GateResult("checks pass", not bad,
                                  "\n".join(f"{r.check.name}: {r.output[-1500:]}" for r in bad)))
        has_code = any(Path(f).suffix in laziness.CODE_EXT for f in self.changed_files())
        if self.require_tests and has_code:
            out.append(GateResult("tests exist", checks_mod.has_tests(detected),
                                  "No test command was found. Add tests (e.g. pytest or an npm test script)."))
        lazy = laziness.scan_files(self.root, self.changed_files())
        out.append(GateResult("no unfinished code", not lazy, "\n".join(f.render() for f in lazy[:20])))
        for g in self.extra_gates:
            out.append(g(self))
        return out

    # ================================================================ run
    def run(self, goal: str | None = None) -> EngineReport:
        st = self.state
        if goal and goal.strip() != st.goal.strip():
            if st.goal and st.tasks:
                st.log(f"new goal: {goal}")
                st.spec, st.tasks, st.phase = "", [], "new"
            st.goal = goal
        st.save()
        st.log(f"run started (autonomy={self.autonomy}, quality={self.quality})")
        reason = "finished"
        gates: list[GateResult] = []
        for round_no in range(1, self.max_rounds + 1):
            if (limit := self.over_limits()):
                reason = limit
                break
            self.understand()
            self.plan()
            st.phase = "build"
            while (task := st.next_task()) is not None:
                if (limit := self.over_limits()):
                    break
                if task.attempts >= self.max_task_attempts:
                    task.status = BLOCKED
                    task.notes.append(f"Gave up after {task.attempts} attempts.")
                    st.save()
                    continue
                self.build_task(task)
            if (limit := self.over_limits()):
                reason = limit
                break
            st.phase = "verify"
            for hook in self.pre_gate_hooks:
                if not self.over_limits():
                    hook(self)
            gates = self.gates()
            if all(g.passed for g in gates):
                st.phase = "done"
                st.save()
                st.log("all done gates passed")
                self._git_commit("yWorkspace: all done gates passed")
                return EngineReport(True, "all done gates passed", gates, st, self.usage)
            # Turn failed gates into new work, and retry blocked tasks once more with fresh eyes.
            failed = [g for g in gates if not g.passed and g.name != "all tasks closed"]
            for g in failed:
                st.add_task(f"Fix done gate: {g.name}", description=g.detail[:3000],
                            acceptance=[f"The '{g.name}' gate passes"], verify="yWorkspace done gates")
            for t in st.tasks:
                if t.status == BLOCKED and t.attempts < self.max_task_attempts + 1:
                    t.status = TODO
            st.save()
            st.log(f"round {round_no}: gates failed: {', '.join(g.name for g in gates if not g.passed)}")
            if not failed and not st.next_task():
                reason = "blocked tasks remain"
                break
        else:
            reason = "max rounds reached"
        st.save()
        return EngineReport(False, reason, gates or self.gates(), st, self.usage)

