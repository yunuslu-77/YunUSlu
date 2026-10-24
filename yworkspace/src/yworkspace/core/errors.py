"""Errors returned to the model. Messages are written so a weak model can act on them."""

from __future__ import annotations


class ToolError(Exception):
    """An error the model can see and recover from."""

    def __init__(self, code: str, message: str, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint

    def to_text(self) -> str:
        text = f"ERROR [{self.code}]: {self.message}"
        if self.hint:
            text += f"\nHINT: {self.hint}"
        return text
