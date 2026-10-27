import json
import threading
import urllib.request

import pytest

from yworkspace.bridge.desktop import AppProfile, BridgeRunner, BridgeStopped
from yworkspace.core import Workspace
from yworkspace.interfaces.relay import Relay
from yworkspace.protocol.session import TextSession
from yworkspace.tools.builtin import build_registry


class FakeChatApp:
    """Simulates a desktop chat app: replies appear after the user presses Enter."""

    def __init__(self, replies, foreground=True):
        self.replies = list(replies)
        self.messages: list[str] = []
        self.sent: list[str] = []
        self.clip = "user's own clipboard"
        self.input = ""
        self.foreground = foreground
        self.stop = False
        self.activated = 0

    # Driver protocol
    def find_window(self, title):
        return "win"

    def is_foreground(self, w):
        return self.foreground

    def activate(self, w):
        self.activated += 1

    def focus_input(self, w, how):
        pass

    def paste(self, text):
        self.input = self.clip

    def press(self, keys):
        self.sent.append(self.input)
        nxt = self.replies.pop(0) if self.replies else "OK"
        self.messages.append(nxt(self.input) if callable(nxt) else nxt)

    def reply_count(self, w, profile):
        return len(self.messages)

    def last_reply(self, w, profile):
        return self.messages[-1] if self.messages else ""

    def is_busy(self, w, profile):
        return False

    def clipboard_get(self):
        return self.clip

    def clipboard_set(self, text):
        self.clip = text

    def user_active_since(self, t):
        return False

    def stop_requested(self):
        return self.stop


def profile():
    return AppProfile("Fake", "Fake", settle_seconds=0.0)


def test_bridge_runner_full_loop(tmp_path):
    ws = Workspace(tmp_path / "p")
    app = FakeChatApp([
        '```\n<<<yw:create path="a.py">>>\nprint(1)\n>>>end\n```',
        lambda sent: "Done, created a.py." if 'ok="true"' in sent else "??",
    ])
    runner = BridgeRunner(app, profile(), TextSession(build_registry(ws), goal="create a.py"), poll=0.01)
    assert runner.run() == "done"
    assert (ws.root / "a.py").read_text(encoding="utf-8") == "print(1)\n"
    assert "<<<yw:" in app.sent[0]  # opening carried the protocol
    assert app.clip == "user's own clipboard"  # clipboard restored


def test_bridge_refuses_wrong_window_and_emergency_stop(tmp_path):
    ws = Workspace(tmp_path / "p")
    app = FakeChatApp(["x"], foreground=False)
    with pytest.raises(BridgeStopped, match="not in front"):
        BridgeRunner(app, profile(), TextSession(build_registry(ws)), poll=0.01).run()
    assert app.sent == [] and app.activated == 1
    app2 = FakeChatApp(["x"])
    app2.stop = True
    with pytest.raises(BridgeStopped, match="emergency"):
        BridgeRunner(app2, profile(), TextSession(build_registry(ws)), poll=0.01).run()


def test_bridge_splits_long_messages(tmp_path):
    ws = Workspace(tmp_path / "p")
    app = FakeChatApp(["OK", "OK", "OK", "OK", "OK", "finished"])
    prof = profile()
    prof.max_chars = 1500
    BridgeRunner(app, prof, TextSession(build_registry(ws), goal="x" * 3000), poll=0.01).run()
    assert len(app.sent) >= 3 and app.sent[0].startswith("[Part 1/")


def test_profiles_load():
    for name in ("deepseek", "chatgpt", "claude", "gemini", "generic"):
        assert AppProfile.load(name).window_title


def test_relay_http(tmp_path):
    ws = Workspace(tmp_path / "p")
    relay = Relay(lambda goal: TextSession(build_registry(ws), goal=goal), token="T")
    httpd = relay.make_server(port=0)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def post(path, body, token="T"):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "X-YW-Token": token})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=5).read())
        except urllib.error.HTTPError as e:
            return {"status": e.code}

    import os
    os.environ["NO_PROXY"] = "127.0.0.1"
    assert post("/start", {"goal": "g"}, token="bad") == {"status": 401}
    start = post("/start", {"goal": "make b.txt"})
    assert "make b.txt" in start["messages"][-1]
    r = post("/reply", {"text": '<<<yw:create path="b.txt">>>\nhey\n>>>end'})
    assert r["calls"] == 1 and not r["done"] and (ws.root / "b.txt").exists()
    assert post("/reply", {"text": "finished"})["done"] is True
    httpd.shutdown()
