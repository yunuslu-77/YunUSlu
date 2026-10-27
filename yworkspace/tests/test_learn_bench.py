from yworkspace.app import build_session
from yworkspace.bench import runner as br
from yworkspace.bench import tasks as bt
from yworkspace.config import Config
from yworkspace.learn import journal as jr
from yworkspace.learn.prove import evaluate
from yworkspace.models.base import ChatResponse, Message, ToolCall, Usage
from yworkspace.skills import load_all

GOOD = ("def average(values):\n    if not values:\n        raise ValueError('empty')\n"
        "    return sum(values) / len(values)\n\n\ndef spread(values):\n    return max(values) - min(values)\n")
BAD = ("def average(values):\n    return sum(values) / len(values)\n\n\n"
       "def spread(values):\n    return max(values) - min(values)\n")
TEST = "from stats import average\n\n\ndef test_average():\n    assert average([2, 4]) == 3\n"


class RoleBot:
    """Stateless fake model: answers from the conversation so far, so one instance serves every run."""

    model = "fake"
    supports_tools = True
    supports_vision = False

    def __init__(self, role, smart_if=None):
        self.role, self.smart_if = role, smart_if

    def chat(self, messages, tools=None, max_tokens=16000):
        step = sum(m.role == "assistant" for m in messages)
        system = messages[0].content
        smart = self.smart_if is None or self.smart_if in system
        plan = {
            "analyst": [("plan_set_spec", {"spec": "# Goal\nfix average\n# Features\n1. mean\n2. empty raises"})],
            "architect": [("plan_add_tasks", {"tasks": [{"title": "fix average", "acceptance": ["mean"],
                                                         "verify": "pytest"}]})],
            "developer": [("create", {"path": "stats.py", "content": GOOD if smart else BAD, "overwrite": True}),
                          ("create", {"path": "test_avg.py", "content": TEST}),
                          ("run", {"command": "python -m pytest -q -p no:cacheprovider"}),
                          ("plan_update", {"status": "done", "evidence": "pytest: passed"})],
            "reviewer": [("review_verdict", {"approved": True})],
        }.get(self.role, [])
        if self.role == "developer" and step == 0:
            msg = Message("assistant", "", [ToolCall("read", {"path": "stats.py"})])
        elif self.role == "developer" and 1 <= step <= len(plan):
            msg = Message("assistant", "", [ToolCall(*plan[step - 1])])
        elif self.role != "developer" and step < len(plan):
            msg = Message("assistant", "", [ToolCall(*plan[step])])
        else:
            msg = Message("assistant", "Done.")
        return ChatResponse(msg, Usage(10, 5), "tool_calls" if msg.tool_calls else "end", self.model)


def bots(smart_if=None):
    cache = {}
    return lambda role: cache.setdefault(role, RoleBot(role, smart_if))


class Bare:
    model = "fake"

    def __init__(self, answer):
        self.answer = answer

    def chat(self, messages, tools=None, max_tokens=16000):
        return ChatResponse(Message("assistant", self.answer), Usage(100, 50), "end", self.model)


def test_bare_mode_and_hidden_tests(tmp_path):
    task = bt.get("fix-average")
    good = Bare(f'<<<yw:create path="stats.py">>>\n{GOOD}>>>end')
    r = br.run_bare(task, good, tmp_path, "fake")
    assert r.passed and r.mode == "bare", r.hidden_output
    cheat = Bare('<<<yw:create path="bench_hidden/test_hidden_stats.py">>>\ndef test_x():\n    pass\n>>>end')
    r2 = br.run_bare(task, cheat, tmp_path, "fake")
    assert not r2.passed  # planted "hidden" tests are replaced by the real ones
    assert len({t.id for t in bt.TASKS}) == len(bt.TASKS) and {t.size for t in bt.TASKS} == {"small", "medium", "large"}


def test_yworkspace_mode_and_report(tmp_path):
    task = bt.get("fix-average")
    r = br.run_yworkspace(task, bots(), tmp_path, "balanced", "fake")
    assert r.passed and r.gates_passed == r.gates_total and r.gates_total > 0, r.hidden_output
    bad = br.run_yworkspace(task, bots(smart_if="never-in-prompt"), tmp_path / "b", "balanced", "fake")
    assert not bad.passed
    md = br.markdown([r, bad])
    assert "| fake | yworkspace-balanced | 1/2 (50%)" in md
    j, m = br.write_results([r], tmp_path / "out")
    assert j.exists() and m.read_text(encoding="utf-8").startswith("# yWorkspace Bench")


def test_learning_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    sess = build_session(tmp_path / "p", Config(sandbox="local", model="deepseek-chat"), with_engine=False)
    (sess.workspace.root / "a.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    call = sess.registry.call
    call("read", {"path": "a.py"})
    for _ in range(3):
        assert call("edit", {"path": "a.py", "find": "x = 1", "replace": "x = 2"}).is_error
    call("edit", {"path": "/etc/passwd", "find": "a", "replace": "b"})
    status = call("learn_status", {}).text
    assert "deepseek: ambiguous in edit ×3" in status, status
    prop = call("learn_propose", {}).text
    assert "file-discipline (deepseek)" in prop and "Make the find text unique" in prop
    lesson = jr.Journal().lessons()[0]
    assert "/" not in lesson["signature"].replace("<path>", "")
    assert call("learn_apply", {"lesson_id": lesson["id"]}).is_error  # not proven yet
    # Proof: a model that only gets it right when the lesson is in its prompt.
    result = evaluate(lesson, sess.config, [bt.get("fix-average")], provider_for=bots(smart_if="Repeated mistake"))
    assert result == {"before": 0, "after": 1, "errors_before": 0, "errors_after": 0, "tasks": 1,
                      "improved": True}, result
    items = jr.Journal().lessons()
    items[0]["status"], items[0]["bench"] = "proven", result
    jr.Journal().save_lessons(items)
    assert "Applied" in call("learn_apply", {"lesson_id": lesson["id"]}).text
    fd = next(s for s in load_all() if s.name == "file-discipline")
    assert "Lessons learned on this computer" in fd.text("tr", "deepseek")
    assert "Lessons learned" not in fd.text("tr", "gemini")
    share = call("learn_share", {"lesson_id": lesson["id"]}).text
    assert "models/deepseek.md" in share and "pass rate 0 → 1" in share
    call("learn_reject", {"lesson_id": lesson["id"]})
    assert "Lessons learned" not in fd.text("tr", "deepseek")
