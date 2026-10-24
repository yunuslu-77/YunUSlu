from yworkspace.cli import main
from yworkspace.core import Workspace
from yworkspace.protocol.session import TextSession
from yworkspace.sandbox import LocalSandbox
from yworkspace.tools.builtin import build_registry


def test_text_session_roundtrip(tmp_path):
    ws = Workspace(tmp_path / "p")
    ts = TextSession(build_registry(ws, LocalSandbox(ws.root)), goal="make a.txt")
    assert "make a.txt" in ts.opening() and "<<<yw:" in ts.opening()
    r = ts.handle('<<<yw:create path="a.txt">>>\nhi\n>>>end')
    assert r.calls == 1 and not r.done and 'ok="true"' in r.reply_to_ai
    assert (ws.root / "a.txt").read_text() == "hi\n"
    assert ts.handle("All finished.").done


def test_text_session_idle_nudge(tmp_path):
    ws = Workspace(tmp_path / "p")
    ts = TextSession(build_registry(ws), idle_nudge=lambda s: "Tests are failing, continue." if s.turns < 2 else None)
    r = ts.handle("done!")
    assert not r.done and r.reply_to_ai == "Tests are failing, continue."
    assert ts.handle("done now").done


def test_split_long_messages(tmp_path):
    ws = Workspace(tmp_path / "p")
    ts = TextSession(build_registry(ws), max_message_chars=1000)
    parts = ts.split("\n".join("line %d %s" % (i, "x" * 50) for i in range(100)))
    assert len(parts) > 3 and all(len(p) <= 1100 for p in parts)
    assert parts[0].startswith("[Part 1/") and "last part" in parts[-1]


def test_cli_init_call_config(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    proj = tmp_path / "proj"
    assert main(["init", str(proj)]) == 0
    assert (proj / ".gitignore").exists()
    assert main(["config", "sandbox", "local"]) == 0
    assert main(["call", "create", '{"path": "x.md", "content": "# hi"}', "-p", str(proj)]) == 0
    assert main(["call", "read", '{"path": "x.md"}', "-p", str(proj)]) == 0
    assert "# hi" in capsys.readouterr().out
    assert main(["call", "read", '{"path": "../etc"}', "-p", str(proj)]) == 1
