import subprocess

from yworkspace.config import Config
from yworkspace.core import Workspace
from yworkspace.engine.engine import AUTO, ECONOMY, Engine
from yworkspace.engine.parallel import parallel_groups
from yworkspace.engine.state import ProjectState, Task
from yworkspace.models.base import Message, ProviderError
from yworkspace.models.profiles import get_profile
from yworkspace.models.router import FallbackProvider, Router, savings
from yworkspace.models.scripted import ScriptedProvider, say
from yworkspace.sandbox import LocalSandbox
from yworkspace.tools.builtin import build_registry


def router(monkeypatch, keys, **cfg):
    for k in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k in keys:
        monkeypatch.setenv(k, "x")
    return Router(Config(**cfg))


def test_router_choices(monkeypatch, tmp_path):
    monkeypatch.setenv("YW_HOME", str(tmp_path))
    r = router(monkeypatch, ["DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY"], model="deepseek-chat")
    assert r.choose("developer").preset == "claude-haiku"  # cheapest standard model with a known price
    assert r.choose("architect").preset == "claude-sonnet"  # cheapest strong model
    t = Task("T1", "x", attempts=2)
    c = r.choose("developer", t)
    assert get_profile(c.preset).tier == "strong" and "escalated" in c.reason
    assert r.choose("reviewer", quality="economy").reason.endswith("economy mode")
    first, second = r.choose("reviewer", quality="max"), r.choose("reviewer", quality="max")
    assert first.preset != second.preset and "second opinion" in second.reason
    assert get_profile(r.choose("test_user").preset).vision


def test_router_rules(monkeypatch, tmp_path):
    monkeypatch.setenv("YW_HOME", str(tmp_path))
    r = router(monkeypatch, ["ANTHROPIC_API_KEY"], model="ollama", local_only=True)
    assert [p.id for p in r.available()] == ["ollama"]
    assert r.choose("architect").preset == "ollama"
    r = router(monkeypatch, ["ANTHROPIC_API_KEY"], role_models={"developer": "deepseek-chat"})
    assert r.choose("developer").preset == "deepseek-chat"


def test_fallback_provider_switches():
    class Broken:
        name, model, supports_tools, supports_vision = "openai-compatible", "broken", True, False

        def chat(self, *a, **k):
            raise ProviderError("down", retryable=True)

    ok = ScriptedProvider([say("from backup")])
    switched = []
    fp = FallbackProvider([Broken(), ok], lambda a, b, e: switched.append(b.model))
    assert fp.chat([Message("user", "hi")]).message.content == "from backup"
    assert switched == ["scripted"]


def test_savings():
    ref = get_profile("claude-opus")
    s = savings({"claude-haiku": {"in": 1_000_000, "out": 0, "usd": 0.1}}, ref)
    assert round(s, 2) == 3.9


def test_parallel_branches_and_merge(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root)
    ws = Workspace(root)
    sb = LocalSandbox(root)
    reg = build_registry(ws, sb)
    st = ProjectState.load(root)
    st.goal, st.spec = "two modules", "# Goal\nx"
    st.add_task("api module", branch="api", acceptance=["api works"])
    st.add_task("ui module", branch="ui", acceptance=["ui works"])
    st.add_task("glue", depends_on=["T1", "T2"])
    st.save()
    assert set(parallel_groups(st)) == {"api", "ui"}

    def dev_script(messages):
        brief = messages[1].content
        if "T1" in brief.split("# Your task:")[-1][:10]:
            name, test = "api.py", "test_api.py"
        elif "T2" in brief.split("# Your task:")[-1][:10]:
            name, test = "ui.py", "test_ui.py"
        else:
            name, test = "glue.py", "test_glue.py"
        mod = name[:-3]
        return [say("", ("create", {"path": name, "content": f"def {mod}():\n    return '{mod}'\n"}),
                    ("create", {"path": test, "content": f"from {mod} import {mod}\n\n\ndef test_{mod}():\n"
                                                         f"    assert {mod}() == '{mod}'\n"})),
                say("", ("plan_update", {"status": "done", "evidence": "pytest passed"})), say("ok")]

    class PerTaskDev:
        name, model, supports_tools, supports_vision = "scripted", "scripted", True, False

        def __init__(self):
            self.queues = {}

        def chat(self, messages, tools=None, max_tokens=16000):
            key = messages[1].content.split("# Your task:")[-1][:12]
            q = self.queues.setdefault(key, dev_script(messages))
            msg = q.pop(0) if q else say("done")
            from yworkspace.models.base import ChatResponse, Usage
            return ChatResponse(msg, Usage(1, 1), "tool_calls" if msg.tool_calls else "end")

    dev = PerTaskDev()
    eng = Engine(ws, reg, provider_for=lambda role: dev if role == "developer" else ScriptedProvider([]),
                 sandbox=sb, autonomy=AUTO, quality=ECONOMY, parallel=2)
    report = eng.run("two modules")
    assert report.finished, report.text()
    for f in ("api.py", "ui.py", "glue.py"):
        assert (root / f).exists(), f
    log = subprocess.run(["git", "log", "--oneline"], cwd=root, capture_output=True, text=True).stdout
    assert "merge api" in log and "merge ui" in log
    assert not (root / ".yw" / "worktrees" / "api").exists()
