import os

import pytest

from yworkspace.core import ToolError, Workspace


@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path / "proj")


def err(fn, *a, **k):
    with pytest.raises(ToolError) as e:
        fn(*a, **k)
    return e.value


def test_create_read_numbered(ws):
    ws.create("a/b.py", "x = 1\ny = 2\n")
    out = ws.read("a/b.py")
    assert "     1\tx = 1" in out and "     2\ty = 2" in out
    assert "lines 1-2 of 2" in out


def test_read_paging(ws):
    ws.create("big.txt", "\n".join(str(i) for i in range(1, 101)) + "\n")
    out = ws.read("big.txt", offset=10, limit=5)
    assert "lines 10-14 of 100" in out and "offset=15" in out


def test_create_refuses_existing(ws):
    ws.create("f.txt", "a")
    assert err(ws.create, "f.txt", "b").code == "exists"


def test_overwrite_requires_read(ws, tmp_path):
    (ws.root / "g.txt").write_text("orig", encoding="utf-8")
    assert err(ws.create, "g.txt", "new", overwrite=True).code == "not_read"
    ws.read("g.txt")
    ws.create("g.txt", "new", overwrite=True)
    assert (ws.root / "g.txt").read_text(encoding="utf-8") == "new"


def test_edit_exact(ws):
    ws.create("m.py", "def add(a, b):\n    return a - b\n")
    out = ws.edit("m.py", "return a - b", "return a + b")
    assert "1 replacement" in out and "+    return a + b" in out
    assert (ws.root / "m.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"


def test_edit_requires_read_and_detects_stale(ws):
    (ws.root / "s.txt").write_text("hello\n", encoding="utf-8")
    assert err(ws.edit, "s.txt", "hello", "bye").code == "not_read"
    ws.read("s.txt")
    (ws.root / "s.txt").write_text("hello world\n", encoding="utf-8")
    assert err(ws.edit, "s.txt", "hello", "bye").code == "stale"


def test_edit_ambiguous_and_replace_all(ws):
    ws.create("d.txt", "x\nx\nx\n")
    e = err(ws.edit, "d.txt", "x", "y")
    assert e.code == "ambiguous" and "3 times" in e.message
    ws.edit("d.txt", "x", "y", replace_all=True)
    assert (ws.root / "d.txt").read_text(encoding="utf-8") == "y\ny\ny\n"


def test_edit_whitespace_suggestion(ws):
    ws.create("w.py", "def f():\n    if True:\n        return 1\n")
    e = err(ws.edit, "w.py", "if True:\n    return 1", "if False:\n    return 2")
    assert e.code == "not_found"
    assert "except for whitespace" in e.message and "lines 2-3" in e.message


def test_edit_fuzzy_suggestion(ws):
    ws.create("z.py", "def compute_total(items):\n    return sum(i.price for i in items)\n")
    e = err(ws.edit, "z.py", "def compute_totals(items):\n    return sum(i.prices for i in items)", "x")
    assert "similar" in e.message and "lines 1-2" in e.message


def test_multi_edit_atomic(ws):
    ws.create("t.txt", "one\ntwo\nthree\n")
    e = err(ws.multi_edit, "t.txt", [{"find": "one", "replace": "1"}, {"find": "zzz", "replace": "2"}])
    assert "no edits were applied" in e.message
    assert (ws.root / "t.txt").read_text(encoding="utf-8") == "one\ntwo\nthree\n"
    ws.multi_edit("t.txt", [{"find": "one", "replace": "1"}, {"find": "three", "replace": "3"}])
    assert (ws.root / "t.txt").read_text(encoding="utf-8") == "1\ntwo\n3\n"


def test_preserves_crlf_and_bom(ws):
    (ws.root / "win.txt").write_bytes(b"\xef\xbb\xbfa\r\nb\r\n")
    ws.read("win.txt")
    ws.edit("win.txt", "b", "c")
    assert (ws.root / "win.txt").read_bytes() == b"\xef\xbb\xbfa\r\nc\r\n"


def test_outside_and_denied(ws):
    assert err(ws.read, "../x").code == "outside_workspace"
    (ws.root / ".env").write_text("SECRET=1", encoding="utf-8")
    assert err(ws.read, ".env").code == "denied"
    (ws.root / ".env.example").write_text("SECRET=", encoding="utf-8")
    assert "SECRET=" in ws.read(".env.example")
    assert err(ws.read, ".yw/history/journal.jsonl").code == "protected"


@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin rights on Windows")
def test_symlink_escape(ws, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("top secret", encoding="utf-8")
    (ws.root / "link.txt").symlink_to(outside)
    assert err(ws.read, "link.txt").code == "outside_workspace"


def test_binary_refused(ws):
    (ws.root / "img.bin").write_bytes(b"\x89PNG\x00\x01")
    assert err(ws.read, "img.bin").code == "binary_file"


def test_undo_edit_create_delete_move(ws):
    ws.create("u.txt", "a\n")
    ws.edit("u.txt", "a", "b")
    ws.undo()
    assert (ws.root / "u.txt").read_text(encoding="utf-8") == "a\n"
    ws.undo()
    assert not (ws.root / "u.txt").exists()
    ws.create("v.txt", "v\n")
    ws.delete("v.txt")
    assert not (ws.root / "v.txt").exists()
    ws.undo()
    assert (ws.root / "v.txt").read_text(encoding="utf-8") == "v\n"
    ws.read("v.txt")
    ws.move("v.txt", "sub/w.txt")
    assert (ws.root / "sub/w.txt").exists()
    ws.undo()
    assert (ws.root / "v.txt").exists() and not (ws.root / "sub/w.txt").exists()


def test_undo_conflict(ws):
    ws.create("c.txt", "1\n")
    (ws.root / "c.txt").write_text("changed by someone\n", encoding="utf-8")
    assert err(ws.undo).code == "conflict"


def test_history_and_diff(ws):
    ws.create("h.txt", "a\n")
    ws.edit("h.txt", "a", "b")
    assert "edit    h.txt" in ws.history_text()
    assert "-a" in ws.diff() and "+b" in ws.diff()


def test_list_glob_search(ws):
    ws.create("src/app.py", "def main():\n    print('hi')\n")
    ws.create("src/util.py", "def helper():\n    pass\n")
    ws.create("node_modules/x.js", "ignored")
    listing = ws.list()
    assert "src/" in listing and "node_modules" not in listing
    assert ws.glob("*.py").splitlines() == ["src/app.py", "src/util.py"]
    assert "src/app.py:2:" in ws.search(r"print\(")
    assert err(ws.search, "(").code == "bad_regex"


def test_outline(ws):
    ws.create("o.py", "class A:\n    def m(self):\n        pass\n\ndef f():\n    pass\n")
    out = ws.outline("o.py")
    assert "class A" in out and "  def m" in out and "def f" in out
    ws.create("doc.md", "# Title\n```\n# not heading\n```\n## Sub\n")
    out = ws.outline("doc.md")
    assert "Title" in out and "Sub" in out and "not heading" not in out
    ws.create("a.ts", "export async function load() {}\nexport class Store {}\n")
    assert "function load" in ws.outline("a.ts") and "class Store" in ws.outline("a.ts")
