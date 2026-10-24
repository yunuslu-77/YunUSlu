"""Anthropic Claude via the official Python SDK (Messages API)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from .base import ChatResponse, Message, ProviderError, ToolCall, Usage

DEFAULT_MODEL = "claude-opus-5-5"
# Models that accept the server-side refusal fallback in its "default" form.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


@dataclass
class ClaudeProvider:
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    effort: str | None = "high"  # low | medium | high | xhigh | max (Opus 5.5 defaults to medium if unset)
    name: str = "claude"
    supports_tools: bool = True
    supports_vision: bool = True
    client: Any = None  # injectable for tests

    def __post_init__(self) -> None:
        if self.client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ProviderError("The 'anthropic' package is required: pip install anthropic") from e
            self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else anthropic.Anthropic()

    @staticmethod
    def _image(b64: str) -> dict:
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}

    def _convert(self, messages: list[Message]) -> tuple[str, list[dict]]:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        out: list[dict] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "assistant":
                if m.raw_provider == "claude" and m.raw is not None:
                    content = m.raw  # thinking blocks must go back unchanged
                else:
                    content = ([{"type": "text", "text": m.content}] if m.content else []) + [
                        {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in m.tool_calls]
                out.append({"role": "assistant", "content": content or [{"type": "text", "text": "(no text)"}]})
            elif m.role == "tool":
                block = {"type": "tool_result", "tool_use_id": m.tool_call_id,
                         "content": [{"type": "text", "text": m.content or "(empty)"}]
                         + [self._image(b) for b in m.images]}
                if m.is_error:
                    block["is_error"] = True
                # All results of one assistant turn must be in a single user message.
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) and \
                        all(b.get("type") == "tool_result" for b in out[-1]["content"]):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            else:
                content = [self._image(b) for b in m.images] + [{"type": "text", "text": m.content}]
                out.append({"role": "user", "content": content})
        return system, out

    def chat(self, messages: list[Message], tools: list | None = None, max_tokens: int = 16000) -> ChatResponse:
        import anthropic

        system, msgs = self._convert(messages)
        kwargs: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens, "messages": msgs}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        try:
            if self.model in FALLBACK_MODELS:
                resp = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                        fallbacks="default", **kwargs)
            else:
                resp = self.client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            raise ProviderError(f"Rate limited: {e}", retryable=True, status=429) from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Claude API error {e.status_code}: {e.message}", e.status_code >= 500,
                                e.status_code) from e
        except anthropic.APIConnectionError as e:
            raise ProviderError(f"Network error: {e}", retryable=True) from e

        text_parts, calls, raw = [], [], []
        for block in resp.content:
            raw.append(block.model_dump(exclude_none=True) if hasattr(block, "model_dump") else block)
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(block.name, dict(block.input or {}), block.id))
        stop = {"tool_use": "tool_calls", "max_tokens": "max_tokens", "refusal": "refusal"}.get(resp.stop_reason, "end")
        u = resp.usage
        usage = Usage(getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0,
                      getattr(u, "cache_read_input_tokens", 0) or 0)
        return ChatResponse(Message("assistant", "".join(text_parts), calls, raw=raw, raw_provider="claude"),
                            usage, stop, getattr(resp, "model", self.model))


def encode_png(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode()
