import subprocess
import sys

import pytest

from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.engine.engine import AUTO, Approver


def test_saas_template_into_project_and_its_tests_pass(tmp_path, monkeypatch):
    for mod in ("fastapi", "sqlalchemy", "jinja2", "itsdangerous", "argon2", "multipart"):
        pytest.importorskip(mod, reason="install saas_kit/templates/fastapi-saas/requirements.txt")
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    sess = build_session(tmp_path / "salon", Config(sandbox="local"), with_engine=False)
    out = sess.registry.call("saas_templates", {}).text
    assert "fastapi-saas" in out and "iyzico" in out
    r = sess.registry.call("saas_new", {"template": "fastapi-saas", "project_name": "Kuaför Randevu"})
    assert not r.is_error, r.text
    root = sess.workspace.root
    assert "Kuaför Randevu" in (root / "README.md").read_text()
    assert "{{project_name}}" not in (root / "app/settings.py").read_text()
    res = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=root, capture_output=True, text=True,
                         timeout=300)
    assert res.returncode == 0, res.stdout[-2000:]
    again = sess.registry.call("saas_new", {"template": "fastapi-saas", "project_name": "x"})
    assert again.is_error and "already exists" in again.text


def test_vps_deploy_prepare_and_run(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    sess = build_session(tmp_path / "app", Config(sandbox="local"), with_engine=False)
    call = sess.registry.call
    opts = {"host": "203.0.113.10", "domain": "app.example.com", "user": "deploy"}
    out = call("deploy_prepare", {"name": "vps", "options": opts}).text
    root = sess.workspace.root
    assert "app.example.com" in (root / "deploy/Caddyfile").read_text()
    assert "reverse_proxy app:8000" in (root / "deploy/Caddyfile").read_text()
    assert "deploy@203.0.113.10" in (root / "deploy/deploy.sh").read_text()
    assert ".env.production" in out and "MISSING" in out
    assert call("deploy_run", {"name": "vps", "options": opts}).is_error  # prerequisites missing
    (root / ".env.production").write_text("SECRET_KEY=x\n")
    ran = []
    sess.deploy_runner["fn"] = lambda cmd, cwd: (ran.append(cmd), (0, "deployed"))[1]
    monkeypatch.setattr("shutil.which", lambda exe: "/usr/bin/" + exe)
    import yworkspace.deploy.tools as dt
    monkeypatch.setattr(dt.time, "sleep", lambda s: None)
    res = call("deploy_run", {"name": "vps", "options": {**opts, "domain": ""}})
    assert ran == ["bash deploy/deploy.sh"] and "deployed" in res.text


def test_deploy_always_needs_approval_even_in_auto(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))

    class No(Approver):
        asked = []

        def approve(self, kind, summary):
            self.asked.append(summary)
            return False, "not now"

    cfg = Config(sandbox="local", autonomy=AUTO)
    sess = build_session(tmp_path / "app", cfg, approver=No())
    r = sess.registry.call("deploy_run", {"name": "vercel"})
    assert r.is_error and "did not approve" in r.text and "not now" in r.text
    assert No.asked and "deploy_run" in No.asked[0]
    assert not sess.registry.call("deploy_targets", {}).is_error
