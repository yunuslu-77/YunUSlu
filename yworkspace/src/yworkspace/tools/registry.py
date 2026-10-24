"""Single source of truth for tools, converted into every model's tool format."""

from __future__ import annotations

import copy
import json
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..core.errors import ToolError

# Risk levels decide which calls need user approval in each autonomy mode.
SAFE, WRITE, EXEC, EXTERNAL, DESTRUCTIVE = "safe", "write", "exec", "external", "destructive"


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]
    risk: str = SAFE
    category: str = "file"
    body_param: str | None = None  # parameter that takes a multi-line body in the text protocol

    @property
    def required(self) -> list[str]:
        return list(self.parameters.get("required", []))


@dataclass
class ToolResult:
    name: str
    text: str
    is_error: bool = False
    images: list[str] = field(default_factory=list)  # base64 PNGs, for vision-capable models


def obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


def _coerce(value: Any, schema: dict[str, Any]) -> Any:
    """Weak models often send numbers as strings or JSON as text. Fix what is unambiguous."""
    t = schema.get("type")
    if t == "integer" and isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    if t == "number" and isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    if t == "boolean" and isinstance(value, str) and value.lower() in ("true", "false", "yes", "no", "1", "0"):
        return value.lower() in ("true", "yes", "1")
    if t in ("array", "object") and isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed
        except json.JSONDecodeError:
            if t == "array":
                return [value]
    if t == "array" and isinstance(value, list) and "items" in schema:
        return [_coerce(v, schema["items"]) for v in value]
    if t == "string" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self.before_call: list[Callable[[Tool, dict], str | None]] = []  # return text to block the call
        self.after_call: list[Callable[[Tool, dict, ToolResult], None]] = []

    def register(self, tool: Tool) -> Tool:
        self._tools[tool.name] = tool
        return tool

    def tool(self, name: str, description: str, parameters: dict, risk: str = SAFE, category: str = "file",
             body_param: str | None = None):
        def deco(fn: Callable[..., str]) -> Callable[..., str]:
            self.register(Tool(name, description, parameters, fn, risk, category, body_param))
            return fn
        return deco

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def subset(self, names: list[str] | None = None, categories: list[str] | None = None) -> ToolRegistry:
        sub = ToolRegistry()
        sub.before_call, sub.after_call = self.before_call, self.after_call
        for t in self._tools.values():
            if (names is None or t.name in names) and (categories is None or t.category in categories):
                sub.register(t)
        return sub

    # ------------------------------------------------------------ execution
    def call(self, name: str, args: dict[str, Any] | None) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            close = [n for n in self._tools if n.split("_")[0] in name or name in n]
            hint = f" Did you mean: {', '.join(close[:3])}?" if close else ""
            return ToolResult(name, f"ERROR [unknown_tool]: There is no tool named {name}.{hint} "
                                    f"Available tools: {', '.join(self._tools)}", True)
        args = dict(args or {})
        props = tool.parameters.get("properties", {})
        unknown = [k for k in args if k not in props]
        for k in unknown:
            args.pop(k)
        for k, v in list(args.items()):
            args[k] = _coerce(v, props[k])
        missing = [k for k in tool.required if k not in args]
        if missing:
            return ToolResult(name, f"ERROR [missing_argument]: {name} needs: {', '.join(missing)}.", True)
        for hook in self.before_call:
            blocked = hook(tool, args)
            if blocked:
                return ToolResult(name, blocked, True)
        try:
            out = tool.handler(**args)
            result = out if isinstance(out, ToolResult) else ToolResult(name, str(out))
        except ToolError as e:
            result = ToolResult(name, e.to_text(), True)
        except Exception as e:  # never crash the agent loop because of a tool bug
            tb = traceback.format_exc(limit=3)
            result = ToolResult(name, f"ERROR [internal]: {type(e).__name__}: {e}\n{tb}", True)
        if unknown:
            result.text += f"\n(note: ignored unknown arguments: {', '.join(unknown)})"
        for hook in self.after_call:
            hook(tool, args, result)
        return result

    # ------------------------------------------------------------ formats
    def to_openai(self) -> list[dict]:
        return [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                  "parameters": t.parameters}} for t in self._tools.values()]

    def to_anthropic(self) -> list[dict]:
        return [{"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in self._tools.values()]

    def to_gemini(self) -> list[dict]:
        return [{"functionDeclarations": [
            {"name": t.name, "description": t.description, "parameters": gemini_schema(t.parameters)}
            for t in self._tools.values()]}]

    def to_mcp(self) -> list[dict]:
        return [{"name": t.name, "description": t.description, "inputSchema": t.parameters}
                for t in self._tools.values()]


_GEMINI_DROP = {"additionalProperties", "default", "$schema", "examples", "title"}


def gemini_schema(schema: dict) -> dict:
    """Gemini accepts an OpenAPI subset: drop unsupported keys, uppercase types."""
    s = copy.deepcopy(schema)

    def fix(node: Any) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k in _GEMINI_DROP:
                    continue
                if k == "type" and isinstance(v, str):
                    out[k] = v.upper()
                elif k == "properties" and isinstance(v, dict):
                    out[k] = {pk: fix(pv) for pk, pv in v.items()}
                else:
                    out[k] = fix(v)
            if out.get("type") == "OBJECT" and not out.get("properties"):
                out.pop("required", None)
            return out
        if isinstance(node, list):
            return [fix(x) for x in node]
        return node

    return fix(s)
