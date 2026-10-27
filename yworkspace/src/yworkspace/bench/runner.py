"""Runs Bench tasks with and without yWorkspace and measures: hidden tests passed, done gates, time, cost,
human interventions. Results are written as JSON + Markdown so they can be published."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ..core.workspace import Workspace
from ..engine.engine import AUTO, Approver, Engine
from ..models.base import Message
from ..protocol import text_protocol
from ..sandbox import LocalSandbox
from ..tools.builtin import build_registry
from .tasks import TASKS, BenchTask


@dataclass
class Result:
    task: str
    size: str
    model: str
    mode: str  # bare | yworkspace-economy | yworkspace-balanced | yworkspace-max
    passed: bool
    hidden_output: str
    gates_passed: int
    gates_total: int
    seconds: float
    cost_usd: float
    interventions: int
    tool_errors: int


class CountingApprover(Approver):
    """Bench runs unattended: approve everything, but count how often a human would have been asked."""

    def __init__(self):
        self.count = 0

    def approve(self, kind, summary):
        self.count += 1
        return True, ""

    def question(self, question):
        self.count += 1
        return ""


def _setup(task: BenchTask, base: Path) -> Path:
    root = base / task.id
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for p, content in task.files.items():
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text(content, "utf-8")
    return root


def _check(task: BenchTask, root: Path) -> tuple[bool, str]:
    hidden = root / "bench_hidden"
    if hidden.exists():
        shutil.rmtree(hidden)  # the model must not plant its own "hidden" tests
    for p, content in task.hidden.items():
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text(content, "utf-8")
    r = LocalSandbox(root).run(task.check, timeout=300)
    return r.exit_code == 0, r.output[-3000:]


def run_bare(task: BenchTask, provider, base: Path, model: str = "") -> Result:
    """The plain model: one request with the files, one answer, applied as-is. No tools, no loop, no checks."""
    root = _setup(task, base)
    ws = Workspace(root)
    reg = build_registry(ws, None)
    files = "\n\n".join(f"--- {p} ---\n{c}" for p, c in task.files.items()) or "(the project is empty)"
    prompt = (f"{task.goal}\n\nProject files:\n{files}\n\nReply with the complete content of every file you create "
              "or change, using these blocks:\n" + text_protocol.instructions(reg.subset(names=["create"])))
    t0 = time.monotonic()
    resp = provider.chat([Message("user", prompt)], None, 16000)
    parsed = text_protocol.parse(resp.message.content, reg)
    errors = 0
    for call in parsed.calls:
        if call.name == "create":
            args = {**call.arguments, "overwrite": True}
            if (root / args.get("path", "")).is_file():
                ws.read(args["path"])
            errors += reg.call("create", args).is_error
    ok, out = _check(task, root)
    usage = getattr(resp, "usage", None)
    return Result(task.id, task.size, model, "bare", ok, out, 0, 0, round(time.monotonic() - t0, 1),
                  _usd(provider, usage), 0, errors)


def _usd(provider, usage) -> float:
    from ..models.profiles import PRESETS
    model = getattr(provider, "model", "")
    prof = next((p for p in PRESETS.values() if getattr(p, "model", None) == model), None)
    if prof is None or usage is None or prof.price_in is None:
        return 0.0
    return round(usage.input_tokens * prof.price_in / 1e6 + usage.output_tokens * (prof.price_out or 0) / 1e6, 4)


def run_yworkspace(task: BenchTask, provider_for: Callable[[str], object], base: Path, quality: str = "balanced",
                   model: str = "", skills_for=None) -> Result:
    root = _setup(task, base)
    ws = Workspace(root)
    sb = LocalSandbox(root)
    reg = build_registry(ws, sb)
    approver = CountingApprover()
    errors = {"n": 0}
    reg.after_call.append(lambda tool, args, res: errors.__setitem__("n", errors["n"] + res.is_error))
    eng = Engine(ws, reg, provider_for, sandbox=sb, approver=approver, autonomy=AUTO, quality=quality,
                 budget_usd=5.0, max_minutes=60, git=False, skills_for=skills_for or (lambda r, t: ""))
    t0 = time.monotonic()
    report = eng.run(task.goal)
    ok, out = _check(task, root)
    return Result(task.id, task.size, model, f"yworkspace-{quality}", ok, out,
                  sum(g.passed for g in report.gates), len(report.gates), round(time.monotonic() - t0, 1),
                  round(eng.state.cost_usd, 4), approver.count, errors["n"])


def run_suite(models: dict[str, Callable[[str], object]], tasks: list[BenchTask] | None = None,
              modes: tuple[str, ...] = ("bare", "balanced"), out_dir: Path | None = None,
              skills_for_model: Callable[[str], Callable] | None = None) -> list[Result]:
    """models: name -> provider_for(role). Returns all results and writes results.json + results.md."""
    tasks = tasks or TASKS
    base = Path(tempfile.mkdtemp(prefix="yw-bench-"))
    results = []
    try:
        for name, provider_for in models.items():
            for task in tasks:
                for mode in modes:
                    work = base / name / mode
                    if mode == "bare":
                        results.append(run_bare(task, provider_for("developer"), work, name))
                    else:
                        sf = skills_for_model(name) if skills_for_model else None
                        results.append(run_yworkspace(task, provider_for, work, mode, name, sf))
    finally:
        shutil.rmtree(base, ignore_errors=True)
    if out_dir:
        write_results(results, Path(out_dir))
    return results


def summary(results: list[Result]) -> dict:
    out: dict = {}
    for r in results:
        k = (r.model, r.mode)
        s = out.setdefault(k, {"passed": 0, "total": 0, "seconds": 0.0, "cost": 0.0, "interventions": 0,
                               "tool_errors": 0})
        s["passed"] += r.passed
        s["total"] += 1
        s["seconds"] += r.seconds
        s["cost"] += r.cost_usd
        s["interventions"] += r.interventions
        s["tool_errors"] += r.tool_errors
    return out


def markdown(results: list[Result]) -> str:
    rows = ["| Model | Mode | Hidden tests passed | Time (s) | Cost ($) | Human interventions | Tool errors |",
            "|---|---|---|---|---|---|---|"]
    for (model, mode), s in sorted(summary(results).items()):
        rows.append(f"| {model} | {mode} | {s['passed']}/{s['total']} ({s['passed'] / s['total'] * 100:.0f}%) | "
                    f"{s['seconds']:.0f} | {s['cost']:.3f} | {s['interventions']} | {s['tool_errors']} |")
    detail = ["", "| Task | Size | Model | Mode | Passed | Gates |", "|---|---|---|---|---|---|"]
    for r in results:
        detail.append(f"| {r.task} | {r.size} | {r.model} | {r.mode} | {'✓' if r.passed else '✗'} | "
                      f"{r.gates_passed}/{r.gates_total} |")
    return (f"# yWorkspace Bench — {datetime.now():%Y-%m-%d}\n\nHidden tests are added only after the model finished.\n\n"
            + "\n".join(rows + detail) + "\n")


def write_results(results: list[Result], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    j = out_dir / f"bench-{stamp}.json"
    j.write_text(json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False), "utf-8")
    m = out_dir / f"bench-{stamp}.md"
    m.write_text(markdown(results), "utf-8")
    return j, m
