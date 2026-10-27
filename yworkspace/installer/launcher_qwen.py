"""Entry point of the Qwen edition: yWorkspace with only Qwen3-Coder-Next, running locally through Janas-LLM.

Only the janas-qwen3-coder-next preset is offered and nothing is sent to cloud models. If the Janas server is
not running, it is started from the folder install-janas.ps1 installed it to, and the web interface opens
once the model answers.
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

MODEL = "janas-qwen3-coder-next"
JANAS_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "yWorkspace" / "janas"


def only_qwen() -> None:
    """Drops every other preset; the dict is shared, so the CLI, web interface and router see only Qwen."""
    keep = PRESETS[MODEL]
    PRESETS.clear()
    PRESETS[MODEL] = keep


def qwen_config() -> None:
    cfg = Config.load()
    if (home() / "config.json").exists() and cfg.model == MODEL and cfg.local_only:
        return
    cfg.model = MODEL
    cfg.local_only = True  # never send code to cloud models
    cfg.role_models = {}
    if not (home() / "config.json").exists():
        cfg.sandbox = "local"  # works without Docker; can be changed in the settings
    cfg.save()


def janas_up() -> bool:
    try:
        return httpx.get(PRESETS[MODEL].base_url + "/models", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def ensure_janas() -> None:
    if janas_up():
        return
    start = JANAS_DIR / "start-janas-server.cmd"
    if not start.exists():
        print(f"Janas-LLM bulunamadı / not found: {start}\n"
              "Önce install-janas.ps1'i çalıştırın / run install-janas.ps1 first.")
        return
    print("Qwen3-Coder-Next başlatılıyor (Janas-LLM) / starting the model...")
    flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    subprocess.Popen(["cmd", "/c", str(start)], creationflags=flags, cwd=str(JANAS_DIR))
    for _ in range(180):  # the 48 GB model opens in well under three minutes on an NVMe SSD
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
        qwen_config()
        ensure_janas()
        args = ["web"]
    sys.exit(main(args))
