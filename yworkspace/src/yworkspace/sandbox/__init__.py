"""Komutların çalıştığı yalıtılmış ortam / isolated command sandbox."""

from .docker import DockerSandbox, RunResult, docker_available
from .local import LocalSandbox

__all__ = ["DockerSandbox", "LocalSandbox", "RunResult", "docker_available"]
