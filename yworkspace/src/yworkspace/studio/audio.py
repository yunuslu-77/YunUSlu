"""Audio: speech (TTS), transcription (STT), music composed in code, sound effects.

Engines are picked in order: local open-source engines if installed (Piper, espeak-ng, faster-whisper,
FluidSynth), otherwise the user's API keys (OpenAI, ElevenLabs). Voice cloning is never offered without
explicit consent and a sample of the user's own (or a consenting person's) voice.
"""

from __future__ import annotations

import math
import shutil
import struct
import subprocess
from pathlib import Path

from ..config import get_secret
from ..core.errors import ToolError
from .video import ff, write_srt

NOTE_INDEX = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5, "f#": 6, "gb": 6, "g": 7,
              "g#": 8, "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11}


# ------------------------------------------------------------------------------ speech
def speak(text: str, out: Path, lang: str = "tr", voice: str | None = None) -> tuple[Path, str]:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".wav")
    if shutil.which("piper") and voice:
        subprocess.run(["piper", "--model", voice, "--output_file", str(wav)], input=text.encode(), check=True,
                       capture_output=True)
        engine = f"piper ({voice})"
    elif shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-v", lang, "-s", "155", "-w", str(wav), text], check=True, capture_output=True)
        engine = "espeak-ng"
    elif get_secret("OPENAI_API_KEY"):
        import httpx
        r = httpx.post("https://api.openai.com/v1/audio/speech", timeout=120,
                       headers={"Authorization": f"Bearer {get_secret('OPENAI_API_KEY')}"},
                       json={"model": "gpt-4o-mini-tts", "voice": voice or "alloy", "input": text,
                             "response_format": "wav"})
        if r.status_code >= 400:
            raise ToolError("tts_failed", r.text[:500])
        wav.write_bytes(r.content)
        engine = "OpenAI TTS"
    elif get_secret("ELEVENLABS_API_KEY"):
        import httpx
        vid = voice or "21m00Tcm4TlvDq8ikWAM"
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", timeout=120,
                       headers={"xi-api-key": get_secret("ELEVENLABS_API_KEY"), "accept": "audio/mpeg"},
                       json={"text": text, "model_id": "eleven_multilingual_v2"})
        if r.status_code >= 400:
            raise ToolError("tts_failed", r.text[:500])
        mp3 = out.with_suffix(".mp3")
        mp3.write_bytes(r.content)
        if out.suffix != ".mp3":
            ff(["-i", str(mp3), str(out)])
        return out, "ElevenLabs"
    else:
        raise ToolError("no_tts", "No speech engine is available.",
                        "Install Piper (best quality, offline, has Turkish voices) or espeak-ng, or add an "
                        "OPENAI_API_KEY / ELEVENLABS_API_KEY.")
    if out.suffix != ".wav":
        ff(["-i", str(wav), str(out)])
        wav.unlink(missing_ok=True)
    return out, engine


