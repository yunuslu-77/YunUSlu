"""The text protocol: tool use for AIs that can only write text (web chats, desktop apps, weak local models).

A call looks like:

    <<<yw:read path="src/app.py" offset="1" limit="80">>>

    <<<yw:edit path="src/app.py">>>
    <<<find
    return a - b
    ===replace
    return a + b
    >>>end

    <<<yw:run>>>
    pytest -q
    >>>end

Tools with a body parameter (create.content, run.command ...) take a body that ends at >>>end.
Other tools are a single line. The parser is tolerant: code fences, missing >>>end at the end,
single quotes, unquoted values and JSON-style calls are all accepted.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..models.base import ToolCall
from ..tools.registry import ToolRegistry, ToolResult

OPEN_RX = re.compile(r"^\s*<<<\s*yw\s*:\s*([A-Za-z_][\w-]*)\s*(.*?)\s*>{2,3}\s*$")
END_RX = re.compile(r"^\s*>{2,3}\s*end\s*$", re.IGNORECASE)
ATTR_RX = re.compile(r"""([A-Za-z_][\w-]*)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|([^\s"']+))""")
FIND_RX = re.compile(r"^\s*<<<\s*find\s*$", re.IGNORECASE)
REPLACE_RX = re.compile(r"^\s*={3,}\s*replace\s*$", re.IGNORECASE)
FENCE_RX = re.compile(r"^\s*```[\w-]*\s*$")
JSON_CALL_RX = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass
class ParseResult:
    calls: list[ToolCall] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    text: str = ""  # the model's prose with call blocks removed


def _attrs(s: str) -> dict[str, str]:
    out = {}
    for m in ATTR_RX.finditer(s):
        val = next(g for g in m.groups()[1:] if g is not None)
        out[m.group(1)] = val.replace('\\"', '"').replace("\\'", "'")
    return out


def _edits_from_body(body: list[str]) -> list[dict] | None:
    if not any(FIND_RX.match(x) for x in body):
        return None
    edits, cur, mode = [], None, None
    for line in body:
        if FIND_RX.match(line):
            if cur:
                edits.append(cur)
            cur, mode = {"find": [], "replace": []}, "find"
        elif REPLACE_RX.match(line) and cur is not None:
            mode = "replace"
        elif cur is not None and mode:
            cur[mode].append(line)
    if cur:
        edits.append(cur)
    return [{"find": "\n".join(e["find"]), "replace": "\n".join(e["replace"])} for e in edits]


def parse(text: str, registry: ToolRegistry) -> ParseResult:
    res = ParseResult()
    lines = text.replace("\r\n", "\n").split("\n")
    prose: list[str] = []
    i = 0
    while i < len(lines):
        m = OPEN_RX.match(lines[i])
        if not m:
            prose.append(lines[i])
            i += 1
            continue
        name, args = m.group(1).replace("-", "_"), _attrs(m.group(2))
        tool = registry.get(name)
        if tool is None:
            res.errors.append(f"Unknown tool '{name}' on line {i + 1}. Available: {', '.join(registry.names())}")
        has_body = name in ("edit", "multi_edit") or (tool is not None and tool.body_param is not None)
        i += 1
        body: list[str] = []
        # A body parameter given as an attribute (<<<yw:run command="ls">>>) means there is no body.
        if has_body and not (tool is not None and tool.body_param in args):
            closed = False
            while i < len(lines):
                if END_RX.match(lines[i]):
                    closed = True
                    i += 1
                    break
                # File contents may contain anything; other blocks stop at the next call if >>>end was forgotten.
                if OPEN_RX.match(lines[i]) and name != "create":
                    break
                body.append(lines[i])
                i += 1
            if not closed:
                res.errors.append(f"Block '{name}' was not closed with >>>end; assumed it ends there.")
                while body and not body[-1].strip():
                    body.pop()
            if len(body) >= 2 and FENCE_RX.match(body[0]) and FENCE_RX.match(body[-1]):
                body = body[1:-1]
        if tool is None:
            continue
        if name in ("edit", "multi_edit"):
            edits = _edits_from_body(body)
            if edits is None and "find" in args and "replace" in args:
                edits = [{"find": args.pop("find"), "replace": args.pop("replace")}]
            if not edits:
                res.errors.append(f"The {name} block for {args.get('path', '?')} has no <<<find / ===replace sections.")
                continue
            path = args.get("path", "")
            if len(edits) == 1 and name == "edit":
                call_args = {"path": path, **edits[0]}
                if "replace_all" in args:
                    call_args["replace_all"] = args["replace_all"]
                res.calls.append(ToolCall("edit", call_args))
            else:
                res.calls.append(ToolCall("multi_edit", {"path": path, "edits": edits}))
            continue
        if has_body and tool.body_param and body:
            args[tool.body_param] = "\n".join(body) + ("\n" if name == "create" else "")
        res.calls.append(ToolCall(name, args))
    # JSON fallback: {"tool": "read", "args": {...}} inside a ```json fence.
    if not res.calls:
        for m in JSON_CALL_RX.finditer(text):
            try:
                obj = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            name = obj.get("tool") or obj.get("name")
            args = obj.get("args") or obj.get("arguments") or obj.get("parameters") or {}
            if isinstance(name, str) and registry.get(name) and isinstance(args, dict):
                res.calls.append(ToolCall(name, args))
    res.text = "\n".join(prose).strip()
    return res


def format_results(results: list[ToolResult], parse_errors: list[str] | None = None) -> str:
    parts = []
    for e in parse_errors or []:
        parts.append(f'<<<yw:result tool="parser" ok="false">>>\n{e}\n>>>end')
    for r in results:
        parts.append(f'<<<yw:result tool="{r.name}" ok="{"false" if r.is_error else "true"}">>>\n{r.text}\n>>>end')
    return "\n\n".join(parts)


def instructions(registry: ToolRegistry, lang: str = "en") -> str:
    """System-prompt section that teaches the protocol, generated from the registry."""
    lines = []
    for t in registry.all():
        props = t.parameters.get("properties", {})
        req = set(t.required)
        if t.name in ("edit", "multi_edit"):
            continue
        attrs = " ".join(f'{k}="…"' for k in props if k != t.body_param and k in req)
        opt = [k for k in props if k not in req and k != t.body_param]
        sig = f"<<<yw:{t.name}{(' ' + attrs) if attrs else ''}>>>"
        if t.body_param:
            sig += f"\n({t.body_param} here)\n>>>end"
        desc = t.description.split(". ")[0].rstrip(".")
        lines.append(f"- {t.name}: {desc}." + (f" Optional: {', '.join(opt)}." if opt else "") + f"\n{sig}")
    tool_list = "\n\n".join(lines)
    edit_help = ""
    if registry.get("edit"):
        edit_help = (
            "\n\n- edit: change part of a file. Copy the 'find' text EXACTLY from the file (no line numbers). "
            "You may put several find/replace pairs in one block.\n"
            '<<<yw:edit path="src/app.py">>>\n<<<find\n    return a - b\n===replace\n    return a + b\n>>>end'
        )
    head = (
        "## How to use tools (yWorkspace text protocol)\n"
        "You cannot call tools directly. Instead, write tool blocks exactly in the format below. "
        "yWorkspace runs them and replies with <<<yw:result ...>>> blocks. Rules:\n"
        "1. Put each block on its own lines. Do not wrap blocks in code fences.\n"
        "2. You may write several blocks in one message; they run in order.\n"
        "3. After writing blocks, STOP and wait for the results. Never invent results.\n"
        "4. Blocks with a body end with a line containing only >>>end.\n"
        "5. Read a file before you edit it.\n"
    )
    if lang == "tr":
        head += "Kullanıcıyla Türkçe konuş, ama blok biçimini aynen koru.\n"
    return f"{head}\n### Tools\n\n{tool_list}{edit_help}"
