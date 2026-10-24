"""Commands added by later stages (web, mcp, bridge, setup, build ...)."""

from __future__ import annotations

COMMANDS = []  # functions (subparsers, cfg) -> None


def command(fn):
    COMMANDS.append(fn)
    return fn


def add_commands(sub, cfg) -> None:
    import importlib
    for mod in ("yworkspace.interfaces.cli_commands",):
        try:
            importlib.import_module(mod)
        except ImportError:
            pass
    for fn in COMMANDS:
        fn(sub, cfg)
