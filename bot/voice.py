"""Sesli cevap: Gemini TTS (yedek: gTTS) → Telegram sesli mesajı (OGG/Opus)."""
from __future__ import annotations

import asyncio
import io
import logging
import re

log = logging.getLogger(__name__)


async def _ffmpeg(args: list[str], data: bytes) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-loglevel", "error", *args, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate(data)
    if proc.returncode != 0:
        raise RuntimeError(err.decode()[:300])
    return out


async def pcm_to_ogg(pcm: bytes, rate: int = 24000) -> bytes:
    return await _ffmpeg(["-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                          "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1"], pcm)


async def mp3_to_ogg(mp3: bytes) -> bytes:
    return await _ffmpeg(["-f", "mp3", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1"], mp3)


def clean_for_speech(text: str) -> str:
    text = re.sub(r"https?://\S+", "bağlantı", text)
    text = re.sub(r"[*_`#>|]", "", text)
    return text[:1500]


async def synthesize(llm, text: str) -> bytes | None:
    text = clean_for_speech(text)
    if not text.strip():
        return None
    try:
        return await pcm_to_ogg(await llm.tts(text))
    except Exception as e:
        log.warning("Gemini TTS başarısız, gTTS deneniyor: %s", e)
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        await asyncio.to_thread(lambda: gTTS(text, lang="tr").write_to_fp(buf))
        return await mp3_to_ogg(buf.getvalue())
    except Exception as e:
        log.warning("gTTS de başarısız: %s", e)
        return None
