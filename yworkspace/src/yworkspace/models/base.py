"""Provider-neutral conversation types and the provider interface."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    id: str = field(default_factory=lambda: "call_" + uuid.uuid4().hex[:12])
    raw_arguments: str | None = None  # unparsed text if the model sent broken JSON


@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # for role == tool
    name: str | None = None  # tool name for role == tool
    is_error: bool = False
    images: list[str] = field(default_factory=list)  # base64 PNG
    # Provider-native assistant content kept verbatim (e.g. Claude thinking blocks must be sent back unchanged).
    raw: Any = None
    raw_provider: str | None = None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_input_tokens += other.cached_input_tokens


@dataclass
class ChatResponse:
    message: Message
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = "end"  # end | tool_calls | max_tokens | refusal | error
    model: str = ""


class ProviderError(Exception):
    def __init__(self, message: str, retryable: bool = False, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


class Provider(Protocol):
    name: str
    model: str
    supports_tools: bool
    supports_vision: bool

    def chat(self, messages: list[Message], tools: list | None = None, max_tokens: int = 16000) -> ChatResponse: ...


def parse_arguments(text: str | dict | None) -> tuple[dict[str, Any], str | None]:
    """Parse tool-call arguments, repairing the most common JSON mistakes of weak models."""
    if isinstance(text, dict):
        return text, None
    if not text or not str(text).strip():
        return {}, None
    raw = str(text).strip()
    candidates = [raw]
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    candidates.append(fenced)
    candidates.append(re.sub(r",\s*([}\]])", r"\1", fenced))  # trailing commas
    if fenced.count("{") > fenced.count("}"):
        candidates.append(fenced + "}" * (fenced.count("{") - fenced.count("}")))
    for c in candidates:
        try:
            value = json.loads(c)
            if isinstance(value, dict):
                return value, None
        except json.JSONDecodeError:
            continue
    return {}, raw
