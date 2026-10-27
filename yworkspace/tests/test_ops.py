import json
import os
import ssl
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.models.scripted import ScriptedProvider, say
from yworkspace.ops.monitor import Monitor, error_signatures

LOG = """INFO started
ERROR 2026-10-24 12:00:01 boom
Traceback (most recent call last):
  File "app.py", line 3, in handler
ZeroDivisionError: division by zero
INFO ok
Traceback (most recent call last):
  File "app.py", line 3, in handler
ZeroDivisionError: division by zero
"""


class Up(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


def serve(handler=Up, tls=None):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(*tls)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_monitor_checks_and_incidents(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    root = tmp_path / "p"
    (root / ".yw").mkdir(parents=True)
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                    "-days", "10", "-subj", "/CN=127.0.0.1"], capture_output=True, check=True)
    up, tls = serve(), serve(tls=(str(cert), str(key)))
    (tmp_path / "app.log").write_text(LOG, encoding="utf-8")
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "db-old.sql").write_text("x", encoding="utf-8")
    old = time.time() - 50 * 3600
    os.utime(backups / "db-old.sql", (old, old))
    mon = Monitor(root)
    mon.save_config({"urls": [f"http://127.0.0.1:{up.server_address[1]}/health", "http://127.0.0.1:9/down"],
                     "ssl_hosts": [f"127.0.0.1:{tls.server_address[1]}"], "insecure_tls": True,
                     "logs_cmd": f"cat '{(tmp_path / 'app.log').as_posix()}'", "disk_cmd": "df -P /", "backup_dir": str(backups),
                     "restore_test_cmd": "false"})
    res = mon.run_checks()
    names = {c.name: c for c in res.checks}
    up_checks = [c for c in res.checks if c.name.startswith("up ")]
    assert up_checks[0].ok and not up_checks[1].ok and "DOWN" in up_checks[1].detail
    ssl_check = next(c for c in res.checks if c.name.startswith("ssl"))
    assert not ssl_check.ok and 8 <= ssl_check.value <= 10  # expires in < 14 days
    assert not names["error logs"].ok and "1 distinct" in names["error logs"].detail
    assert not names["backups fresh"].ok and not names["backup restores"].ok
    kinds = sorted(i.kind for i in res.new_incidents)
    assert kinds == ["backup", "downtime", "error", "ssl"]
    again = mon.run_checks()
    assert again.new_incidents == []  # same problems are not new incidents
    mon.set_status(next(i.id for i in mon.incidents() if i.kind == "error"), "fixed")
    third = mon.run_checks()
    assert [i.kind for i in third.new_incidents] == ["error"]  # it came back
    report = mon.health_report()
    assert "Uptime: 50.00%" in report and "Incidents: 4" in report
    up.shutdown()
    tls.shutdown()


def test_error_grouping():
    groups = error_signatures(LOG)
    assert len(groups) == 1 and len(next(iter(groups.values()))) == 3


def test_server_agent_runs_locally(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    up = serve()
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "x.sql").write_text("x", encoding="utf-8")
    cfg = {"urls": [f"http://127.0.0.1:{up.server_address[1]}/"], "backup_dir": str(tmp_path / "b"),
           "status_file": str(tmp_path / "status.json")}
    (tmp_path / "agent.json").write_text(json.dumps(cfg), encoding="utf-8")
    agent = Path(__file__).resolve().parents[1] / "src/yworkspace/ops/agent/yw_agent.py"
    r = subprocess.run([sys.executable, str(agent), str(tmp_path / "agent.json")], capture_output=True, text=True)
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["checks"]["backups"]["ok"] and status["checks"][f"url {cfg['urls'][0]}"]["ok"]
    assert r.returncode in (0, 1)
    up.shutdown()


def test_incident_fix_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    root = tmp_path / "app"
    sess = build_session(root, Config(sandbox="local", autonomy="auto", quality="economy"))
    ws = sess.workspace
    ws.create("calc.py", "def ratio(a, b):\n    return a / b\n")
    ws._seen.clear()
    mon = Monitor(root)
    inc = mon.record("error", "ZeroDivisionError: division by zero", LOG)
    dev = ScriptedProvider([
        say("", ("read", {"path": "calc.py"})),
        say("", ("edit", {"path": "calc.py", "find": "    return a / b", "replace":
                           "    if b == 0:\n        return 0.0\n    return a / b"}),
            ("create", {"path": "test_calc.py", "content": "from calc import ratio\n\n\ndef test_zero():\n"
                                                           "    assert ratio(1, 0) == 0.0\n"})),
        say("", ("run", {"command": "python -m pytest -q"})),
        say("", ("plan_update", {"status": "done", "evidence": "1 passed"})), say("fixed")])
    sess.engine.router = None
    sess.engine.provider_for = lambda role: dev if role == "developer" else ScriptedProvider([])
    out = sess.registry.call("incident_fix", {"incident_id": inc.id, "deploy": False}).text
    assert "DONE" in out, out
    assert next(i for i in Monitor(root).incidents() if i.id == inc.id).status == "fixed"
    assert "b == 0" in (root / "calc.py").read_text(encoding="utf-8")
