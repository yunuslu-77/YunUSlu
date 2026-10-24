"""End-to-end: the real browser extension (background worker + content script) in Chromium,
driving a fake chat page, talking to the real relay, which runs real tools."""

import json
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from yworkspace.core import Workspace
from yworkspace.interfaces.relay import Relay
from yworkspace.protocol.session import TextSession
from yworkspace.tools.builtin import build_registry

pw = pytest.importorskip("playwright.sync_api")

EXT = Path(__file__).resolve().parents[1] / "src" / "yworkspace" / "extension" / "browser"

FAKE_CHAT = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<textarea id="in"></textarea><button type="submit" id="send">Send</button><div id="log"></div>
<script>
let turn = 0;
document.getElementById('send').onclick = () => {
  const box = document.getElementById('in'); const sent = box.value; box.value = '';
  const u = document.createElement('div'); u.className = 'user'; u.textContent = sent; log.appendChild(u);
  setTimeout(() => {
    const d = document.createElement('div'); d.className = 'markdown';
    if (sent.startsWith('[Part') && !sent.includes('last part')) { d.textContent = 'OK'; }
    else if (turn === 0) {
      turn++;
      d.innerHTML = '<p>Dosyayı oluşturuyorum.</p><pre><code>&lt;&lt;&lt;yw:create path="web.txt"&gt;&gt;&gt;\\n' +
        'tarayıcıdan merhaba\\n&gt;&gt;&gt;end</code></pre>';
    } else {
      d.textContent = sent.includes('ok="true"') ? 'Bitti, web.txt oluşturuldu.' : 'Bir sorun var.';
    }
    log.appendChild(d);
  }, 300);
};
</script></body></html>"""


def test_extension_drives_chat(tmp_path):
    # Test copy of the extension that also matches the local fake chat page.
    ext = tmp_path / "ext"
    shutil.copytree(EXT, ext)
    manifest = json.loads((ext / "manifest.json").read_text())
    manifest["content_scripts"][0]["matches"].append("http://127.0.0.1/*")
    (ext / "manifest.json").write_text(json.dumps(manifest))

    site = tmp_path / "site"
    site.mkdir()
    (site / "chat.html").write_text(FAKE_CHAT, "utf-8")
    web = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(site)))
    threading.Thread(target=web.serve_forever, daemon=True).start()

    ws = Workspace(tmp_path / "proj")
    relay = Relay(lambda goal: TextSession(build_registry(ws), goal=goal, max_message_chars=4000), token="tok")
    rs = relay.make_server(port=0)
    threading.Thread(target=rs.serve_forever, daemon=True).start()

    with pw.sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                str(tmp_path / "profile"), headless=True, channel="chromium",
                args=[f"--disable-extensions-except={ext}", f"--load-extension={ext}", "--no-proxy-server"])
        except Exception as e:  # pragma: no cover
            pytest.skip(f"Chromium with extensions unavailable: {e}")
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{web.server_address[1]}/chat.html")
        sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker", timeout=10000)
        page.wait_for_timeout(500)
        sw.evaluate("""([port]) => chrome.tabs.query({}).then(tabs => Promise.allSettled(tabs.map(t =>
            chrome.tabs.sendMessage(t.id, {type: 'yw-start', token: 'tok', port, goal: 'web.txt yaz'}))))""",
                    [rs.server_address[1]])
        page.wait_for_function("document.body.innerText.includes('Bitti ✓')", timeout=60000)
        ctx.close()
    web.shutdown()
    rs.shutdown()
    assert (ws.root / "web.txt").read_text("utf-8") == "tarayıcıdan merhaba\n"
