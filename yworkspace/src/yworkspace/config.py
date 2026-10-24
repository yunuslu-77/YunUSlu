"""User configuration stored in ~/.yworkspace (or $YW_HOME). API keys are kept in a file only the user can read."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("YW_HOME", Path.home() / ".yworkspace"))


@dataclass
class Config:
    lang: str = "tr"
    model: str = "deepseek-chat"
    sandbox: str = "docker"  # docker | local
    sandbox_image: str = "python:3.12-slim"
    autonomy: str = "milestones"  # steps | milestones | auto
    quality: str = "balanced"  # economy | balanced | max
    budget_usd: float = 5.0
    max_steps: int = 200
    max_minutes: int = 240
    projects_dir: str = str(Path.home() / "yWorkspace")
    role_models: dict[str, str] = field(default_factory=dict)  # role -> model preset
    model_overrides: dict[str, dict] = field(default_factory=dict)
    router: bool = True
    telemetry: bool = False  # never sends anything unless the user turns it on

    @classmethod
    def load(cls) -> Config:
        p = home() / "config.json"
        if not p.exists():
            return cls()
        data = json.loads(p.read_text("utf-8"))
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self) -> None:
        home().mkdir(parents=True, exist_ok=True)
        (home() / "config.json").write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), "utf-8")


def _secrets_path() -> Path:
    return home() / "secrets.json"


def get_secret(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    try:
        import keyring  # optional: OS key store
        value = keyring.get_password("yworkspace", name)
        if value:
            return value
    except Exception:
        pass
    p = _secrets_path()
    if p.exists():
        return json.loads(p.read_text("utf-8")).get(name)
    return None


def set_secret(name: str, value: str) -> str:
    try:
        import keyring
        keyring.set_password("yworkspace", name, value)
        return "os-keyring"
    except Exception:
        pass
    home().mkdir(parents=True, exist_ok=True)
    p = _secrets_path()
    data = json.loads(p.read_text("utf-8")) if p.exists() else {}
    data[name] = value
    p.write_text(json.dumps(data, indent=2), "utf-8")
    if hasattr(os, "chmod"):
        os.chmod(p, 0o600)
    return str(p)
