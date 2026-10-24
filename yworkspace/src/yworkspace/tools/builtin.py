"""Built-in file and terminal tools. Descriptions are written for weak models: short, concrete, with rules."""

from __future__ import annotations

from ..core.workspace import Workspace
from .registry import DESTRUCTIVE, EXEC, SAFE, WRITE, Tool, ToolRegistry, obj

S = {"type": "string"}
INT = {"type": "integer"}
B = {"type": "boolean"}


def add_file_tools(reg: ToolRegistry, ws: Workspace) -> None:
    reg.register(Tool(
        "read",
        "Read a text file. Returns lines prefixed with line numbers (the number column is not part of the file). "
        "Big files are paged: use offset and limit. You must read a file before you edit or overwrite it.",
        obj({"path": S, "offset": {**INT, "description": "first line to read (1-based)"},
             "limit": {**INT, "description": "how many lines (default 2000)"}}, ["path"]),
        ws.read, SAFE, "file"))
    reg.register(Tool(
        "outline",
        "Show the structure of a file (classes, functions, headings) with line numbers, without reading it all. "
        "Use it on big files, then read only the lines you need.",
        obj({"path": S}, ["path"]), ws.outline, SAFE, "file"))
    reg.register(Tool(
        "create",
        "Create a new file with the full content. Folders are created automatically. "
        "To change an existing file use edit instead. Only set overwrite=true to replace a whole file you have read.",
        obj({"path": S, "content": {**S, "description": "complete file content"}, "overwrite": B}, ["path", "content"]),
        ws.create, WRITE, "file", body_param="content"))
    reg.register(Tool(
        "edit",
        "Change part of a file: 'find' must be copied EXACTLY from the file (same spaces and indentation, "
        "no line numbers) and must appear exactly once; it is replaced by 'replace'. Include 2-3 surrounding lines "
        "if the text is not unique. Read the file first. Never rewrite a whole file with edit.",
        obj({"path": S, "find": S, "replace": S,
             "replace_all": {**B, "description": "replace every occurrence"}}, ["path", "find", "replace"]),
        ws.edit, WRITE, "file"))
    reg.register(Tool(
        "multi_edit",
        "Apply several find/replace edits to one file at once. Either all edits apply or none do. "
        "Edits are applied in order, so later edits see the result of earlier ones.",
        obj({"path": S, "edits": {"type": "array", "items": obj({"find": S, "replace": S, "replace_all": B},
                                                                 ["find", "replace"])}}, ["path", "edits"]),
        ws.multi_edit, WRITE, "file"))
    reg.register(Tool("move", "Move or rename a file.", obj({"src": S, "dst": S}, ["src", "dst"]),
                      ws.move, WRITE, "file"))
    reg.register(Tool("delete", "Delete a file (it can be restored with undo) or an empty folder.",
                      obj({"path": S}, ["path"]), ws.delete, DESTRUCTIVE, "file"))
    reg.register(Tool("list", "List files and folders (with sizes). Dependency and build folders are skipped.",
                      obj({"path": S, "depth": INT}), ws.list, SAFE, "file"))
    reg.register(Tool("glob", "Find files by name pattern, e.g. '*.py' or 'src/**/*.tsx'.",
                      obj({"pattern": S}, ["pattern"]), ws.glob, SAFE, "file"))
    reg.register(Tool(
        "search", "Search file contents with a regular expression. Returns path:line: text.",
        obj({"pattern": S, "path": S, "file_glob": {**S, "description": "only files matching, e.g. '*.py'"},
             "ignore_case": B}, ["pattern"]), ws.search, SAFE, "file"))
    reg.register(Tool("history", "List recent file changes with their change ids.", obj({"limit": INT}),
                      ws.history_text, SAFE, "file"))
    reg.register(Tool("diff", "Show the diff of a change (default: the latest).", obj({"change_id": S}),
                      ws.diff, SAFE, "file"))
    reg.register(Tool("undo", "Undo a change (default: the latest).", obj({"change_id": S}),
                      ws.undo, WRITE, "file"))


def add_shell_tools(reg: ToolRegistry, sandbox) -> None:
    def run(command: str, timeout: int = 120, cwd: str | None = None) -> str:
        return sandbox.run(command, timeout=timeout, cwd=cwd).to_text()

    def install(manager: str, packages: list[str]) -> str:
        return sandbox.install(manager, packages).to_text()

    reg.register(Tool(
        "run",
        "Run a shell command in the project's isolated Linux sandbox (working directory = project root). "
        "Returns exit code and output. Use it for tests, builds, scripts and git. "
        "Do NOT use it for servers or watchers that never exit: use start_process for those.",
        obj({"command": S, "timeout": {**INT, "description": "seconds, default 120, max 3600"},
             "cwd": {**S, "description": "sub-folder to run in"}}, ["command"]),
        run, EXEC, "shell", body_param="command"))
    reg.register(Tool(
        "start_process",
        "Start a long-running command in the background (dev server, watcher) under a name. "
        "Returns its first log lines and the ports it can be reached on.",
        obj({"name": S, "command": S, "cwd": S}, ["name", "command"]),
        sandbox.start_process, EXEC, "shell", body_param="command"))
    reg.register(Tool("logs", "Show the last lines of a background process's output.",
                      obj({"name": S, "tail": INT}, ["name"]), sandbox.logs, SAFE, "shell"))
    reg.register(Tool("stop_process", "Stop a background process.", obj({"name": S}, ["name"]),
                      sandbox.stop_process, EXEC, "shell"))
    reg.register(Tool("processes", "List background processes and whether they are running.", obj({}),
                      sandbox.processes, SAFE, "shell"))
    reg.register(Tool(
        "install", "Install packages in the sandbox. manager: pip, npm, pnpm or apt.",
        obj({"manager": {"type": "string", "enum": ["pip", "npm", "pnpm", "apt"]},
             "packages": {"type": "array", "items": S}}, ["manager", "packages"]),
        install, EXEC, "shell"))


def build_registry(ws: Workspace, sandbox=None) -> ToolRegistry:
    reg = ToolRegistry()
    add_file_tools(reg, ws)
    if sandbox is not None:
        add_shell_tools(reg, sandbox)
    return reg
