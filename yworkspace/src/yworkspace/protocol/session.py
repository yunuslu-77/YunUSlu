"""A text-protocol session: shared by manual mode, the desktop bridge and the browser extension.

The AI lives somewhere we can only exchange text with (a chat window). This class produces the opening
message, executes the blocks found in each reply, and produces the text to send back.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..tools.registry import ToolRegistry
from . import text_protocol


@dataclass
class TurnResult:
    reply_to_ai: str  # what to paste back into the chat
    calls: int
    errors: int
    done: bool  # the AI wrote no tool blocks: its turn is over
    prose: str = ""


@dataclass
class TextSession:
    registry: ToolRegistry
    role_prompt: str = ""
    goal: str = ""
    lang: str = "tr"
    max_message_chars: int = 30_000  # many chat UIs reject very long messages
    turns: int = 0
    idle_nudge: callable = None  # (session) -> str | None, e.g. the engine's done-gate checker
    history: list[tuple[str, str]] = field(default_factory=list)

    def opening(self) -> str:
        parts = []
        if self.role_prompt:
            parts.append(self.role_prompt)
        parts.append(text_protocol.instructions(self.registry, self.lang))
        if self.goal:
            parts.append(f"## Task\n{self.goal}\n\nStart now. Begin by looking at the project with list.")
        return "\n\n".join(parts)

    def handle(self, ai_reply: str) -> TurnResult:
        self.turns += 1
        parsed = text_protocol.parse(ai_reply, self.registry)
        results = [self.registry.call(c.name, c.arguments) for c in parsed.calls]
        if not parsed.calls and not parsed.errors:
            nudge = self.idle_nudge(self) if self.idle_nudge else None
            self.history.append((ai_reply, nudge or ""))
            return TurnResult(nudge or "", 0, 0, nudge is None, parsed.text)
        text = text_protocol.format_results(results, parsed.errors)
        text += "\n\nContinue. Write the next tool blocks, or a short final summary if everything is done and verified."
        self.history.append((ai_reply, text))
        return TurnResult(text, len(parsed.calls), sum(r.is_error for r in results) + len(parsed.errors),
                          False, parsed.text)

    def split(self, text: str) -> list[str]:
        """Split a long message into numbered parts that fit the chat's limit."""
        limit = self.max_message_chars
        if len(text) <= limit:
            return [text]
        chunks, cur = [], ""
        for line in text.split("\n"):
            while len(line) > limit - 200:
                chunks.append(cur + line[: limit - 200 - len(cur)])
                line = line[limit - 200 - len(cur):]
                cur = ""
            if len(cur) + len(line) + 1 > limit - 200:
                chunks.append(cur)
                cur = ""
            cur += line + "\n"
        if cur:
            chunks.append(cur)
        n = len(chunks)
        out = []
        for i, c in enumerate(chunks, 1):
            if i < n:
                out.append(f"[Part {i}/{n}. Do not answer yet; reply only with 'OK' until the last part.]\n{c}")
            else:
                out.append(f"[Part {i}/{n}. This is the last part; now answer.]\n{c}")
        return out
