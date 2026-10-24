import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.labs.security import dast
from yworkspace.labs.security.tools import quick_scan

TEMPLATE = Path(__file__).resolve().parents[1] / "src/yworkspace/saas_kit/templates/fastapi-saas"

# The fake key is assembled at run time so the repository never contains a key-shaped string.
FAKE_STRIPE_KEY = "sk_" + "live_" + "51AbCdEfGhIjKlMnOpQrStUv"
VULN_PY = '''import os, pickle, subprocess, sqlite3
STRIPE = "FAKE_KEY"
def find(db, name):
    return db.execute(f"SELECT * FROM users WHERE name = '{name}'")
def run(cmd):
    subprocess.run("ls " + cmd, shell=True)
def load(data):
    return pickle.loads(data)
def calc(expr):
    return eval(expr)
'''


def make_vuln(root: Path):
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root)
    (root / "app.py").write_text(VULN_PY.replace("FAKE_KEY", FAKE_STRIPE_KEY))
    (root / "ui.js").write_text("el.innerHTML = userInput;\n")
    (root / "Dockerfile").write_text("FROM python\nCOPY . .\nCMD python app.py\n")
    (root / ".env").write_text("SECRET=abc\n")
    subprocess.run(["git", "add", "-A"], cwd=root)


def test_vulnerable_project_is_caught(tmp_path):
    root = tmp_path / "vuln"
    make_vuln(root)
    rules = {f.rule for f in quick_scan(root)}
    for expected in ("secret:stripe-live-key", "py:sql-injection", "py:shell-injection", "py:unsafe-deserialization",
                     "py:eval", "js:xss-innerhtml", "docker:runs-as-root", "secret:env-committed",
                     "config:env-not-ignored", "docker:unpinned-base"):
        assert expected in rules, expected


def test_saas_template_is_clean():
    bad = [f for f in quick_scan(TEMPLATE) if f.severity in ("critical", "high")]
    assert not bad, "\n".join(f.render() for f in bad)


def test_gate_and_deploy_block(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    root = tmp_path / "vuln"
    make_vuln(root)
    sess = build_session(root, Config(sandbox="local", quality="balanced", autonomy="auto"))
    out = sess.registry.call("security_scan", {"kind": "all"}).text
    assert "CRITICAL" in out and "Fix:" in out
    gate = next(g for g in sess.engine.extra_gates if "security" in g(sess.engine).name)
    assert not gate(sess.engine).passed
    (root / ".env.production").write_text("x=1\n")
    r = sess.registry.call("deploy_run", {"name": "vps", "options": {"host": "h", "domain": "d.example"}})
    assert r.is_error and ("security_block" in r.text or "denied" in r.text)


class VulnApp(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/.env":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"DB_PASSWORD=hunter2")
            return
        if "next" in q:
            self.send_response(302)
            self.send_header("Location", q["next"][0])
            self.end_headers()
            return
        body = "<p>" + (q.get("q", [""])[0]) + "</p>"
        if "'" in q.get("search", [""])[0]:
            body = "sqlite3.OperationalError: near \"'\": syntax error"
        self.send_response(200)
        self.send_header("Set-Cookie", "session=abc; Path=/")
        self.end_headers()
        self.wfile.write(body.encode())


def test_dast_against_local_vulnerable_app(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), VulnApp)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    rules = {f.rule for f in dast.scan_url(url)}
    srv.shutdown()
    for expected in ("dast:file-exposed", "dast:open-redirect", "dast:reflected-xss", "dast:sql-error",
                     "dast:cookie-not-httponly", "dast:clickjacking", "dast:no-nosniff"):
        assert expected in rules, (expected, rules)


def test_dast_refuses_foreign_hosts(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    sess = build_session(tmp_path / "p", Config(sandbox="local"), with_engine=False)
    r = sess.registry.call("security_scan", {"kind": "dast", "url": "https://example.com"})
    assert r.is_error and "own app" in r.text
