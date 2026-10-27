import pytest

from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.core import ToolError
from yworkspace.sdk import loader


def test_scaffold_install_and_use(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    from yworkspace import skills
    monkeypatch.setattr(skills, "EXTRA_DIRS", [])
    src = loader.scaffold(tmp_path, "demo")
    (src / "skills" / "custom" / "demo-skill").mkdir(parents=True)
    (src / "skills" / "custom" / "demo-skill" / "skill.yaml").write_text(
        "name: demo-skill\ntitle_tr: Demo\ntitle_en: Demo\ndescription: d\ntriggers: [zebra]\n", encoding="utf-8")
    (src / "skills" / "custom" / "demo-skill" / "core.en.md").write_text("Zebra rules.", encoding="utf-8")
    seen = []
    meta = loader.install_plugin(str(src), lambda m: seen.append(m.permissions) or True)
    assert seen == [["shell"]] and meta.name == "demo"
    sess = build_session(tmp_path / "proj", Config(sandbox="local"), with_engine=False)
    assert "demo.hello" in sess.registry.names() and "demo.word_count" in sess.registry.names()
    assert sess.registry.call("demo.hello", {"name": "Yunus"}).text == "Merhaba Yunus, from demo!"
    sess.workspace.create("a.txt", "bir iki uc\n")  # wc counts non-ASCII words differently per locale
    assert sess.registry.call("demo.word_count", {"path": "a.txt"}).text.split("\n")[1].strip().startswith("3")
    from yworkspace.skills import select
    assert "demo-skill" in [s.name for s in select("developer", "zebra")]
    loader.set_enabled("demo", False)
    assert not loader.installed()[0].enabled


def test_permissions_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    d = tmp_path / "bad"
    d.mkdir()
    (d / "plugin.yaml").write_text("name: bad\nversion: 1\ndescription: x\npermissions: []\n"
                                   "tools:\n  - {name: rm, command: 'rm -rf $p', risk: exec}\n", encoding="utf-8")
    meta = loader.PluginMeta.load(d)
    sess = build_session(tmp_path / "proj", Config(sandbox="local"), with_engine=False)
    with pytest.raises(ToolError, match="shell"):
        loader.load_into(sess, meta)
    (d / "plugin.yaml").write_text("name: bad\nversion: 1\ndescription: x\npermissions: [root]\n", encoding="utf-8")
    with pytest.raises(ToolError, match="Unknown permissions"):
        loader.PluginMeta.load(d)
    with pytest.raises(ToolError, match="cancelled"):
        loader.install_plugin(str(loader.scaffold(tmp_path, "x")), lambda m: False)


def test_shell_injection_is_quoted(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    src = loader.Path(loader.__file__).parent / "examples" / "markdown-tools"
    loader.install_plugin(str(src), lambda m: True)
    sess = build_session(tmp_path / "proj", Config(sandbox="local"), with_engine=False)
    sess.registry.call("markdown-tools.word_count", {"path": "x; touch pwned"})
    assert not (sess.workspace.root / "pwned").exists()
