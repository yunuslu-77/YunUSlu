"""Media Studio tools: the AI is the director, these tools are the crew."""

from __future__ import annotations

import base64
from pathlib import Path

from ..core.errors import ToolError
from ..engine.engine import GateResult
from ..extensions import register, register_gate
from ..models.base import Message
from ..tools.registry import EXTERNAL, SAFE, WRITE, Tool, ToolResult, obj
from . import audio, image, licenses, render, three_d, video

S = {"type": "string"}
N = {"type": "number"}
INT = {"type": "integer"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}


def _vision_provider(session):
    """A vision-capable model the user has, to describe images for text-only models."""
    eng = session.engine
    router = getattr(eng, "router", None) if eng else None
    if router is None:
        return None
    for prof in router.available():
        if prof.vision:
            return router.provider(prof.id)
    return None


@register
def install(session) -> None:
    reg, ws = session.registry, session.workspace

    def P(path: str) -> Path:
        return ws.resolve(path)

    def internal(path: str) -> Path:
        """Scratch files under .yw/media (the workspace tools refuse .yw paths on purpose)."""
        p = ws.root / ".yw" / "media" / path
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def rel(p: Path) -> str:
        return ws.rel(Path(p).resolve())

    def render_html(html: str, out: str, width: int = 1280, height: int = 720, background: str = "#ffffff") -> ToolResult:
        p = render.html_to_png(html, P(out), width, height, background)
        return ToolResult("render_html", f"Rendered {rel(p)} ({width}x{height}).",
                          images=[base64.b64encode(p.read_bytes()).decode()])

    def chart(kind: str, labels: list[str], values: list[float], out: str, title: str = "", unit: str = "") -> ToolResult:
        svg = render.svg_chart(kind, labels, values, title, unit=unit)
        svg_path = P(out).with_suffix(".svg")
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(svg, "utf-8")
        png = render.html_to_png(svg, P(out).with_suffix(".png"), 960, 540)
        return ToolResult("chart", f"Wrote {rel(svg_path)} and {rel(png)}.",
                          images=[base64.b64encode(png.read_bytes()).decode()])

    def diagram(mermaid: str, out: str) -> str:
        p = render.diagram_png(mermaid, P(out))
        return f"Rendered {rel(p)} (Mermaid, needs internet once to load mermaid.js)."

    def animation(html: str, out: str, seconds: float = 5, width: int = 1280, height: int = 720) -> str:
        webm = render.record_animation(html, P(out).with_suffix(".webm"), seconds, width, height)
        if P(out).suffix == ".mp4":
            video.ff(["-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
                      str(P(out))])
            webm.unlink()
            return f"Recorded {out} ({seconds}s)."
        return f"Recorded {rel(webm)} ({seconds}s)."

    def video_compose(scenes: list[dict], out: str, format: str = "16:9", music: str = "",
                      burn_subtitles: bool = True, title: str = "", voice_lang: str = "tr") -> str:
        built = []
        notes = []
        for i, sc in enumerate(scenes):
            img = sc.get("image")
            if sc.get("html"):
                w, h = video.FORMATS.get(format, (1920, 1080))
                img = str(render.html_to_png(sc["html"], internal(f"scene{i:02d}.png"), w, h))
            voice = sc.get("voice")
            if sc.get("narration") and not voice:
                try:
                    voice, engine = audio.speak(sc["narration"], internal(f"voice{i:02d}.wav"), voice_lang)
                    voice = str(voice)
                    notes.append(f"scene {i + 1}: narration by {engine}")
                except ToolError as e:
                    notes.append(f"scene {i + 1}: no narration ({e.message})")
            dur = float(sc.get("duration") or 0)
            if voice and not dur:
                dur = audio.tone_seconds(Path(voice)) + 0.6
            built.append(video.Scene(dur or 4.0, str(P(img)) if img and not Path(img).is_absolute() else img,
                                     str(P(sc["video"])) if sc.get("video") else None, sc.get("subtitle", ""),
                                     voice))
        spec = video.ComposeSpec(built, P(out), video.FORMATS.get(format, (1920, 1080)),
                                 music=str(P(music)) if music else None, burn_subtitles=burn_subtitles, title=title)
        result = video.compose(spec)
        total = sum(s.duration for s in built)
        check = video.inspect(result, total, spec.size, expect_audio=True,
                              srt=result.with_suffix(".srt") if any(s.subtitle for s in built) else None)
        return (f"Composed {rel(result)} ({total:.1f}s, {format}).\n" + "\n".join(notes) +
                f"\nInspection: {check.text()}")

    def video_edit(src: str, out: str, start: float | None = None, end: float | None = None, speed: float = 1.0,
                   watermark: str = "", mute: bool = False, reframe: str = "") -> str:
        p = video.edit(P(src), P(out), start, end, speed, str(P(watermark)) if watermark else None, mute)
        if reframe:
            tmp = p.with_name(p.stem + ".reframed" + p.suffix)
            video.reframe(p, tmp, reframe)
            tmp.replace(p)
        return f"Wrote {rel(p)}. {video.inspect(p).text()}"

    def export_social(src: str, formats: list[str] | None = None) -> str:
        out = []
        for fmt in formats or ["16:9", "9:16", "1:1"]:
            name = {"16:9": "youtube", "9:16": "reels-shorts-tiktok", "1:1": "square", "4:5": "feed"}[fmt]
            dest = P(src).with_name(f"{P(src).stem}-{name}.mp4")
            video.reframe(P(src), dest, fmt)
            out.append(f"{rel(dest)}: {video.inspect(dest, expect_size=video.FORMATS[fmt]).text()}")
        return "\n".join(out)

    def media_inspect(path: str, expect_duration: float | None = None, expect_audio: bool | None = None) -> str:
        p = P(path)
        srt = p.with_suffix(".srt")
        return video.inspect(p, expect_duration, None, expect_audio, srt if srt.exists() else None).text()

    def speak(text: str, out: str, lang: str = "tr", voice: str = "") -> str:
        p, engine = audio.speak(text, P(out), lang, voice or None)
        return f"Wrote {rel(p)} ({audio.tone_seconds(p):.1f}s) with {engine}."

    def transcribe(path: str, lang: str = "", srt: str = "") -> str:
        text, segs = audio.transcribe(P(path), lang or None, P(srt) if srt else None)
        return f"{len(segs)} segments.\n{text[:6000]}"

    def music(tracks: list[dict], bpm: int, out: str, soundfont: str = "") -> str:
        p, engine = audio.render_music(tracks, bpm, P(out), str(P(soundfont)) if soundfont else None)
        return f"Wrote {rel(p)} and {rel(p.with_suffix('.mid'))} ({audio.tone_seconds(p):.1f}s) with {engine}."

    def sound_effect(kind: str, out: str, seconds: float = 0.6) -> str:
        return f"Wrote {rel(audio.sound_effect(kind, P(out), seconds))}."

    def image_generate(prompt: str, out: str, size: str = "1024x1024", commercial: bool = False) -> ToolResult:
        p, engine = image.generate(prompt, P(out), size)
        return ToolResult("image_generate", f"Wrote {rel(p)} with {engine}. Marked as AI-generated.",
                          images=[base64.b64encode(p.read_bytes()).decode()])

    def image_edit(src: str, out: str, ops: list[dict]) -> ToolResult:
        p = image.edit(P(src), P(out), ops)
        return ToolResult("image_edit", f"Wrote {rel(p)}.", images=[base64.b64encode(p.read_bytes()).decode()])

    def image_understand(path: str, question: str = "Describe this image in detail.") -> str:
        p = P(path)
        if p.suffix.lower() in VIDEO_EXT:
            return video_understand(path, question)
        provider = _vision_provider(session)
        basic = image.describe_basic(p)
        if provider is None:
            return f"No vision model available (add a key for a vision model such as Gemini or Claude).\n{basic}"
        b64 = base64.b64encode(p.read_bytes()).decode()
        r = provider.chat([Message("user", question, images=[b64])], None, 2000)
        return f"{r.message.content}\n\n(Technical: {basic})"

    def video_understand(path: str, question: str = "What happens in this video?") -> str:
        p = P(path)
        frames = video.extract_frames(p, internal(f"frames-{p.stem}/x").parent, 6)
        provider = _vision_provider(session)
        parts = [f"Video {rel(p)}: {video.inspect(p).text()}"]
        for i, f in enumerate(frames):
            if provider is not None:
                r = provider.chat([Message("user", f"Frame {i + 1}/6 of a video. {question} Be concise.",
                                           images=[base64.b64encode(f.read_bytes()).decode()])], None, 600)
                parts.append(f"Frame {i + 1}: {r.message.content}")
            else:
                parts.append(f"Frame {i + 1}: {image.describe_basic(f)}")
        try:
            text, _ = audio.transcribe(p)
            parts.append("Speech: " + text[:3000])
        except ToolError as e:
            parts.append(f"Speech: not transcribed ({e.message})")
        return "\n".join(parts)

    def app_icons(src: str, out_dir: str = "assets/icons", name: str = "app") -> str:
        files = image.app_icons(P(src), P(out_dir), name)
        return f"Wrote {len(files)} icon files (Android, iOS, web/PWA, Windows .ico, macOS .icns) under {out_dir}."

    def model_3d(kind: str, out: str, code: str = "", size: list[float] | None = None) -> str:
        if kind == "openscad":
            return f"Wrote {rel(three_d.openscad(code, P(out)))}."
        if kind == "blender":
            return f"Wrote {rel(three_d.blender(code, P(out)))}."
        if kind == "box":
            w, d, h = (size or [40, 20, 10])[:3]
            p = three_d.box_stl(w, d, h, P(out))
            return f"Wrote {rel(p)} ({three_d.stl_triangles(p)} triangles, {w}x{d}x{h} mm)."
        if kind == "threejs":
            html = ("<!doctype html><html><body style='margin:0'><script type='module'>\nimport * as THREE from "
                    "'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';\n" + code + "\n</script></body></html>")
            P(out).write_text(html, "utf-8")
            return f"Wrote {out} (open it in a browser)."
        raise ToolError("bad_kind", "kind must be openscad, blender, box or threejs")

    def media_licenses(models: list[str], commercial: bool = False) -> str:
        warnings = licenses.check(models, commercial)
        return "\n".join(warnings) or "All listed models allow this use."

    tools = [
        Tool("render_html", "Draw anything with HTML/CSS/SVG and save it as PNG (logos, illustrations, social posts, "
             "slides, infographics). No image model needed.",
             obj({"html": S, "out": S, "width": INT, "height": INT, "background": S}, ["html", "out"]),
             render_html, WRITE, "media", "html"),
        Tool("chart", "Bar or line chart (SVG + PNG).", obj({"kind": {"type": "string", "enum": ["bar", "line"]},
             "labels": {"type": "array", "items": S}, "values": {"type": "array", "items": N}, "out": S, "title": S,
             "unit": S}, ["kind", "labels", "values", "out"]), chart, WRITE, "media"),
        Tool("diagram", "Mermaid diagram → PNG (flowchart, sequence, ER, gantt, mindmap).",
             obj({"mermaid": S, "out": S}, ["mermaid", "out"]), diagram, WRITE, "media", "mermaid"),
        Tool("animation", "Record an HTML/CSS/JS animation as a video (motion graphics, animated titles).",
             obj({"html": S, "out": S, "seconds": N, "width": INT, "height": INT}, ["html", "out"]), animation, WRITE,
             "media", "html"),
        Tool("video_compose", "Make a finished video from scenes. Each scene: html (drawn) or image or video, "
             "duration, subtitle, narration (spoken text) or voice (audio file). Adds music (ducked under speech), "
             "subtitles, fades, then inspects the result.",
             obj({"scenes": {"type": "array", "items": {"type": "object"}}, "out": S,
                  "format": {"type": "string", "enum": ["16:9", "9:16", "1:1", "4:5"]}, "music": S,
                  "burn_subtitles": {"type": "boolean"}, "title": S, "voice_lang": S}, ["scenes", "out"]),
             video_compose, WRITE, "media"),
        Tool("video_edit", "Trim, change speed, add a logo, mute, or reframe (16:9 / 9:16 / 1:1 / 4:5) a video.",
             obj({"src": S, "out": S, "start": N, "end": N, "speed": N, "watermark": S, "mute": {"type": "boolean"},
                  "reframe": S}, ["src", "out"]), video_edit, WRITE, "media"),
        Tool("export_social", "Export a video for YouTube, Reels/Shorts/TikTok and square feeds.",
             obj({"src": S, "formats": {"type": "array", "items": S}}, ["src"]), export_social, WRITE, "media"),
        Tool("media_inspect", "Technical check of a video/audio file: duration, resolution, audio, sync, black or "
             "frozen frames, silence, subtitle timing.", obj({"path": S, "expect_duration": N,
                                                             "expect_audio": {"type": "boolean"}}, ["path"]),
             media_inspect, SAFE, "media"),
        Tool("speak", "Text to speech (Turkish and many languages).", obj({"text": S, "out": S, "lang": S, "voice": S},
                                                                          ["text", "out"]), speak, WRITE, "media"),
        Tool("transcribe", "Speech to text, optionally writing an .srt subtitle file.",
             obj({"path": S, "lang": S, "srt": S}, ["path"]), transcribe, SAFE, "media"),
        Tool("music", "Compose music in code: tracks with notes like [[\"C4\", 1], [[\"C4\",\"E4\",\"G4\"], 2], "
             "[\"R\", 0.5]] (lengths in beats), General MIDI program per track. Writes .mid and audio.",
             obj({"tracks": {"type": "array", "items": {"type": "object"}}, "bpm": INT, "out": S, "soundfont": S},
                 ["tracks", "bpm", "out"]), music, WRITE, "media"),
        Tool("sound_effect", "UI sound effects: click, pop, whoosh, success, error, notification.",
             obj({"kind": S, "out": S, "seconds": N}, ["kind", "out"]), sound_effect, WRITE, "media"),
        Tool("image_generate", "Generate an image from a description with an image model (uses your API key). "
             "Never depict real people without consent.", obj({"prompt": S, "out": S, "size": S,
                                                               "commercial": {"type": "boolean"}}, ["prompt", "out"]),
             image_generate, EXTERNAL, "media"),
        Tool("image_edit", "Edit an image: resize, crop, fit, rotate, grayscale, text, remove_background, upscale.",
             obj({"src": S, "out": S, "ops": {"type": "array", "items": {"type": "object"}}}, ["src", "out", "ops"]),
             image_edit, WRITE, "media"),
        Tool("image_understand", "Understand an image or video (for models that cannot see): description via a vision "
             "model you have, plus size, colours and text.", obj({"path": S, "question": S}, ["path"]),
             image_understand, SAFE, "media"),
        Tool("app_icons", "From one square image make every app icon size: Android, iOS, web/PWA, Windows, macOS.",
             obj({"src": S, "out_dir": S, "name": S}, ["src"]), app_icons, WRITE, "media"),
        Tool("model_3d", "3D models: openscad (printable parts, code), blender (script), box (simple STL), threejs "
             "(web scene).", obj({"kind": S, "out": S, "code": S, "size": {"type": "array", "items": N}},
                                 ["kind", "out"]), model_3d, WRITE, "media"),
        Tool("media_licenses", "Check whether open media models allow your (commercial) use.",
             obj({"models": {"type": "array", "items": S}, "commercial": {"type": "boolean"}}, ["models"]),
             media_licenses, SAFE, "media"),
    ]
    for t in tools:
        reg.register(t)


@register_gate
def install_gate(session) -> None:
    def gate(engine) -> GateResult:
        problems = []
        for f in engine.changed_files():
            p = engine.root / f
            if p.suffix.lower() in VIDEO_EXT and ".yw" not in p.parts:
                try:
                    srt = p.with_suffix(".srt")
                    res = video.inspect(p, srt=srt if srt.exists() else None)
                    if not res.ok:
                        problems.append(f"{f}: " + "; ".join(res.problems))
                except ToolError as e:
                    problems.append(f"{f}: {e.message}")
        return GateResult("media files pass inspection", not problems, "\n".join(problems))
    session.engine.extra_gates.append(gate)