def transcribe(path: Path, lang: str | None = None, srt_out: Path | None = None) -> tuple[str, list]:
    """Speech → text (+ timed segments). faster-whisper locally, or the OpenAI API."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        WhisperModel = None
    if WhisperModel is not None:
        model = WhisperModel("small", compute_type="int8")
        segments, _info = model.transcribe(str(path), language=lang)
        segs = [(s.start, s.end, s.text.strip()) for s in segments]
    else:
        key = get_secret("OPENAI_API_KEY")
        if not key:
            raise ToolError("no_stt", "No transcription engine is available.",
                            "pip install faster-whisper (offline), or add an OPENAI_API_KEY.")
        import httpx
        with open(path, "rb") as f:
            r = httpx.post("https://api.openai.com/v1/audio/transcriptions", timeout=600,
                           headers={"Authorization": f"Bearer {key}"},
                           files={"file": (Path(path).name, f)},
                           data={"model": "whisper-1", "response_format": "verbose_json",
                                 **({"language": lang} if lang else {})})
        if r.status_code >= 400:
            raise ToolError("stt_failed", r.text[:500])
        segs = [(s["start"], s["end"], s["text"].strip()) for s in r.json().get("segments", [])]
    if srt_out:
        write_srt(segs, srt_out)
    return " ".join(s[2] for s in segs), segs


# ------------------------------------------------------------------------------ music in code
def note_number(name: str) -> int:
    """'C4' → 60, 'F#3' → 54, 'Bb5' → 82. 'R' is a rest (-1)."""
    if name.upper() in ("R", "REST"):
        return -1
    pitch, octave = name[:-1].lower(), int(name[-1])
    return 12 * (octave + 1) + NOTE_INDEX[pitch]


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def write_midi(tracks: list[dict], bpm: int, out: Path) -> Path:
    """tracks: [{"program": 0, "channel": 0, "notes": [["C4", 1], ["E4", 0.5], ["R", 0.5], ...]}] (lengths in beats).
    A note can be a chord: [["C4", "E4", "G4"], 2]."""
    ppq = 480
    chunks = []
    tempo = int(60_000_000 / bpm)
    for ti, tr in enumerate(tracks):
        ch = tr.get("channel", ti) & 0x0F
        ev = bytearray()
        if ti == 0:
            ev += b"\x00\xff\x51\x03" + tempo.to_bytes(3, "big")
        ev += _vlq(0) + bytes([0xC0 | ch, tr.get("program", 0) & 0x7F])
        vel = tr.get("velocity", 90)
        pending = 0
        for item in tr["notes"]:
            names, beats = item[0], float(item[1])
            names = names if isinstance(names, list) else [names]
            ticks = int(beats * ppq)
            nums = [note_number(n) for n in names]
            if all(n < 0 for n in nums):
                pending += ticks
                continue
            for k, n in enumerate(nums):
                ev += _vlq(pending if k == 0 else 0) + bytes([0x90 | ch, n, vel])
            pending = 0
            for k, n in enumerate(nums):
                ev += _vlq(ticks if k == 0 else 0) + bytes([0x80 | ch, n, 0])
        ev += b"\x00\xff\x2f\x00"
        chunks.append(b"MTrk" + len(ev).to_bytes(4, "big") + bytes(ev))
    header = b"MThd" + (6).to_bytes(4, "big") + struct.pack(">HHH", 1, len(chunks), ppq)
    Path(out).write_bytes(header + b"".join(chunks))
    return Path(out)


def render_music(tracks: list[dict], bpm: int, out: Path, soundfont: str | None = None) -> tuple[Path, str]:
    """MIDI → audio. FluidSynth + a SoundFont for real instruments; otherwise a simple synthesized render."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mid = write_midi(tracks, bpm, out.with_suffix(".mid"))
    if shutil.which("fluidsynth") and soundfont:
        wav = out.with_suffix(".wav")
        subprocess.run(["fluidsynth", "-ni", "-F", str(wav), "-r", "48000", soundfont, str(mid)], check=True,
                       capture_output=True)
        if out.suffix != ".wav":
            ff(["-i", str(wav), str(out)])
        return out, "FluidSynth"
    # Simple additive synth via FFmpeg: one tone per note, then mixed.
    beat = 60 / bpm
    parts, filters = [], []
    for tr in tracks:
        t = 0.0
        for item in tr["notes"]:
            names, beats = item[0], float(item[1])
            names = names if isinstance(names, list) else [names]
            dur = beats * beat
            for nm in names:
                n = note_number(nm)
                if n >= 0:
                    f = 440 * 2 ** ((n - 69) / 12)
                    expr = f"0.25*sin(2*PI*{f:.2f}*t)*exp(-2.2*t)+0.08*sin(4*PI*{f:.2f}*t)*exp(-3*t)"
                    parts += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"aevalsrc='{expr}':s=48000:c=stereo"]
                    filters.append(f"[{len(filters)}:a]adelay={int(t * 1000)}|{int(t * 1000)}[n{len(filters)}]")
            t += dur
    if not filters:
        raise ToolError("no_notes", "The music has no notes.")
    mix = "".join(f"[n{i}]" for i in range(len(filters)))
    graph = ";".join(filters) + f";{mix}amix=inputs={len(filters)}:normalize=0,alimiter=limit=0.9[out]"
    ff([*parts, "-filter_complex", graph, "-map", "[out]", str(out)])
    return out, "built-in synthesizer (install FluidSynth + a SoundFont for real instruments)"


def sound_effect(kind: str, out: Path, seconds: float = 0.6) -> Path:
    exprs = {
        "click": "0.6*sin(2*PI*1800*t)*exp(-60*t)",
        "pop": "0.7*sin(2*PI*(400+1200*t)*t)*exp(-14*t)",
        "whoosh": "0.4*(random(0)-0.5)*sin(PI*t/" + f"{seconds}" + ")",
        "success": "0.3*sin(2*PI*660*t)*exp(-4*t)+0.3*sin(2*PI*880*(t-0.12))*gt(t,0.12)*exp(-4*(t-0.12))",
        "error": "0.35*sin(2*PI*220*t)*exp(-3*t)+0.25*sin(2*PI*185*t)*exp(-3*t)",
        "notification": "0.3*sin(2*PI*988*t)*exp(-6*t)+0.3*sin(2*PI*1319*(t-0.09))*gt(t,0.09)*exp(-6*(t-0.09))",
    }
    if kind not in exprs:
        raise ToolError("bad_effect", f"Unknown effect {kind}.", f"Use: {', '.join(exprs)}")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    ff(["-f", "lavfi", "-t", f"{seconds}", "-i", f"aevalsrc='{exprs[kind]}':s=48000:c=stereo", str(out)])
    return Path(out)


def tone_seconds(path: Path) -> float:
    from .video import probe
    return float(probe(path)["format"]["duration"])


def ensure_consent_for_clone(consent: bool, sample_owner: str) -> None:
    if not consent or not sample_owner.strip():
        raise ToolError("consent_required", "Voice cloning needs the voice owner's explicit consent.",
                        "Only clone your own voice, or a person who agreed in writing. Never imitate public figures.")


def db_to_gain(db: float) -> float:
    return math.pow(10, db / 20)
