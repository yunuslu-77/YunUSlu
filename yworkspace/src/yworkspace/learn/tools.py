"""Self-improving skills: hooks that record mistakes, and tools to propose, prove, apply and share lessons."""

from __future__ import annotations

from ..core.errors import ToolError
from ..extensions import register, register_gate
from ..skills import model_family
from ..tools.registry import SAFE, WRITE, Tool, obj
from . import journal as jr

S = {"type": "string"}
SKIP_CODES = {"denied", "needs_approval", "internal"}  # the user's choice or our bug, not the model's mistake


@register
def install(session) -> None:
    reg = session.registry
    journal = jr.Journal()
    family = lambda: model_family(session.config.model) or "unknown"  # noqa: E731

    def record_tool_error(tool, args, res) -> None:
        if not res.is_error or not getattr(session.config, "learn", True):
            return
        code = jr.error_code(res.text)
        if code in SKIP_CODES:
            return
        try:
            journal.record("tool_error", family(), jr.signature(res.text), code, tool.name)
        except OSError:
            pass
    reg.after_call.append(record_tool_error)

    def find(lessons, lesson_id):
        x = next((x for x in lessons if x["id"] == lesson_id), None)
        if x is None:
            raise ToolError("not_found", f"No lesson {lesson_id}.", "Use learn_status.")
        return x

    def learn_status(min_count: int = 3) -> str:
        pats = jr.patterns(journal.entries(), min_count)
        lessons = journal.lessons()
        lines = [f"{len(journal.entries())} recorded mistakes; {len(pats)} repeated patterns; {len(lessons)} lessons."]
        for p in pats[:15]:
            lines.append(f"- {p['family']}: {p['code'] or p['kind']} in {p['tool'] or '-'} ×{p['count']}: "
                         f"{p['signature'][:120]}")
        for x in lessons[-15:]:
            lines.append(f"[{x['id']}] {x['status']} → {x['skill']} ({x['family']}): {x['lesson'][:140]}")
        return "\n".join(lines)

    def learn_propose(min_count: int = 3) -> str:
        new = jr.propose(journal, min_count)
        if not new:
            return "No new repeated mistakes to learn from."
        return "Proposed lessons (prove them with learn_try, then learn_apply):\n" + "\n".join(
            f"[{x['id']}] {x['skill']} ({x['family']}): {x['lesson']}" for x in new)

    def learn_edit(lesson_id: str, lesson: str) -> str:
        items = journal.lessons()
        x = find(items, lesson_id)
        x["lesson"] = lesson.strip()
        x["status"] = "proposed"
        x["bench"] = {}
        journal.save_lessons(items)
        return f"Updated lesson {lesson_id}; it needs a new learn_try."

    def learn_try(lesson_id: str, tasks: list[str] | None = None) -> str:
        from ..bench import tasks as bt
        from .prove import evaluate
        items = journal.lessons()
        x = find(items, lesson_id)
        chosen = [bt.get(t) for t in tasks] if tasks else [t for t in bt.TASKS if t.size != "large"]
        result = evaluate(x, session.config, chosen)
        x["bench"] = result
        x["status"] = "proven" if result["improved"] else "not_better"
        journal.save_lessons(items)
        return (f"Lesson {lesson_id}: without {result['before']}, with {result['after']} hidden-test passes on "
                f"{result['tasks']} tasks; tool errors {result['errors_before']} → {result['errors_after']}. "
                + ("IMPROVES results - apply it with the user's approval." if result["improved"] else
                   "Does NOT improve results - reject or rewrite it."))

    def learn_apply(lesson_id: str, force: bool = False) -> str:
        items = journal.lessons()
        x = find(items, lesson_id)
        if x["status"] != "proven" and not force:
            raise ToolError("not_proven", "This lesson has not been shown to improve results.",
                            "Run learn_try first (or force=true if the user explicitly wants it anyway).")
        p = jr.apply(x)
        x["status"] = "applied"
        journal.save_lessons(items)
        return f"Applied: {x['skill']} now includes this lesson for {x['family']} ({p})."

    def learn_reject(lesson_id: str) -> str:
        items = journal.lessons()
        x = find(items, lesson_id)
        jr.unapply(x)
        x["status"] = "rejected"
        journal.save_lessons(items)
        return f"Rejected lesson {lesson_id}."

    def learn_share(lesson_id: str) -> str:
        x = find(journal.lessons(), lesson_id)
        return jr.share_text(x)

    tools = [
        Tool("learn_status", "Self-improving skills: repeated mistakes recorded on this computer and the lessons "
             "made from them.", obj({"min_count": {"type": "integer"}}), learn_status, SAFE, "learn"),
        Tool("learn_propose", "Turn repeated mistakes into proposed skill lessons.",
             obj({"min_count": {"type": "integer"}}), learn_propose, SAFE, "learn"),
        Tool("learn_edit", "Rewrite a proposed lesson's text (general advice only, no project details).",
             obj({"lesson_id": S, "lesson": S}, ["lesson_id", "lesson"]), learn_edit, WRITE, "learn"),
        Tool("learn_try", "Prove a lesson on yWorkspace Bench: same tasks with and without it.",
             obj({"lesson_id": S, "tasks": {"type": "array", "items": S}}, ["lesson_id"]), learn_try, WRITE,
             "learn"),
        Tool("learn_apply", "Apply a proven lesson to the local skills (the user must agree).",
             obj({"lesson_id": S, "force": {"type": "boolean"}}, ["lesson_id"]), learn_apply, WRITE, "learn"),
        Tool("learn_reject", "Reject (and remove) a lesson.", obj({"lesson_id": S}, ["lesson_id"]), learn_reject,
             WRITE, "learn"),
        Tool("learn_share", "Text for a pull request that shares a lesson with everyone (no project data).",
             obj({"lesson_id": S}, ["lesson_id"]), learn_share, SAFE, "learn"),
    ]
    for t in tools:
        reg.register(t)


@register_gate
def install_gate(session) -> None:
    """Record failed done gates (wrapping the engine's gate check; never changes the result)."""
    eng = session.engine
    journal = jr.Journal()
    original = eng.gates

    def gates():
        results = original()
        if getattr(session.config, "learn", True):
            fam = model_family(session.config.model) or "unknown"
            for g in results:
                if not g.passed and g.name != "all tasks closed":
                    try:
                        journal.record("gate_failed", fam, jr.signature(g.detail or g.name), f"gate:{g.name}")
                    except OSError:
                        pass
        return results
    eng.gates = gates
