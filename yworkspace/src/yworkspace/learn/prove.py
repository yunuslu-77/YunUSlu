"""Proof step: run Bench tasks with the user's model, with and without a lesson."""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from ..skills import skills_for
from . import journal as jr


def provider_for_config(cfg):
    from ..app import provider_factory
    provider_for, _ = provider_factory(cfg)
    return provider_for


def evaluate(lesson: dict, cfg, tasks, provider_for=None) -> dict:
    from ..bench.runner import run_yworkspace
    cfg = copy.deepcopy(cfg)
    provider_for = provider_for or provider_for_config(cfg)
    base = Path(tempfile.mkdtemp(prefix="yw-learn-"))

    def sf(role, text):
        return skills_for(role, text, cfg.lang, None, cfg.model)

    def run(tag):
        res = [run_yworkspace(t, provider_for, base / tag, cfg.quality, cfg.model, sf) for t in tasks]
        return sum(r.passed for r in res), sum(r.tool_errors for r in res)

    was_applied = lesson.get("status") == "applied"
    jr.unapply(lesson)
    before, err_before = run("before")
    jr.apply(lesson)
    try:
        after, err_after = run("after")
    finally:
        if not was_applied:
            jr.unapply(lesson)
    improved = after > before or (after == before and err_after < err_before)
    return {"before": before, "after": after, "errors_before": err_before, "errors_after": err_after,
            "tasks": len(tasks), "improved": improved}
