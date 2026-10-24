import json
import shutil
import struct

import pytest

from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.core.errors import ToolError
from yworkspace.studio import audio, image, licenses, render, three_d, video

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")


def _playwright_ok():
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


needs_browser = pytest.mark.skipif(not _playwright_ok(), reason="Playwright not installed")


def session(tmp_path, monkeypatch, name="medya", engine=False):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    return build_session(tmp_path / name, Config(sandbox="local"), with_engine=engine)


def test_midi_file_is_valid(tmp_path):
    out = audio.write_midi([{"program": 0, "notes": [["C4", 1], [["C4", "E4", "G4"], 2], ["R", 0.5], ["Bb5", 1]]}],
                           120, tmp_path / "a.mid")
    data = out.read_bytes()
    assert data[:4] == b"MThd" and struct.unpack(">HHH", data[8:14]) == (1, 1, 480)
    assert data[14:18] == b"MTrk" and data.endswith(b"\x00\xff\x2f\x00")
    assert audio.note_number("C4") == 60 and audio.note_number("F#3") == 54 and audio.note_number("R") == -1


def test_box_stl_and_licenses(tmp_path):
    p = three_d.box_stl(40, 20, 10, tmp_path / "box.stl")
    assert three_d.stl_triangles(p) == 12 and p.stat().st_size == 84 + 12 * 50
    warn = licenses.check(["MusicGen", "FLUX.1-dev", "FLUX.1-schnell", "BilinmeyenModel"], commercial=True)
    assert any("MusicGen" in w and "NOT allow commercial" in w for w in warn)
    assert any("FLUX.1-dev" in w and "NOT" in w for w in warn)
    assert not any(w.startswith("FLUX.1-schnell") for w in warn)
    assert any("unknown" in w for w in warn)


