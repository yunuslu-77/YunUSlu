"""A scripted fake model for tests, demos and offline benchmarks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .base import ChatResponse, Message, ToolCall, Usage

Step = Message | Callable[[list[Message]], Message]


@dataclass
class ScriptedProvider:
    script: list[Step]
    name: str = "scripted"
    model: str = "scripted"
    supports_tools: bool = True
    supports_vision: bool = False
    seen: list[list[Message]] = field(default_factory=list)

    def chat(self, messages, tools=None, max_tokens=16000) -> ChatResponse:
        self.seen.append(list(messages))
        if not self.script:
            return ChatResponse(Message("assistant", "(script finished)"), Usage(1, 1), "end", self.model)
        step = self.script.pop(0)
        msg = step(messages) if callable(step) else step
        return ChatResponse(msg, Usage(10, 5), "tool_calls" if msg.tool_calls else "end", self.model)


def say(text: str, *calls: tuple[str, dict]) -> Message:
    return Message("assistant", text, [ToolCall(n, a) for n, a in calls])
