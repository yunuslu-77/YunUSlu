"""The basic agent loop: send messages, run tool calls, feed results back. Works in native and text mode."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..models.base import ChatResponse, Message, Provider, ProviderError, Usage
from ..protocol import text_protocol
from ..tools.registry import ToolRegistry, ToolResult

NATIVE, TEXT = "native", "text"


def format_tools(registry: ToolRegistry, provider) -> list:
    """Tool definitions in the format of this provider's API."""
    name = getattr(provider, "name", "")
    if name == "claude":
        return registry.to_anthropic()
    if name == "gemini":
        return registry.to_gemini()
    return registry.to_openai()


@dataclass
class LoopEvent:
    kind: str  # assistant | tool_call | tool_result | info | error | done
    text: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class LoopResult:
    messages: list[Message]
    usage: Usage
    steps: int
    stop: str  # finished | max_steps | budget | error | stopped
    final_text: str = ""


@dataclass
class AgentLoop:
    provider: Provider
    registry: ToolRegistry
    mode: str = NATIVE
    max_steps: int = 50
    max_tokens: int = 16000
    on_event: Callable[[LoopEvent], None] | None = None
    # Called when the model ends its turn without tool calls. Return a message to continue, or None to stop.
    on_idle: Callable[[list[Message]], str | None] | None = None
    should_stop: Callable[[], bool] | None = None
    retries: int = 3
    usage: Usage = field(default_factory=Usage)

    def __post_init__(self) -> None:
        if self.mode == NATIVE and not getattr(self.provider, "supports_tools", True):
            self.mode = TEXT

    def _emit(self, kind: str, text: str = "", **data) -> None:
        if self.on_event:
            self.on_event(LoopEvent(kind, text, data))

    def system_suffix(self) -> str:
        return text_protocol.instructions(self.registry) if self.mode == TEXT else ""

    def _chat(self, messages: list[Message]) -> ChatResponse:
        tools = None
        if self.mode == NATIVE:
            tools = self.registry if getattr(self.provider, "accepts_registry", False) else \
                format_tools(self.registry, self.provider)
        delay = 3.0
        for attempt in range(self.retries + 1):
            try:
                return self.provider.chat(messages, tools, self.max_tokens)
            except ProviderError as e:
                if not e.retryable or attempt == self.retries:
                    raise
                self._emit("info", f"Model error, retrying in {delay:.0f}s: {e}")
                time.sleep(delay)
                delay *= 2
        raise ProviderError("unreachable")

    def run(self, messages: list[Message]) -> LoopResult:
        if self.mode == TEXT and messages and messages[0].role == "system" and "yWorkspace text protocol" not in messages[0].content:
            messages[0].content += "\n\n" + self.system_suffix()
        steps = 0
        final = ""
        while steps < self.max_steps:
            if self.should_stop and self.should_stop():
                return LoopResult(messages, self.usage, steps, "stopped", final)
            steps += 1
            try:
                resp = self._chat(messages)
            except ProviderError as e:
                self._emit("error", str(e))
                return LoopResult(messages, self.usage, steps, "error", str(e))
            self.usage.add(resp.usage)
            msg = resp.message
            messages.append(msg)
            calls = msg.tool_calls
            parse_errors: list[str] = []
            if self.mode == TEXT:
                parsed = text_protocol.parse(msg.content, self.registry)
                calls, parse_errors = parsed.calls, parsed.errors
                if parsed.text:
                    self._emit("assistant", parsed.text)
            elif msg.content:
                self._emit("assistant", msg.content)
            if msg.content:
                final = msg.content
            if resp.stop_reason == "max_tokens" and not calls:
                cont = "Your reply was cut off by the length limit. Continue exactly where you stopped."
                messages.append(Message("user", cont))
                continue
            if not calls and not parse_errors:
                nudge = self.on_idle(messages) if self.on_idle else None
                if nudge:
                    self._emit("info", nudge)
                    messages.append(Message("user", nudge))
                    continue
                self._emit("done", final)
                return LoopResult(messages, self.usage, steps, "finished", final)
            results: list[ToolResult] = []
            for call in calls:
                if call.raw_arguments is not None and not call.arguments:
                    r = ToolResult(call.name, "ERROR [bad_json]: Your tool arguments were not valid JSON. "
                                              "Send the call again with a valid JSON object.", True)
                else:
                    self._emit("tool_call", call.name, args=call.arguments)
                    r = self.registry.call(call.name, call.arguments)
                self._emit("tool_result", r.text, name=call.name, is_error=r.is_error)
                results.append(r)
                if self.mode == NATIVE:
                    messages.append(Message("tool", r.text, tool_call_id=call.id, name=call.name,
                                            is_error=r.is_error, images=r.images))
            if self.mode == TEXT:
                images = [img for r in results for img in r.images]
                messages.append(Message("user", text_protocol.format_results(results, parse_errors), images=images))
        return LoopResult(messages, self.usage, steps, "max_steps", final)
