import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("playwright.sync_api")

from yworkspace.app import build_session  # noqa: E402
from yworkspace.config import Config  # noqa: E402

APP = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>Kayıt</title></head><body>
<h1>Hesap oluştur</h1>
<label for="email">E-posta</label><input id="email" placeholder="ornek@mail.com">
<input id="pw" type="password" placeholder="Şifre">
<img src="x.png">
<button id="go">Kayıt ol</button>
<p id="msg"></p>
<script>
document.getElementById('go').onclick = () => {
  const e = document.getElementById('email').value;
  document.getElementById('msg').textContent = e.includes('@') ? 'Hoş geldin ' + e : 'Geçersiz e-posta';
  if (!e.includes('@')) console.error('validation failed');
};
</script></body></html>"""


@pytest.fixture
def served(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(APP, "utf-8")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(site)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
    httpd.shutdown()


def test_human_like_web_usage(tmp_path, served, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    cfg = Config(sandbox="local")
    sess = build_session(tmp_path / "proj", cfg)
    call = sess.registry.call
    r = call("screen_open", {"target": served, "persona": "first_time"})
    assert not r.is_error, r.text
    assert r.images, "a labelled screenshot is attached for vision models"
    assert 'placeholder="ornek@mail.com"' in r.text and '"Kayıt ol"' in r.text
    lines = r.text.splitlines()
    n_email = next(ln for ln in lines if "ornek@mail.com" in ln).split("]")[0].strip("[")
    n_btn = next(ln for ln in lines if "Kayıt ol" in ln and "button" in ln).split("]")[0].strip("[")
    r = call("type", {"n": n_email, "text": "yunus@yunuslu.dev"})
    assert 'value="yunus@yunuslu.dev"' in r.text
    call("tap", {"n": n_btn})
    r = call("wait_for", {"text": "Hoş geldin"})
    assert not r.is_error and "Hoş geldin yunus@yunuslu.dev" in r.text
    a11y = call("a11y_check", {}).text
    assert "Image without alt text" in a11y and "Form field without a label" in a11y
    assert "Recorded journey" in call("journey_result", {"name": "Sign up", "passed": True}).text
    exp = call("journey_export", {"name": "Sign up"}).text
    assert "get_by_placeholder('ornek@mail.com').fill('yunus@yunuslu.dev')" in exp
    assert "get_by_role('button', name='Kayıt ol').click()" in exp
    assert (sess.workspace.root / "tests/e2e/test_sign_up.py").exists()
    assert "Video" in call("screen_close", {}).text

    # Journey gate: the spec's journeys must have been walked through.
    eng = sess.engine
    (sess.workspace.root / "index.html").write_text("<html></html>", encoding="utf-8")
    eng.state.spec = "# User journeys\n1. Sign up with email\n2. Delete my account\n"
    gate = next(r for r in (g(eng) for g in eng.extra_gates) if r.name.startswith("user journeys"))
    assert not gate.passed and "Delete my account" in gate.detail
    sess.close()


def test_invalid_input_and_console_errors(tmp_path, served, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    sess = build_session(tmp_path / "proj", Config(sandbox="local"), with_engine=False)
    call = sess.registry.call
    r = call("screen_open", {"target": served, "persona": "impatient"})
    n_btn = next(ln for ln in r.text.splitlines() if "Kayıt ol" in ln).split("]")[0].strip("[")
    r = call("tap", {"n": n_btn})
    assert "Geçersiz e-posta" in r.text and "validation failed" in r.text
    assert call("screen_open", {"target": served, "persona": "nobody"}).is_error
    sess.close()
