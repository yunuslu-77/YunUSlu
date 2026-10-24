import json
import struct
import zlib

from yworkspace.operator.android import AndroidScreen, adb_text, parse_hierarchy
from yworkspace.operator.appium import AppiumScreen
from yworkspace.operator.desktop import DesktopScreen
from yworkspace.operator.vm import key_combo, ppm_to_png
from yworkspace.operator.web import PERSONAS

DUMP = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation="0">
<node index="0" text="" class="android.widget.FrameLayout" bounds="[0,0][1080,2340]" clickable="false">
 <node text="Hoş geldiniz" class="android.widget.TextView" bounds="[100,200][980,300]" clickable="false"/>
 <node text="" resource-id="com.yunuslu.app:id/email" class="android.widget.EditText" bounds="[100,400][980,520]"
       clickable="true" password="false"/>
 <node text="" content-desc="" class="android.widget.ImageButton" bounds="[20,40][60,80]" clickable="true"/>
 <node text="Giriş yap" class="android.widget.Button" bounds="[100,600][980,720]" clickable="true" enabled="true"/>
 <node text="Beni hatırla" class="android.widget.CheckBox" bounds="[100,760][400,820]" checkable="true" checked="true"/>
</node></hierarchy>"""


def test_parse_android_hierarchy():
    els = parse_hierarchy("garbage before " + DUMP)
    names = [(e.role, e.name) for e in els]
    assert ("text", "Hoş geldiniz") in names and ("button", "Giriş yap") in names
    email = next(e for e in els if "id=email" in e.extra)
    assert email.role == "edit" and (email.x, email.y) == (540, 460)
    assert "checked" in next(e for e in els if e.role == "checkbox").extra


def test_android_actions_produce_real_adb_commands(tmp_path):
    calls = []

    def fake(args, binary=False, timeout=120):
        calls.append(args)
        if args[:1] == ["devices"]:
            return "List of devices attached\nemulator-5554\tdevice\n"
        if "uiautomator" in args:
            return DUMP
        if args[:2] == ["shell", "wm"]:
            return "Physical size: 1080x2340"
        if "screencap" in args:
            return None
        return ""

    scr = AndroidScreen(tmp_path, PERSONAS["impatient"], runner=fake)
    text, _ = scr.open("com.yunuslu.app")
    assert "[4] button \"Giriş yap\"" in text
    scr.type(2, "a b&c")
    scr.click(4)
    scr.type(2, "çiçek")
    scr.scroll("down")
    scr.back()
    a11y = scr.a11y()
    flat = [" ".join(c) for c in calls]
    assert any("monkey -p com.yunuslu.app" in c for c in flat)
    assert "shell input text a%sb\\&c" in flat
    assert flat.count("shell input tap 540 660") == 2  # impatient persona double-taps
    assert any("ADB_INPUT_TEXT" in c and "çiçek" in c for c in flat)
    assert any(c.startswith("shell input swipe 540") for c in flat)
    assert "shell input keyevent KEYCODE_BACK" in flat
    assert any("no accessible name" in i for i in a11y) and any("small touch target" in i for i in a11y)
    assert adb_text("hi there") == "hi%sthere"


def test_vm_helpers():
    w, h = 2, 1
    ppm = b"P6\n2 1\n255\n" + bytes([255, 0, 0, 0, 255, 0])
    png = ppm_to_png(ppm)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (w, h)
    idat_len = struct.unpack(">I", png[33:37])[0]
    raw = zlib.decompress(png[41:41 + idat_len])
    assert raw == b"\x00" + bytes([255, 0, 0, 0, 255, 0])
    assert key_combo("Control+Alt+Delete") == [{"type": "qcode", "data": "ctrl"}, {"type": "qcode", "data": "alt"},
                                              {"type": "qcode", "data": "delete"}]


class FakeA11y:
    def find_window(self, rx):
        return "win" if rx.search("Hesap Makinesi") else None

    def activate(self, w):
        pass

    def rect(self, w):
        return (100, 50, 400, 300)

    def nodes(self, w):
        class H:
            def __init__(self, x, y):
                self.BoundingRectangle = type("R", (), {"left": x, "top": y, "width": lambda s: 80, "height": lambda s: 40})()
        yield "button", "7", H(110, 100)
        yield "button", "=", H(300, 300)
        yield "text", "", H(0, 0)


class FakePG:
    def __init__(self):
        self.log = []

    def moveTo(self, x, y, duration=0):
        self.log.append(("move", x, y))

    def click(self):
        self.log.append(("click",))

    def doubleClick(self):
        self.log.append(("dbl",))

    def screenshot(self, region=None):
        class Img:
            def save(self, buf, fmt):
                buf.write(b"\x89PNG")
        return Img()


def test_desktop_uses_window_relative_elements_and_absolute_clicks(tmp_path):
    pg = FakePG()
    scr = DesktopScreen(tmp_path, PERSONAS["first_time"], backend=FakeA11y(), pyautogui=pg)
    text, _ = scr.open("hesap")
    assert '[1] button "7"' in text and '[2] button "="' in text
    assert (scr.el(1).x, scr.el(1).y) == (50, 70)  # relative to the window
    scr.click(2)
    assert ("move", 340, 320) in pg.log and ("click",) in pg.log  # absolute on screen


def test_appium_ios_session(tmp_path):
    src = ('<AppiumAUT><XCUIElementTypeApplication name="Not" x="0" y="0" width="390" height="844">'
           '<XCUIElementTypeTextField name="E-posta" x="20" y="100" width="350" height="44" visible="true"/>'
           '<XCUIElementTypeButton label="Giriş" x="20" y="200" width="350" height="50" visible="true"/>'
           '</XCUIElementTypeApplication></AppiumAUT>')
    sent = []

    class Client:
        def request(self, method, url, json=None):
            sent.append((method, url, json))
            path = url.split("/session", 1)[-1]
            if method == "POST" and path == "":
                value = {"sessionId": "S1"}
            elif path.endswith("/source"):
                value = src
            elif path.endswith("/window/rect"):
                value = {"width": 390, "height": 844}
            elif path.endswith("/screenshot"):
                import base64
                value = base64.b64encode(b"\x89PNG").decode()
            else:
                value = {}
            return type("R", (), {"status_code": 200, "json": lambda s: {"value": value}})()

    scr = AppiumScreen(tmp_path, PERSONAS["first_time"], client=Client())
    text, images = scr.open("com.yunuslu.not")
    assert '[2] button "Giriş"' in text and images
    scr.click(2)
    caps = sent[0][2]["capabilities"]["alwaysMatch"]
    assert caps["platformName"] == "iOS" and caps["appium:bundleId"] == "com.yunuslu.not"
    actions = next(j for m, u, j in sent if u.endswith("/actions"))
    assert actions["actions"][0]["actions"][0] == {"type": "pointerMove", "duration": 0, "x": 195, "y": 225}
    assert json.dumps(actions)
