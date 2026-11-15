"""Araç (tool) kayıt sistemi. Her araç bir gruba aittir; ajanlar grup listesiyle araç alır."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


@dataclass
class ToolContext:
    app: Any            # bot.app.App
    chat_id: int
    agent: str = "asistan"
    depth: int = 0
    approved: bool = False  # kullanıcı onayından sonra çalışıyorsa True


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    func: Callable[..., Awaitable[Any]]
    group: str
    approval: bool | Callable[[dict], bool] = False
    summary: Callable[[dict], str] | None = None

    def needs_approval(self, args: dict) -> bool:
        return self.approval(args) if callable(self.approval) else bool(self.approval)

    def describe(self, args: dict) -> str:
        if self.summary:
            try:
                return self.summary(args)
            except Exception:
                pass
        pretty = ", ".join(f"{k}={str(v)[:200]}" for k, v in args.items())
        return f"{self.name}({pretty})"

    def declaration(self) -> dict:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


REGISTRY: dict[str, Tool] = {}


def P(type_: type | str, description: str, required: bool = True, enum: list | None = None,
      items: str = "string", default: Any = None) -> dict:
    t = type_ if isinstance(type_, str) else TYPE_MAP[type_]
    d: dict = {"type": t, "description": description, "_required": required}
    if enum:
        d["enum"] = enum
    if t == "array":
        d["items"] = {"type": items}
    return d


def tool(name: str, description: str, group: str, params: dict | None = None,
         approval: bool | Callable[[dict], bool] = False, summary: Callable[[dict], str] | None = None):
    params = params or {}
    props, required = {}, []
    for k, v in params.items():
        v = dict(v)
        if v.pop("_required", True):
            required.append(k)
        props[k] = v
    schema: dict = {"type": "object", "properties": props}
    if required:
        schema["required"] = required

    def deco(fn):
        REGISTRY[name] = Tool(name, description, schema, fn, group, approval, summary)
        return fn
    return deco


def tools_for_groups(groups: list[str]) -> list[Tool]:
    return [t for t in REGISTRY.values() if t.group in groups]


def all_groups() -> list[str]:
    return sorted({t.group for t in REGISTRY.values()})
