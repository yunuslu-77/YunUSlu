"""Known models: how to reach them and how the engine should treat them.

Prices are USD per million tokens and only filled in where they were confirmed; None means "unknown,
set it in your config". Model lineups change fast: every value here can be overridden in the user config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

from .base import Provider


@dataclass
class ModelProfile:
    id: str  # yWorkspace preset name
    provider: str  # openai | claude | gemini
    model: str  # provider model id
    base_url: str | None = None
    key_env: str | None = None
    context_window: int = 128_000
    tool_calling: str = "native"  # native | text (use the text protocol)
    vision: bool = False
    tier: str = "standard"  # small | standard | strong  (used by the router)
    price_in: float | None = None
    price_out: float | None = None
    local: bool = False
    notes: list[str] = field(default_factory=list)  # weaknesses the engine/skills compensate for


PRESETS: dict[str, ModelProfile] = {p.id: p for p in [
    ModelProfile("deepseek-chat", "openai", "deepseek-chat", "https://api.deepseek.com", "DEEPSEEK_API_KEY",
                 128_000, tier="standard",
                 notes=["Tends to finish early: keep pushing until done gates pass.",
                        "Copy edit 'find' text exactly; it sometimes drops indentation."]),
    ModelProfile("deepseek-reasoner", "openai", "deepseek-reasoner", "https://api.deepseek.com", "DEEPSEEK_API_KEY",
                 128_000, tier="strong", notes=["Good planner and reviewer."]),
    ModelProfile("gemini-flash", "gemini", "gemini-2.5-flash", None, "GEMINI_API_KEY", 1_000_000, vision=True,
                 tier="standard", notes=["Large context: prefer outline + targeted reads anyway."]),
    ModelProfile("gemini-pro", "gemini", "gemini-2.5-pro", None, "GEMINI_API_KEY", 1_000_000, vision=True,
                 tier="strong"),
    ModelProfile("claude-opus", "claude", "claude-opus-5-5", None, "ANTHROPIC_API_KEY", 1_000_000, vision=True,
                 tier="strong", price_in=4.0, price_out=20.0),
    ModelProfile("claude-sonnet", "claude", "claude-sonnet-5-5", None, "ANTHROPIC_API_KEY", 1_000_000, vision=True,
                 tier="strong", price_in=2.0, price_out=10.0),
    ModelProfile("claude-haiku", "claude", "claude-haiku-5-5", None, "ANTHROPIC_API_KEY", 1_000_000, vision=True,
                 tier="standard", price_in=0.10, price_out=0.50),
    ModelProfile("openai", "openai", "gpt-4.1", "https://api.openai.com/v1", "OPENAI_API_KEY", 1_000_000,
                 vision=True, tier="strong"),
    ModelProfile("qwen", "openai", "qwen-plus", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                 "DASHSCOPE_API_KEY", 128_000, tier="standard"),
    ModelProfile("mistral", "openai", "mistral-large-latest", "https://api.mistral.ai/v1", "MISTRAL_API_KEY",
                 128_000, tier="standard"),
    ModelProfile("grok", "openai", "grok-4", "https://api.x.ai/v1", "XAI_API_KEY", 256_000, vision=True,
                 tier="strong"),
    ModelProfile("kimi", "openai", "kimi-k2-0905-preview", "https://api.moonshot.ai/v1", "MOONSHOT_API_KEY",
                 256_000, tier="standard"),
    ModelProfile("openrouter", "openai", "deepseek/deepseek-chat", "https://openrouter.ai/api/v1",
                 "OPENROUTER_API_KEY", 128_000),
    ModelProfile("ollama", "openai", "qwen2.5-coder:7b", "http://localhost:11434/v1", None, 32_000,
                 tier="small", local=True, price_in=0.0, price_out=0.0,
                 notes=["Small local model: keep instructions short, use examples, read files in small pages.",
                        "If native tool calls are unreliable, switch tool_calling to 'text'."]),
    # Janas-LLM (github.com/prabanta-dev/janas): MoE models larger than RAM, experts streamed from an NVMe SSD.
    # Start it with installer/windows/install-janas.ps1 or `janas-server <model.jns>` (OpenAI API on port 8080).
    ModelProfile("janas-qwen3-coder-next", "openai", "qwen3-coder-next", "http://127.0.0.1:8080/v1", None, 16_384,
                 tier="standard", local=True, price_in=0.0, price_out=0.0,
                 notes=["Qwen3-Coder-Next (80B MoE, 3B active) running locally through Janas-LLM.",
                        "The first reply of a session is slower while experts load from the SSD; keep going.",
                        "Context is 16K tokens by default: read files in pages and keep notes in memory_note."]),
]}


def get_profile(name: str, **overrides) -> ModelProfile:
    if name in PRESETS:
        base = PRESETS[name]
    elif ":" in name and name.split(":", 1)[0] in PRESETS:  # e.g. "ollama:llama3.1:8b"
        preset, model = name.split(":", 1)
        base = replace(PRESETS[preset], id=name, model=model)
    else:
        raise KeyError(f"Unknown model preset {name!r}. Known: {', '.join(PRESETS)}")
    clean = {k: v for k, v in overrides.items() if v is not None}
    return replace(base, **clean) if clean else base


def create_provider(profile: ModelProfile, api_key: str | None = None, **kwargs) -> Provider:
    key = api_key or (os.environ.get(profile.key_env) if profile.key_env else None)
    if profile.provider == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider(model=profile.model, api_key=key, **kwargs)
    if profile.provider == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(model=profile.model, api_key=key, **kwargs)
    from .openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(model=profile.model, base_url=profile.base_url or "", api_key=key,
                                name=profile.id, supports_tools=profile.tool_calling == "native",
                                supports_vision=profile.vision, **kwargs)
