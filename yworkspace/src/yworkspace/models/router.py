"""Smart model router: each role/task goes to the most suitable model the user has.

Rules, in order:
  1. User rules win: role_models from the config, and local_only (code never leaves the computer).
  2. Role difficulty: planning, review and debugging want a strong model; routine building a standard one;
     using the screen wants a vision-capable model.
  3. Escalation: a task that already failed (attempts ≥ 2) or is marked hard moves up to a strong model.
  4. Cheapest suitable model wins among equals (unknown prices count as expensive).
  5. Second opinions: in maximum quality, consecutive reviews rotate through different strong models.
  6. Fallback: if a model's API fails, the same request goes to the next suitable model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import get_secret
from .base import ChatResponse, Message, ProviderError
from .profiles import PRESETS, ModelProfile, create_provider, get_profile

TIER_RANK = {"small": 0, "standard": 1, "strong": 2}
ROLE_TIER = {"analyst": "strong", "architect": "strong", "reviewer": "strong", "debugger": "strong",
             "merger": "standard", "developer": "standard", "tester": "standard", "director": "standard",
             "test_user": "standard"}
NEEDS_VISION = {"test_user", "director"}


@dataclass
class Choice:
    preset: str
    reason: str


@dataclass
class FallbackProvider:
    chain: list  # providers, best first
    on_switch: callable = None
    name: str = field(init=False)
    model: str = field(init=False)
    supports_tools: bool = field(init=False)
    supports_vision: bool = field(init=False)

    def __post_init__(self) -> None:
        p = self.chain[0]
        self.name, self.model = p.name, p.model
        self.supports_tools, self.supports_vision = p.supports_tools, p.supports_vision

    accepts_registry = True  # the loop hands us the registry; each provider gets tools in its own format

    def chat(self, messages: list[Message], tools=None, max_tokens: int = 16000) -> ChatResponse:
        from ..engine.loop import format_tools
        last: Exception | None = None
        for i, p in enumerate(self.chain):
            try:
                return p.chat(messages, format_tools(tools, p) if tools is not None else None, max_tokens)
            except ProviderError as e:
                last = e
                if self.on_switch and i + 1 < len(self.chain):
                    self.on_switch(p, self.chain[i + 1], e)
        raise last or ProviderError("no providers")


class Router:
    def __init__(self, cfg, provider_for=None, profile_for=None):
        self.cfg = cfg
        self._cache: dict[str, object] = {}
        self._review_turn = 0
        self.log: list[str] = []

    # ------------------------------------------------------------ inventory
    def available(self) -> list[ModelProfile]:
        """Models the user can actually use: cloud models with a key, plus the configured local model."""
        local_only = getattr(self.cfg, "local_only", False)
        out = []
        for preset in PRESETS:
            prof = get_profile(preset, **self.cfg.model_overrides.get(preset, {}))
            if prof.local or local_only:
                continue
            if prof.key_env and get_secret(prof.key_env):
                out.append(prof)
        default = self._profile(self.cfg.model)
        if default and (default.local or not local_only) and all(p.id != default.id for p in out):
            out.insert(0, default)
        return out

    def _profile(self, preset: str) -> ModelProfile | None:
        try:
            base = preset.split(":")[0] if preset.startswith("ollama:") else preset
            return get_profile(preset, **self.cfg.model_overrides.get(base, {}))
        except KeyError:
            return None

    @staticmethod
    def _cost(p: ModelProfile) -> float:
        if p.price_in is None or p.price_out is None:
            return 1e6
        return p.price_in + 4 * p.price_out

    # ------------------------------------------------------------ choice
    def choose(self, role: str, task=None, quality: str = "balanced") -> Choice:
        if role in self.cfg.role_models:
            return Choice(self.cfg.role_models[role], "user rule")
        if not getattr(self.cfg, "router", True):
            return Choice(self.cfg.model, "router off")
        models = self.available()
        if not models:
            return Choice(self.cfg.model, "no other models available")
        want = ROLE_TIER.get(role, "standard")
        reason = f"{role} → {want}"
        if task is not None and (getattr(task, "hard", False) or getattr(task, "attempts", 0) >= 2):
            want, reason = "strong", f"escalated ({'hard task' if getattr(task, 'hard', False) else 'repeated failures'})"
        if quality == "economy" and want == "strong" and role not in ("debugger",):
            want, reason = "standard", reason + ", economy mode"
        pool = [m for m in models if (role not in NEEDS_VISION or m.vision)] or models
        suitable = [m for m in pool if TIER_RANK[m.tier] >= TIER_RANK[want]]
        if not suitable:
            suitable = sorted(pool, key=lambda m: -TIER_RANK[m.tier])[:1]
            reason += ", best available"
        suitable.sort(key=self._cost)
        if role == "reviewer" and quality == "max" and len(suitable) > 1:
            pick = suitable[self._review_turn % len(suitable)]
            self._review_turn += 1
            return Choice(pick.id, reason + ", second opinion rotation")
        return Choice(suitable[0].id, reason)

    def fallback_chain(self, preset: str, role: str) -> list[str]:
        others = [m.id for m in self.available() if m.id != preset]
        want = ROLE_TIER.get(role, "standard")
        others.sort(key=lambda pid: (TIER_RANK[self._profile(pid).tier] < TIER_RANK[want], self._cost(self._profile(pid))))
        return [preset] + others[:2]

    # ------------------------------------------------------------ providers
    def provider(self, preset: str):
        if preset not in self._cache:
            prof = self._profile(preset)
            key = get_secret(prof.key_env) if prof and prof.key_env else None
            self._cache[preset] = create_provider(prof, api_key=key)
        return self._cache[preset]

    def provider_for_choice(self, choice: Choice, role: str):
        chain = [self.provider(p) for p in self.fallback_chain(choice.preset, role)]
        if len(chain) == 1:
            return chain[0]
        return FallbackProvider(chain, lambda a, b, e: self.log.append(f"{a.model} failed ({e}); switched to {b.model}"))

    # Backwards-compatible API used by app.build_session
    def provider_for(self, role: str):
        return self.provider_for_choice(self.choose(role, quality=self.cfg.quality), role)

    def profile_for(self, role: str) -> ModelProfile | None:
        return self._profile(self.choose(role, quality=self.cfg.quality).preset)


def savings(cost_by_model: dict[str, dict], reference: ModelProfile | None) -> float:
    """How much cheaper the run was than sending every token to the reference (strongest) model."""
    if reference is None or reference.price_in is None:
        return 0.0
    total_ref = sum((v.get("in", 0) * reference.price_in + v.get("out", 0) * reference.price_out) / 1e6
                    for v in cost_by_model.values())
    actual = sum(v.get("usd", 0.0) for v in cost_by_model.values())
    return max(0.0, total_ref - actual)
