import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from yworkspace.app import build_session
from yworkspace.config import Config


def test_verify_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=proj)
    sess = build_session(proj, Config(sandbox="local"), with_engine=False)
    call = sess.registry.call
    sess.workspace.create("calc.py", "def add(a, b):\n    return a + b\n")
    sess.workspace.create("test_calc.py", "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    out = call("check", {"kind": "test"}).text
    assert "pytest" in out and "PASSED" in out
    assert "calc.py" in call("git_status", {}).text
    assert "+def add" in call("git_diff", {}).text or "calc.py" in call("git_diff", {}).text
    call("git_commit", {"message": "add calc"})
    assert "add calc" in call("git_log", {}).text

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r = call("http_local", {"url": f"http://127.0.0.1:{srv.server_address[1]}/health"})
    assert "HTTP 200" in r.text and '"ok": true' in r.text
    assert call("http_local", {"url": "https://example.com"}).is_error
    srv.shutdown()

    assert "OK" in call("db_query", {"sql": "create table t(x int)"}).text
    call("db_query", {"sql": "insert into t values (42)"})
    assert "42" in call("db_query", {"sql": "select * from t"}).text
    assert call("db_query", {"sql": "select 1", "database": "notes.txt"}).is_error