def test_speak_without_engines_says_how(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(audio, "get_secret", lambda name: None)
    with pytest.raises(ToolError) as e:
        audio.speak("merhaba", tmp_path / "v.wav")
    assert e.value.code == "no_tts" and "Piper" in e.value.hint


def test_app_icons_and_image_edit(tmp_path):
    from PIL import Image
    src = tmp_path / "logo.png"
    Image.new("RGBA", (600, 400), (40, 110, 220, 255)).save(src)
    files = image.app_icons(src, tmp_path / "icons", "yapp")
    names = {f.relative_to(tmp_path / "icons").as_posix() for f in files}
    assert "android/mipmap-xxxhdpi/ic_launcher.png" in names
    assert "android/mipmap-mdpi/ic_launcher_foreground.png" in names
    assert "ios/AppIcon.appiconset/icon-1024@1x.png" in names and "ios/AppIcon.appiconset/icon-83.5@2x.png" in names
    assert "windows/yapp.ico" in names and "web/favicon.ico" in names
    contents = json.loads((tmp_path / "icons/ios/AppIcon.appiconset/Contents.json").read_text())
    for img in contents["images"]:
        assert (tmp_path / "icons/ios/AppIcon.appiconset" / img["filename"]).exists()
    with Image.open(tmp_path / "icons/ios/AppIcon.appiconset/icon-1024@1x.png") as big:
        assert big.size == (1024, 1024) and big.mode == "RGB"
    with Image.open(tmp_path / "icons/android/mipmap-xxxhdpi/ic_launcher.png") as a:
        assert a.size == (192, 192)
    out = image.edit(src, tmp_path / "e.jpg", [{"op": "fit", "w": 300, "h": 300}, {"op": "text", "text": "Şirket"},
                                                {"op": "grayscale"}])
    with Image.open(out) as e:
        assert e.size == (300, 300) and e.mode in ("L", "RGB")
    assert "300x300" in image.describe_basic(out)
    with pytest.raises(ToolError):
        image.edit(src, tmp_path / "x.png", [{"op": "uçur"}])


@needs_ffmpeg
def test_music_and_sound_effects(tmp_path):
    out, engine = audio.render_music([{"notes": [["C4", 1], ["E4", 1], [["G4", "C5"], 2]]}], 120, tmp_path / "m.wav")
    assert out.exists() and (tmp_path / "m.mid").exists()
    assert abs(audio.tone_seconds(out) - 2.0) < 0.15, audio.tone_seconds(out)
    fx = audio.sound_effect("success", tmp_path / "ok.wav")
    assert abs(audio.tone_seconds(fx) - 0.6) < 0.1
    with pytest.raises(ToolError):
        audio.sound_effect("patlama", tmp_path / "x.wav")


@needs_ffmpeg
@needs_browser
def test_compose_video_with_music_and_subtitles(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch)
    call = sess.registry.call
    music = call("music", {"tracks": [{"notes": [["C4", 1], ["E4", 1], ["G4", 1], ["C5", 1]] * 2}], "bpm": 120,
                           "out": "media/muzik.wav"})
    assert not music.is_error, music.text
    html = "<div style='display:flex;height:100%;align-items:center;justify-content:center;background:{c};" \
           "color:#fff;font:bold 120px sans-serif'>{t}</div>"
    r = call("video_compose", {"scenes": [
        {"html": html.format(c="#2f6fe4", t="Merhaba"), "duration": 2.5, "subtitle": "İlk sahne"},
        {"html": html.format(c="#e4572f", t="yWorkspace"), "duration": 2.5, "subtitle": "İkinci sahne"}],
        "out": "media/tanitim.mp4", "format": "9:16", "music": "media/muzik.wav", "title": "Tanıtım"})
    assert not r.is_error, r.text
    assert "Inspection: PASS" in r.text, r.text
    root = sess.workspace.root
    info = video.probe(root / "media/tanitim.mp4")
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert "AI-generated" in json.dumps(info["format"].get("tags", {}))
    assert "İkinci sahne" in (root / "media/tanitim.srt").read_text("utf-8")
    social = call("export_social", {"src": "media/tanitim.mp4", "formats": ["16:9", "1:1"]})
    assert not social.is_error and social.text.count("PASS") == 2, social.text
    frames = video.extract_frames(root / "media/tanitim.mp4", tmp_path / "frames", 3)
    assert len(frames) == 3 and all(f.exists() for f in frames)
    understood = call("image_understand", {"path": "media/tanitim-square.mp4"})
    assert not understood.is_error and "Frame 1" in understood.text


@needs_browser
def test_render_and_chart(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch)
    r = sess.registry.call("chart", {"kind": "bar", "labels": ["Oca", "Şub", "Mar"], "values": [12, 30, 21],
                                     "out": "grafik/satis", "title": "Satışlar"})
    assert not r.is_error and r.images, r.text
    svg = (sess.workspace.root / "grafik/satis.svg").read_text("utf-8")
    assert "Satışlar" in svg and svg.count("<rect") == 4
    png = render.html_to_png("<h1>Logo</h1>", tmp_path / "l.png", 200, 100)
    from PIL import Image
    with Image.open(png) as im:
        assert im.size == (200, 100)


@needs_ffmpeg
def test_media_gate_catches_black_video(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch, engine=True)
    root = sess.workspace.root
    (root / "media").mkdir()
    video.ff(["-f", "lavfi", "-i", "color=c=white:s=320x240:d=2", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=3",
              "-f", "lavfi", "-i", "color=c=white:s=320x240:d=2", "-filter_complex",
              "[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p[v]", "-map", "[v]", str(root / "media/kotu.mp4")])
    monkeypatch.setattr(sess.engine, "changed_files", lambda: ["media/kotu.mp4"])
    gate = next(g for g in sess.engine.extra_gates if g(sess.engine).name == "media files pass inspection")
    res = gate(sess.engine)
    assert not res.passed and "black frames" in res.detail, res.detail
