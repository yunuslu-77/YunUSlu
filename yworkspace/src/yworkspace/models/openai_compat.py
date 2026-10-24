"""OpenAI-compatible chat completions: DeepSeek, OpenAI, Qwen, Mistral, Grok, Kimi, Ollama, OpenRouter, Groq..."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx

from .base import ChatResponse, Message, ProviderError, ToolCall, Usage, parse_arguments

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}


def post_json(client: httpx.Client, url: str, headers: dict, body: dict, retries: int = 3) -> dict:
    delay = 2.0
    for attempt in range(retries + 1):
        try:
            r = client.post(url, headers=headers, json=body)
        except httpx.HTTPError as e:
            if attempt == retries:
                raise ProviderError(f"Network error: {e}", retryable=True) from e
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code in RETRY_STATUS and attempt < retries:
            wait = r.headers.get("retry-after")
            time.sleep(float(wait) if wait and wait.replace(".", "").isdigit() else delay)
            delay *= 2
            continue
        if r.status_code >= 400:
            raise ProviderError(f"HTTP {r.status_code}: {r.text[:1000]}", r.status_code in RETRY_STATUS, r.status_code)
        return r.json()
    raise ProviderError("unreachable")


@dataclass
class OpenAICompatProvider:
    model: str
    base_url: str
    api_key: str | None = None
    name: str = "openai-compatible"
    supports_tools: bool = True
    supports_vision: bool = False
    timeout: float = 600.0
    extra_body: dict = field(default_factory=dict)
    transport: httpx.BaseTransport | None = None  # for tests

    def __post_init__(self) -> None:
        self._client = httpx.Client(timeout=self.timeout, transport=self.transport)

    def _convert(self, messages: list[Message]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            if m.role == "tool":
                out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content or "(empty)"})
                if m.images and self.supports_vision:
                    out.append({"role": "user", "content": [
                        {"type": "text", "text": f"Image returned by {m.name}:"},
                        *({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}} for b in m.images)]})
                continue
            if m.role == "assistant":
                msg: dict = {"role": "assistant", "content": m.content or None}
                if m.tool_calls:
                    msg["tool_calls"] = [{"id": c.id, "type": "function", "function": {
                        "name": c.name, "arguments": c.raw_arguments or json.dumps(c.arguments, ensure_ascii=False)}}
                        for c in m.tool_calls]
                out.append(msg)
                continue
            if m.images and self.supports_vision:
                out.append({"role": m.role, "content": [{"type": "text", "text": m.content}] + [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}} for b in m.images]})
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    def chat(self, messages: list[Message], tools: list | None = None, max_tokens: int = 16000) -> ChatResponse:
        body: dict = {"model": self.model, "messages": self._convert(messages), "max_tokens": max_tokens,
                      **self.extra_body}
        if tools and self.supports_tools:
            body["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = post_json(self._client, self.base_url.rstrip("/") + "/chat/completions", headers, body)
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected response: {str(data)[:500]}") from e
        msg = choice.get("message", {})
        calls = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function", {})
            args, raw = parse_arguments(fn.get("arguments"))
            calls.append(ToolCall(fn.get("name", ""), args, c.get("id") or ToolCall("", {}).id, raw))
        u = data.get("usage") or {}
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or u.get("prompt_cache_hit_tokens") or 0
        finish = choice.get("finish_reason")
        stop = {"tool_calls": "tool_calls", "length": "max_tokens", "content_filter": "refusal"}.get(finish, "end")
        if calls:
            stop = "tool_calls"
        return ChatResponse(Message("assistant", msg.get("content") or "", calls),
                            Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0), cached),
                            stop, data.get("model", self.model))
