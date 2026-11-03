import json

from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.engine.roles import CORE_CATEGORIES, focused_categories


def test_focused_categories_follow_the_work():
    assert focused_categories("developer", "Ekrana Merhaba Dünya yazan hello.py oluştur") == CORE_CATEGORIES
    assert "data" in focused_categories("developer", "Satışlar.xlsx dosyasını özetle")
    assert "office" in focused_categories("developer", "Satışlar.xlsx dosyasını özetle")
    assert "media" in focused_categories("director", "")
    assert "operator" in focused_categories("developer", "Web sitesindeki giriş sayfasını dene")
    assert "factory" not in focused_categories("developer", "Make a clean design for the form")  # not "sign"
    assert "media" in focused_categories("developer", "Tanıtım videoyu kısalt")


def test_local_model_gets_a_small_tool_list(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    sess = build_session(tmp_path / "p", Config(sandbox="local", model="janas-qwen3-coder-next"))
    try:
        everything = sess.registry.subset(names=[n for n in sess.registry.names() if n != "review_verdict"])
        focused = everything.subset(categories=focused_categories("developer", "hello.py"))
        size = len(json.dumps(focused.to_openai(), ensure_ascii=False))
        assert {"read", "create", "edit", "run", "check", "plan_update", "git_commit"} <= set(focused.names())
        assert size < len(json.dumps(everything.to_openai(), ensure_ascii=False)) / 3
    finally:
        sess.close()
