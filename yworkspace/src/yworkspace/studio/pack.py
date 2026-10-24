"""Media pack: what to install for the Media Studio, chosen by the computer's hardware."""

from __future__ import annotations

import shutil
import sys

TIERS = {
    "none": "Ekran kartı yok: kodla üretim (FFmpeg, grafik, diyagram) + küçük ses ve anlama modelleri + isteğe bağlı API'ler",
    "mid": "Orta ekran kartı: + görsel üretimi ve hafif video modelleri",
    "high": "Güçlü ekran kartı: + yüksek kaliteli video, müzik ve 3B modelleri",
}

PIP_BASE = ["pillow", "matplotlib", "moviepy", "faster-whisper", "piper-tts", "pytesseract"]
PIP_GPU = ["torch", "diffusers", "transformers", "accelerate"]


def tier(info) -> str:
    g = info.best_gpu
    if g.vendor == "nvidia" and g.vram_gb >= 16 or (g.vendor == "apple" and info.ram_gb >= 32):
        return "high"
    if g.vendor in ("nvidia", "amd") and g.vram_gb >= 6 or g.vendor == "apple":
        return "mid"
    return "none"


def pack_actions(ctx) -> list:
    from ..setup.wizard import Action
    t = tier(ctx.info)
    acts = [Action(f"Medya paketi seviyesi / media tier: {TIERS[t]}", None, manual="Bilgi / info")]
    if not shutil.which("ffmpeg"):
        cmd = {"windows": ["winget", "install", "-e", "--id", "Gyan.FFmpeg"],
               "macos": ["brew", "install", "ffmpeg"] if shutil.which("brew") else None}.get(ctx.info.os)
        if ctx.info.os == "linux":
            cmd = {"debian": ["sudo", "apt-get", "install", "-y", "ffmpeg", "tesseract-ocr"],
                   "fedora": ["sudo", "dnf", "install", "-y", "ffmpeg", "tesseract"],
                   "arch": ["sudo", "pacman", "-S", "--noconfirm", "ffmpeg", "tesseract"]}.get(ctx.info.distro)
        acts.append(Action("FFmpeg kur / install FFmpeg", cmd, admin=ctx.info.os == "linux",
                           manual="https://ffmpeg.org/download.html"))
    acts.append(Action("Temel medya kütüphaneleri / base media libraries",
                       [sys.executable, "-m", "pip", "install", *PIP_BASE]))
    if t in ("mid", "high"):
        acts.append(Action("Ekran kartı kütüphaneleri / GPU libraries (birkaç GB / several GB)",
                           [sys.executable, "-m", "pip", "install", *PIP_GPU]))
    return acts
