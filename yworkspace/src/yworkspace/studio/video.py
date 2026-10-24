"""FFmpeg-based video assembly and editing, plus technical inspection (the media done gates)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import ToolError

FORMATS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def ff(args: list[str], timeout: int = 1800) -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise ToolError("no_ffmpeg", "FFmpeg is not installed.", "Run the setup wizard's media step.")
    r = subprocess.run([exe, "-hide_banner", "-y", *args], capture_output=True, text=True, timeout=timeout,
                       errors="replace")
    if r.returncode != 0:
        raise ToolError("ffmpeg_failed", r.stderr[-2500:])
    return r.stderr


def probe(path: Path) -> dict:
    exe = shutil.which("ffprobe")
    if not exe:
        raise ToolError("no_ffprobe", "ffprobe is not installed.")
    r = subprocess.run([exe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ToolError("bad_media", f"{path.name} cannot be read: {r.stderr[-500:]}")
    return json.loads(r.stdout)


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write_srt(cues: list[tuple[float, float, str]], out: Path) -> Path:
    lines = []
    for i, (a, b, text) in enumerate(cues, 1):
        lines += [str(i), f"{srt_time(a)} --> {srt_time(b)}", text.strip(), ""]
    Path(out).write_text("\n".join(lines), "utf-8")
    return Path(out)


@dataclass
class Scene:
    duration: float
    image: str | None = None  # still image (png/jpg) - code-rendered or generated
    video: str | None = None  # a clip
    subtitle: str = ""
    voice: str | None = None  # path to narration audio for this scene


@dataclass
class ComposeSpec:
    scenes: list[Scene]
    out: Path
    size: tuple[int, int] = (1920, 1080)
    fps: int = 30
    music: str | None = None
    music_volume: float = 0.18
    burn_subtitles: bool = True
    title: str = ""
    fade: float = 0.4
    extra: dict = field(default_factory=dict)


def _scene_clip(sc: Scene, i: int, tmp: Path, w: int, h: int, fps: int, fade: float) -> Path:
    out = tmp / f"scene{i:03d}.mp4"
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
          f"setsar=1,fps={fps},format=yuv420p")
    if fade > 0 and sc.duration > 2 * fade:
        vf += f",fade=t=in:st=0:d={fade},fade=t=out:st={sc.duration - fade:.3f}:d={fade}"
    if sc.image:
        args = ["-loop", "1", "-t", f"{sc.duration}", "-i", sc.image]
    elif sc.video:
        args = ["-t", f"{sc.duration}", "-i", sc.video]
    else:
        args = ["-f", "lavfi", "-t", f"{sc.duration}", "-i", f"color=c=black:s={w}x{h}:r={fps}"]
    audio = ["-i", sc.voice] if sc.voice else ["-f", "lavfi", "-t", f"{sc.duration}", "-i",
                                                 "anullsrc=channel_layout=stereo:sample_rate=48000"]
    ff([*args, *audio, "-filter_complex", f"[0:v]{vf}[v];[1:a]aresample=48000,apad,atrim=0:{sc.duration}[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{sc.duration}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", str(out)])
    return out


def compose(spec: ComposeSpec) -> Path:
    """Scenes → one MP4 with narration, background music, subtitles and AI-generated metadata."""
    if not spec.scenes:
        raise ToolError("no_scenes", "A video needs at least one scene.")
    w, h = spec.size
    tmp = Path(tempfile.mkdtemp(prefix="yw-video-"))
    try:
        clips = [_scene_clip(sc, i, tmp, w, h, spec.fps, spec.fade) for i, sc in enumerate(spec.scenes)]
        listing = tmp / "list.txt"
        listing.write_text("".join(f"file '{c}'\n" for c in clips), "utf-8")
        joined = tmp / "joined.mp4"
        ff(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])
        cues, t = [], 0.0
        for sc in spec.scenes:
            if sc.subtitle:
                cues.append((t + 0.15, t + sc.duration - 0.15, sc.subtitle))
            t += sc.duration
        total = t
        srt = None
        if cues:
            srt = write_srt(cues, Path(spec.out).with_suffix(".srt"))
        inputs = ["-i", str(joined)]
        fc = []
        amap = "0:a"
        if spec.music:
            inputs += ["-stream_loop", "-1", "-i", spec.music]
            # Music ducks under the narration (sidechain), then both are mixed.
            fc.append(f"[0:a]asplit=2[sc][voice];"
                      f"[1:a]volume={spec.music_volume},atrim=0:{total},afade=t=out:st={max(0, total - 1.5)}:d=1.5[m];"
                      f"[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];"
                      f"[duck][voice]amix=inputs=2:duration=first:normalize=0[a]")
            amap = "[a]"
        vmap = "0:v"
        if srt and spec.burn_subtitles:
            style = "FontName=DejaVu Sans,FontSize=" + ("13" if h > w else "18") + \
                    ",PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=40"
            esc = str(srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            fc.append(f"[0:v]subtitles='{esc}':force_style='{style}'[v]")
            vmap = "[v]"
        out = Path(spec.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        args = [*inputs]
        if fc:
            args += ["-filter_complex", ";".join(fc)]
        args += ["-map", vmap, "-map", amap, "-c:v", "libx264" if vmap != "0:v" else "copy", "-preset", "veryfast",
                 "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-t", f"{total}", "-movflags", "+faststart",
                 "-metadata", f"title={spec.title}", "-metadata", "comment=AI-generated with yWorkspace (YunUSlu)",
                 str(out)]
        if vmap == "0:v":
            args = [a for a in args if a not in ("-preset", "veryfast", "-crf", "20")]
        ff(args)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def reframe(src: Path, out: Path, fmt: str, mode: str = "pad") -> Path:
    """Export for YouTube (16:9), Reels/Shorts/TikTok (9:16), square (1:1) or feed (4:5)."""
    if fmt not in FORMATS:
        raise ToolError("bad_format", f"Unknown format {fmt}.", f"Use {', '.join(FORMATS)}")
    w, h = FORMATS[fmt]
    if mode == "crop":
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    else:
        vf = (f"split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:5[bg];"
              f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    ff(["-i", str(src), "-filter_complex", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "copy", str(out)])
    return Path(out)


def edit(src: Path, out: Path, start: float | None = None, end: float | None = None, speed: float = 1.0,
         watermark: str | None = None, mute: bool = False) -> Path:
    args = []
    if start is not None:
        args += ["-ss", str(start)]
    if end is not None:
        args += ["-to", str(end)]
    args += ["-i", str(src)]
    vf, af = [], []
    if speed != 1.0:
        vf.append(f"setpts=PTS/{speed}")
        af.append(f"atempo={speed}" if 0.5 <= speed <= 2 else "atempo=2.0")
    if watermark:
        args += ["-i", watermark]
        filt = ";".join(filter(None, [f"[0:v]{','.join(vf) or 'null'}[base]",
                                      "[1:v]scale=iw*0.12:-1[wm]", "[base][wm]overlay=W-w-32:H-h-32[v]"]))
        args += ["-filter_complex", filt, "-map", "[v]", "-map", "0:a?"]
        if af and not mute:
            args += ["-af", ",".join(af)]
    else:
        if vf:
            args += ["-vf", ",".join(vf)]
        if af and not mute:
            args += ["-af", ",".join(af)]
    if mute:
        args += ["-an"]
    ff([*args, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)])
    return Path(out)


def extract_frames(src: Path, out_dir: Path, count: int = 6) -> list[Path]:
    info = probe(src)
    dur = float(info["format"].get("duration", 0) or 0)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(count):
        t = dur * (i + 0.5) / count
        p = out_dir / f"frame{i:02d}.png"
        ff(["-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", str(p)])
        frames.append(p)
    return frames


@dataclass
class Inspection:
    ok: bool
    facts: dict
    problems: list[str]

    def text(self) -> str:
        head = "PASS" if self.ok else "FAIL"
        return f"{head}: " + ", ".join(f"{k}={v}" for k, v in self.facts.items()) + (
            "\nProblems:\n" + "\n".join(f"- {p}" for p in self.problems) if self.problems else "")


def inspect(path: Path, expect_duration: float | None = None, expect_size: tuple[int, int] | None = None,
            expect_audio: bool | None = None, srt: Path | None = None) -> Inspection:
    """Technical media checks: readable, duration, resolution, audio, black/frozen frames, silence, subtitles."""
    path = Path(path)
    info = probe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"].get("duration", 0) or 0)
    facts = {"duration": f"{dur:.2f}s", "video": f"{v['width']}x{v['height']} {v['codec_name']}" if v else "none",
             "audio": a["codec_name"] if a else "none"}
    problems = []
    if expect_duration and abs(dur - expect_duration) > max(0.6, expect_duration * 0.05):
        problems.append(f"duration {dur:.2f}s, expected about {expect_duration:.2f}s")
    if expect_size and v and (v["width"], v["height"]) != tuple(expect_size):
        problems.append(f"resolution {v['width']}x{v['height']}, expected {expect_size[0]}x{expect_size[1]}")
    if expect_audio and not a:
        problems.append("no audio track")
    if v and a:
        vd, ad = float(v.get("duration", dur) or dur), float(a.get("duration", dur) or dur)
        if abs(vd - ad) > 0.35:
            problems.append(f"audio ({ad:.2f}s) and video ({vd:.2f}s) lengths differ: possible sync problem")
    if v:
        log = ff(["-i", str(path), "-vf", "blackdetect=d=0.6:pix_th=0.06,freezedetect=n=0.003:d=2.5",
                  "-an", "-f", "null", "-"])
        blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)
        # A short fade at the very start/end is normal.
        long_black = [(float(s), float(e)) for s, e in blacks if not (float(s) < 0.8 or float(e) > dur - 0.8)]
        if long_black:
            problems.append(f"black frames at {', '.join(f'{s:.1f}-{e:.1f}s' for s, e in long_black)}")
        freezes = re.findall(r"freeze_start: ([\d.]+)", log)
        facts["frozen_segments"] = len(freezes)
    if a and expect_audio:
        log = ff(["-i", str(path), "-af", "silencedetect=n=-45dB:d=3", "-vn", "-f", "null", "-"])
        sil = re.findall(r"silence_start: ([\d.]+)", log)
        if sil and float(sil[0]) < 0.5 and "silence_end" not in log:
            problems.append("the audio track is silent")
    if srt is not None and Path(srt).exists():
        cues = re.findall(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)", Path(srt).read_text("utf-8"))

        def sec(t):
            hh, mm, rest = t.split(":")
            s, ms = rest.split(",")
            return int(hh) * 3600 + int(mm) * 60 + int(s) + int(ms) / 1000
        late = [b for _a, b in cues if sec(b) > dur + 0.2]
        if late:
            problems.append(f"{len(late)} subtitles end after the video")
        facts["subtitles"] = len(cues)
    return Inspection(not problems, facts, problems)
