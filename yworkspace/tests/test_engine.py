from yworkspace.core import Workspace
from yworkspace.engine import laziness
from yworkspace.engine.engine import AUTO, ECONOMY, MILESTONES, Approver, Engine
from yworkspace.engine.state import ProjectState
from yworkspace.models.scripted import ScriptedProvider, say
from yworkspace.sandbox import LocalSandbox
from yworkspace.tools.builtin import build_registry

GOOD_CODE = "def slugify(text):\n    return '-'.join(text.lower().split())\n"
TEST_CODE = ("from slug import slugify\n\n\ndef test_slugify():\n"
             "    assert slugify('Merhaba Dünya') == 'merhaba-dünya'\n")


def make_engine(tmp_path, scripts, **kw):
    ws = Workspace(tmp_path / "proj")
    sb = LocalSandbox(ws.root)
    reg = build_registry(ws, sb)
    providers = {role: ScriptedProvider(list(steps)) for role, steps in scripts.items()}
    eng = Engine(ws, reg, provider_for=lambda role: providers.setdefault(role, ScriptedProvider([])),
                 sandbox=sb, **kw)
    return eng, providers


def test_full_run_passes_gates(tmp_path):
    scripts = {
        "analyst": [say("", ("plan_set_spec", {"spec": "# Goal\nslugify\n# Features\n1. lowercases"})), say("ok")],
        "architect": [say("", ("plan_add_tasks", {"tasks": [{"title": "slugify function",
                                                              "acceptance": ["lowercase + dashes"],
                                                              "verify": "pytest"}]})), say("planned")],
        "developer": [
            say("", ("create", {"path": "slug.py", "content": GOOD_CODE}),
                ("create", {"path": "test_slug.py", "content": TEST_CODE})),
            say("", ("run", {"command": "python -m pytest -q"})),
            say("", ("plan_update", {"status": "done", "evidence": "pytest: 1 passed"})),
            say("Done."),
        ],
        "reviewer": [say("", ("review_verdict", {"approved": True})), say("lgtm")],
    }
    eng, provs = make_engine(tmp_path, scripts, autonomy=AUTO)
    report = eng.run("Write a slugify function")
    assert report.finished, report.text()
    assert all(g.passed for g in report.gates)
    st = ProjectState.load(eng.root)
    assert st.phase == "done" and st.tasks[0].status == "done"
    assert (eng.root / ".yw" / "progress.md").exists()


def test_done_requires_evidence_and_lazy_code_is_caught(tmp_path):
    lazy_code = "def slugify(text):\n    # TODO: implement this\n    pass\n"
    scripts = {
        "analyst": [say("", ("plan_set_spec", {"spec": "spec"}))],
        "architect": [say("", ("plan_add_tasks", {"tasks": [{"title": "slugify"}]}))],
        "developer": [
            say("", ("create", {"path": "slug.py", "content": lazy_code}),
                ("create", {"path": "test_slug.py", "content": TEST_CODE})),
            say("", ("plan_update", {"status": "done"})),  # rejected: no evidence
            say("", ("plan_update", {"status": "done", "evidence": "trust me"})),
            say("Done."),
        ],
        "debugger": [
            say("", ("read", {"path": "slug.py"})),
            say("", ("create", {"path": "slug.py", "content": GOOD_CODE, "overwrite": True})),
            say("", ("run", {"command": "python -m pytest -q"})),
            say("Fixed root cause."),
        ],
    }
    eng, provs = make_engine(tmp_path, scripts, autonomy=AUTO, quality=ECONOMY)
    report = eng.run("slugify")
    dev_seen = provs["developer"].seen
    assert any("no_evidence" in m.content for m in dev_seen[2] if m.role == "tool")
    assert report.finished, report.text()
    assert "TODO" not in (eng.root / "slug.py").read_text()


def test_gates_fail_without_tests_and_turn_into_tasks(tmp_path):
    scripts = {
        "analyst": [say("", ("plan_set_spec", {"spec": "spec"}))],
        "architect": [say("", ("plan_add_tasks", {"tasks": [{"title": "code only"}]}))],
        "developer": [say("", ("create", {"path": "a.py", "content": "X = 1\n"})),
                      say("", ("plan_update", {"status": "done", "evidence": "compiles"})), say("done")],
    }
    eng, _ = make_engine(tmp_path, scripts, autonomy=AUTO, quality=ECONOMY, max_rounds=2, max_task_attempts=1)
    report = eng.run("constant")
    assert not report.finished
    names = {g.name: g.passed for g in report.gates}
    assert names["tests exist"] is False
    assert any(t.title == "Fix done gate: tests exist" for t in report.state.tasks)


class Recorder(Approver):
    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = []

    def approve(self, kind, summary):
        self.asked.append(kind)
        return self.answers.pop(0) if self.answers else (True, "")


def test_milestone_approvals_and_destructive_hook(tmp_path):
    scripts = {
        "analyst": [say("", ("plan_set_spec", {"spec": "v1"})), say(""),
                    say("", ("plan_set_spec", {"spec": "v2 with dark mode"})), say("")],
        "architect": [say("", ("plan_add_tasks", {"tasks": [{"title": "t"}]})), say("")],
        "developer": [say("", ("create", {"path": "x.txt", "content": "x"})),
                      say("", ("delete", {"path": "x.txt"})), say("stop")],
    }
    appr = Recorder([(False, "add dark mode"), (True, ""), (False, "")])
    eng, provs = make_engine(tmp_path, scripts, autonomy=MILESTONES, approver=appr, quality=ECONOMY,
                             max_rounds=1, max_task_attempts=1)
    eng.run("app")
    assert eng.state.spec == "v2 with dark mode"
    assert appr.asked[:3] == ["spec", "plan", "tool"]
    assert (eng.root / "x.txt").exists()  # delete was denied
    denied = [m.content for m in provs["developer"].seen[2] if m.role == "tool"]
    assert any("denied" in c for c in denied)


def test_budget_limit(tmp_path):
    from yworkspace.models.profiles import ModelProfile
    prof = ModelProfile("p", "openai", "m", price_in=1_000_000.0, price_out=0.0)
    scripts = {"analyst": [say("", ("plan_set_spec", {"spec": "s"}))]}
    eng, _ = make_engine(tmp_path, scripts, autonomy=AUTO, budget_usd=1.0)
    eng.profile_for = lambda role: prof
    report = eng.run("x")
    assert not report.finished and "budget" in report.reason


def test_laziness_scanner():
    f = laziness.scan_text("a.py", "def f():\n    pass\n\n# rest of the code here\nx = 1  # TODO\n")
    reasons = {x.reason for x in f}
    assert "empty function (only 'pass')" in reasons and "TODO/FIXME left in code" in reasons
    assert laziness.scan_text("a.html", '<input placeholder="E-posta">') == []
    assert laziness.scan_text("b.ts", "// buraya kodunuzu ekleyin\n")
    assert laziness.scan_text("README.md", "TODO list") == []
