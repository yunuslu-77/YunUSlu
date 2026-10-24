"""Google Gemini (generateContent REST API)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx

from .base import ChatResponse, Message, ProviderError, ToolCall, Usage
from .openai_compat import post_json

BASE = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class GeminiProvider:
    model: str = "gemini-2.5-flash"
    api_key: str | None = None
    name: str = "gemini"
    supports_tools: bool = True
    supports_vision: bool = True
    base_url: str = BASE
    timeout: float = 600.0
    transport: httpx.BaseTransport | None = None

    def __post_init__(self) -> None:
        self._client = httpx.Client(timeout=self.timeout, transport=self.transport)

    def _convert(self, messages: list[Message]) -> tuple[dict | None, list[dict]]:
        system = [m.content for m in messages if m.role == "system"]
        contents: list[dict] = []

        def push(role: str, parts: list[dict]) -> None:
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": parts})

        for m in messages:
            if m.role == "system":
                continue
            if m.role == "assistant":
                if m.raw_provider == "gemini" and m.raw:
                    push("model", list(m.raw))  # keep thought signatures intact
                    continue
                parts = [{"text": m.content}] if m.content else []
                parts += [{"functionCall": {"name": c.name, "args": c.arguments}} for c in m.tool_calls]
                push("model", parts or [{"text": ""}])
            elif m.role == "tool":
                parts = [{"functionResponse": {"name": m.name or "tool",
                                               "response": {"error" if m.is_error else "result": m.content}}}]
                parts += [{"inlineData": {"mimeType": "image/png", "data": b}} for b in m.images]
                push("user", parts)
            else:
                parts = [{"text": m.content}] + [{"inlineData": {"mimeType": "image/png", "data": b}} for b in m.images]
                push("user", parts)
        sys = {"parts": [{"text": "\n\n".join(system)}]} if system else None
        return sys, contents

    def chat(self, messages: list[Message], tools: list | None = None, max_tokens: int = 16000) -> ChatResponse:
        sys, contents = self._convert(messages)
        body: dict = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens}}
        if sys:
            body["systemInstruction"] = sys
        if tools:
            body["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-goog-api-key"] = self.api_key
        data = post_json(self._client, f"{self.base_url}/models/{self.model}:generateContent", headers, body)
        cands = data.get("candidates") or []
        if not cands:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")
            return ChatResponse(Message("assistant", f"[blocked: {reason}]"), stop_reason="refusal", model=self.model)
        cand = cands[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if "text" in p and not p.get("thought"))
        calls = [ToolCall(p["functionCall"].get("name", ""), p["functionCall"].get("args") or {},
                          "call_" + uuid.uuid4().hex[:12]) for p in parts if "functionCall" in p]
        u = data.get("usageMetadata") or {}
        finish = cand.get("finishReason", "STOP")
        stop = "tool_calls" if calls else {"MAX_TOKENS": "max_tokens", "SAFETY": "refusal",
                                           "RECITATION": "refusal"}.get(finish, "end")
        if finish == "MALFORMED_FUNCTION_CALL" and not calls:
            text += "\n[Your last tool call was malformed. Call the tool again with valid arguments.]"
        msg = Message("assistant", text, calls, raw=parts, raw_provider="gemini")
        if not parts and finish not in ("STOP", "MAX_TOKENS"):
            raise ProviderError(f"Gemini returned no content (finishReason={finish}).", retryable=True)
        return ChatResponse(msg, Usage(u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0),
                                       u.get("cachedContentTokenCount", 0)), stop, self.model)
