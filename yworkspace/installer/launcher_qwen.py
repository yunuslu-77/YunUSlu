"""Entry point of the Qwen edition: yWorkspace with only the Qwen coders, running locally through Janas-LLM.

Only the janas-qwen3-coder-* presets are offered and nothing is sent to cloud models. If the Janas server is
not running, it is started with the model the settings name, from the folder install-janas.ps1 installed
Janas to, and the web interface opens once the model answers.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

from yworkspace.cli import main
from yworkspace.config import Config, home
from yworkspace.models.profiles import PRESETS

DEFAULT = "janas-qwen3-coder-30b"
JANAS_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "yWorkspace" / "janas"
# preset -> (model file in JANAS_DIR/models, server options)
MODELS = {
    "janas-qwen3-coder-30b": ("qwen3-coder-30b-a3b-instruct-q4_k_m.jns", ["--cache", "18"]),  # every expert in memory
    "janas-qwen3-coder-next": ("qwen3-coder-next-q4km.jns", ["--reserve", "8"]),  # experts streamed from the SSD
}


def only_qwen() -> None:
    """Drops every other preset; the dict is shared, so the CLI, web interface and router see only Qwen."""
    keep = {k: PRESETS[k] for k in MODELS if k in PRESETS}
    PRESETS.clear()
    PRESETS.update(keep)


def installed(preset: str) -> bool:
    return (JANAS_DIR / "models" / MODELS[preset][0]).exists()


def qwen_config() -> Config:
    cfg = Config.load()
    fresh = not (home() / "config.json").exists()
    if cfg.model not in MODELS or not installed(cfg.model):
        cfg.model = next((p for p in MODELS if installed(p)), DEFAULT)
    cfg.local_only = True  # never send code to cloud models
    cfg.role_models = {k: v for k, v in cfg.role_models.items() if v in MODELS}
    if fresh:
        cfg.sandbox = "local"  # works without Docker; can be changed in the settings
    cfg.save()
    return cfg


def janas_up() -> bool:
    try:
        return httpx.get(PRESETS[DEFAULT].base_url + "/models", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def ensure_janas(preset: str) -> None:
    if janas_up():
        return
    model = JANAS_DIR / "models" / MODELS[preset][0]
    server = JANAS_DIR / "janas" / "janas-server.exe"
    if not (model.exists() and server.exists()):
        print(f"Janas-LLM ya da model bulunamadı / not found: {model}\n"
              "Önce install-janas.ps1'i çalıştırın / run install-janas.ps1 first.")
        return
    print(f"{PRESETS[preset].model} başlatılıyor (Janas-LLM) / starting the model...")
    flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    subprocess.Popen([str(server), str(model), *MODELS[preset][1]], creationflags=flags, cwd=str(JANAS_DIR))
    for _ in range(180):  # an 18-48 GB model opens in well under three minutes on an NVMe SSD
        if janas_up():
            print("Model hazır / model ready.")
            return
        time.sleep(1)
    print("Model henüz yanıt vermiyor; açılan Janas penceresine bakın / the model is not answering yet, "
          "see the Janas window.")


if __name__ == "__main__":
    only_qwen()
    args = sys.argv[1:]
    if not args:
        ensure_janas(qwen_config().model)
        args = ["web"]
    sys.exit(main(args))
