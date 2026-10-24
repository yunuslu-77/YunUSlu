"""Optional tool groups and done gates, installed into a session when their dependencies are present."""

from __future__ import annotations

INSTALLERS = []  # functions (session) -> None
GATE_INSTALLERS = []  # functions (session) -> None


def register(fn):
    INSTALLERS.append(fn)
    return fn


def register_gate(fn):
    GATE_INSTALLERS.append(fn)
    return fn


def _load_builtin_extensions() -> None:
    import importlib
    for mod in ("yworkspace.tools.verify", "yworkspace.operator.tools", "yworkspace.studio.tools",
                "yworkspace.factory.tools", "yworkspace.deploy.tools", "yworkspace.labs.security.tools",
                "yworkspace.labs.data.tools", "yworkspace.ops.tools", "yworkspace.automations.tools",
                "yworkspace.engine.parallel", "yworkspace.sdk.loader"):
        try:
            importlib.import_module(mod)
        except ImportError:
            continue


def install_all(session) -> None:
    _load_builtin_extensions()
    for fn in INSTALLERS:
        fn(session)


def install_gates(session) -> None:
    for fn in GATE_INSTALLERS:
        fn(session)
