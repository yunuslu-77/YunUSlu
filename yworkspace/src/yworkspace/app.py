"""Assembles a working yWorkspace session: workspace + sandbox + tools + models + engine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config, get_secret
from .core.workspace import Workspace
from .engine.engine import Approver, Engine
from .engine.loop import LoopEvent
from .models.profiles import ModelProfile, create_provider, get_profile
from .tools.builtin import build_registry
from .tools.registry import ToolRegistry


@dataclass
class Session:
    config: Config
    workspace: Workspace
    sandbox: object
    registry: ToolRegistry
    engine: Engine | None = None

    close_hooks: list = field(default_factory=list)

    def close(self) -> None:
        for hook in self.close_hooks:
            try:
                hook()
            except Exception:
                pass
        stop = getattr(self.sandbox, "stop", None)
        if stop and self.config.sandbox == "local":
            stop()


def make_sandbox(root: Path, cfg: Config):
    if cfg.sandbox == "local":
        from .sandbox import LocalSandbox
        return LocalSandbox(root)
    from .sandbox import DockerSandbox
    return DockerSandbox(root, image=cfg.sandbox_image)


def profile(cfg: Config, preset: str) -> ModelProfile:
    return get_profile(preset, **cfg.model_overrides.get(preset, {}))


def provider_factory(cfg: Config) -> tuple[Callable[[str], object], Callable[[str], ModelProfile]]:
    cache: dict[str, object] = {}

    def preset_for(role: str) -> str:
        return cfg.role_models.get(role) or cfg.model

    def profile_for(role: str) -> ModelProfile:
        return profile(cfg, preset_for(role))

    def provider_for(role: str):
        preset = preset_for(role)
        if preset not in cache:
            prof = profile(cfg, preset)
            key = get_secret(prof.key_env) if prof.key_env else None
            cache[preset] = create_provider(prof, api_key=key)
        return cache[preset]

    return provider_for, profile_for


def build_session(project: str | Path, cfg: Config | None = None, approver: Approver | None = None,
                  on_event: Callable[[LoopEvent], None] | None = None, with_engine: bool = True,
                  extensions: bool = True) -> Session:
    cfg = cfg or Config.load()
    ws = Workspace(Path(project))
    sb = make_sandbox(ws.root, cfg)
    reg = build_registry(ws, sb)
    sess = Session(cfg, ws, sb, reg)
    if extensions:
        from .extensions import install_all
        install_all(sess)
    if with_engine:
        provider_for, profile_for = provider_factory(cfg)
        if cfg.router:
            from .models.router import Router
            router = Router(cfg, provider_for, profile_for)
            provider_for, profile_for = router.provider_for, router.profile_for
        from .skills import skills_for
        sess.engine = Engine(ws, reg, provider_for, profile_for, sandbox=sb, approver=approver or Approver(),
                             autonomy=cfg.autonomy, quality=cfg.quality, lang=cfg.lang, budget_usd=cfg.budget_usd,
                             max_minutes=cfg.max_minutes, on_event=on_event,
                             skills_for=lambda role, text: skills_for(role, text, cfg.lang, ws.root))
        if extensions:
            from .extensions import install_gates
            install_gates(sess)
    return sess
