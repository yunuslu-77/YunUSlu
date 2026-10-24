"""Licenses of popular open media models. Many open weights forbid commercial use: yWorkspace warns when a
commercial project would use one, and suggests an alternative. Verify the current license before shipping -
model licenses change."""

MODELS = {
    # name: (kind, license, commercial_ok, note)
    "FLUX.1-schnell": ("image", "Apache-2.0", True, ""),
    "FLUX.1-dev": ("image", "FLUX.1 [dev] Non-Commercial License", False, "use FLUX.1-schnell or SDXL instead"),
    "Stable Diffusion XL": ("image", "CreativeML OpenRAIL++-M", True, "use restrictions apply"),
    "Stable Diffusion 3.5": ("image", "Stability AI Community License", True, "free under $1M revenue"),
    "Wan 2.1": ("video", "Apache-2.0", True, ""),
    "HunyuanVideo": ("video", "Tencent Hunyuan Community License", True, "territory and scale limits apply"),
    "LTX-Video": ("video", "LTX-Video Open Weights License", True, "check revenue limits"),
    "CogVideoX-5B": ("video", "CogVideoX License", True, "registration may be required"),
    "MusicGen": ("music", "CC-BY-NC-4.0 (weights)", False, "compose in code (MIDI) or use a commercial API"),
    "Stable Audio Open": ("music", "Stability AI Community License", True, "free under $1M revenue"),
    "Piper voices": ("speech", "varies per voice (many MIT/CC-BY)", True, "check each voice's license"),
    "XTTS-v2": ("speech", "Coqui Public Model License", False, "non-commercial only"),
    "Kokoro-82M": ("speech", "Apache-2.0", True, ""),
    "Whisper / faster-whisper": ("transcription", "MIT", True, ""),
    "Qwen2.5-VL": ("vision", "Apache-2.0 (most sizes)", True, "the 72B model has its own license"),
    "LLaVA": ("vision", "Llama 2 Community / research", True, "check the base model's license"),
    "Florence-2": ("vision", "MIT", True, ""),
    "Real-ESRGAN": ("upscale", "BSD-3-Clause", True, ""),
    "rembg (U2-Net)": ("background", "MIT / Apache-2.0", True, ""),
    "TripoSR": ("3d", "MIT", True, ""),
    "Hunyuan3D-2": ("3d", "Tencent Hunyuan Community License", True, "territory and scale limits apply"),
}


def check(models: list[str], commercial: bool) -> list[str]:
    warnings = []
    for m in models:
        info = MODELS.get(m)
        if info is None:
            warnings.append(f"{m}: license unknown to yWorkspace - check it yourself before use.")
        elif commercial and not info[2]:
            warnings.append(f"{m}: {info[1]} does NOT allow commercial use - {info[3]}.")
        elif info[3]:
            warnings.append(f"{m}: {info[1]} ({info[3]}).")
    return warnings
