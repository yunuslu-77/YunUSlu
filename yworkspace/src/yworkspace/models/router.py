"""Smart model router (filled in at stage 11)."""

from __future__ import annotations


class Router:
    def __init__(self, cfg, provider_for, profile_for):
        self.cfg = cfg
        self._provider_for = provider_for
        self._profile_for = profile_for

    def provider_for(self, role: str):
        return self._provider_for(role)

    def profile_for(self, role: str):
        return self._profile_for(role)
