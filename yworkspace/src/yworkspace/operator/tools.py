"""Screen tools: one set of tools for every platform (web now; Android, desktop, VM backends plug in)."""

from __future__ import annotations

from ..core.errors import ToolError
from ..engine.engine import GateResult
from ..extensions import register, register_gate
from ..tools.registry import SAFE, Tool, ToolResult, obj
from .journeys import JourneyResult, JourneyStore, journeys_gate_status
from .web import PERSONAS, WebScreen

S = {"type": "string"}
INT = {"type": "integer"}


def _backend(kind: str, evidence, persona, target: str):
    if kind == "web":
        return WebScreen(evidence, persona)
    if kind == "android":
        from .android import AndroidScreen
        return AndroidScreen(evidence, persona)
    if kind == "desktop":
        from .desktop import DesktopScreen
        return DesktopScreen(evidence, persona)
    if kind == "vm":
        from .vm import VmScreen
        return VmScreen(evidence, persona)
    if kind == "ios":
        from .appium import AppiumScreen
        return AppiumScreen(evidence, persona)
    raise ToolError("bad_kind", f"Unknown screen kind {kind}.", "Use web, android, ios, desktop or vm.")


def _tap_xy(scr, x: int, y: int):
    if hasattr(scr, "click_xy"):
        scr.click_xy(int(x), int(y))
    elif hasattr(scr, "_page") and scr._page is not None:
        scr._page.mouse.click(int(x), int(y))
    else:
        from .base import Element
        scr.elements.append(Element(9999, "point", "", int(x), int(y), 2, 2))
        scr.click(9999)
    return scr.view()


def _device(scr, action: str) -> str:
    if not hasattr(scr, "device"):
        raise ToolError("unsupported", "Device actions are available on Android screens.")
    return scr.device(action)


@register
def install(session) -> None:
    reg, root = session.registry, session.workspace.root
    state = {"screen": None, "kind": None}
    store = JourneyStore(root)

    def screen():
        if state["screen"] is None:
            raise ToolError("no_screen", "No screen is open.", "Call screen_open first.")
        return state["screen"]

    def as_result(name: str, view) -> ToolResult:
        text, images = view if isinstance(view, tuple) else (view, [])
        return ToolResult(name, text, images=images)

    def screen_open(target: str, kind: str = "web", persona: str = "first_time") -> ToolResult:
        if persona not in PERSONAS:
            raise ToolError("bad_persona", f"Unknown persona {persona}.", f"Use one of: {', '.join(PERSONAS)}")
        if kind == "desktop" and session.engine is not None:
            ok, why = session.engine.approver.approve("tool", f"Use your real desktop: control mouse and keyboard in "
                                                               f"the window '{target}'")
            if not ok:
                raise ToolError("denied", "The user did not allow desktop control." + (f" {why}" if why else ""))
        if state["screen"] is not None:
            state["screen"].close()
        evidence = root / ".yw" / "evidence" / f"{kind}-{persona}"
        state["screen"] = _backend(kind, evidence, PERSONAS[persona], target)
        state["kind"] = kind
        return as_result("screen_open", state["screen"].open(target))

    def screen_view() -> ToolResult:
        return as_result("screen_view", screen().view())

    def act(name: str, fn):
        def run(**kw) -> ToolResult:
            fn(screen(), **kw)
            return as_result(name, screen().view())
        return run

    def wait_for(text: str, timeout: int = 15) -> ToolResult:
        ok = screen().wait_for(text, timeout)
        view = screen().view()
        prefix = f"'{text}' appeared." if ok else f"'{text}' did NOT appear within {timeout}s."
        text_, images = view if isinstance(view, tuple) else (view, [])
        return ToolResult("wait_for", prefix + "\n\n" + text_, not ok, images)

    def screen_close() -> str:
        if state["screen"] is None:
            return "No screen open."
        out = state["screen"].close()
        state["screen"] = None
        return out

    def a11y_check() -> str:
        issues = screen().a11y()
        return "No accessibility issues found by the automatic checks." if not issues else \
            "Accessibility issues:\n" + "\n".join(f"- {i}" for i in issues)

    def journey_result(name: str, passed: bool, notes: str = "") -> str:
        scr = state["screen"]
        evidence = []
        if scr is not None and hasattr(scr, "evidence_dir"):
            evidence = sorted(str(p.relative_to(root)) for p in scr.evidence_dir.glob("step-*.png"))[-5:]
        persona = scr.persona.key if scr is not None else ""
        store.add(JourneyResult(name, bool(passed), persona, notes, evidence))
        return f"Recorded journey '{name}': {'PASSED' if passed else 'FAILED'} ({len(evidence)} screenshots as evidence)."

    def journey_export(name: str) -> str:
        scr = screen()
        if not hasattr(scr, "export_test"):
            raise ToolError("unsupported", "Exporting tests is supported for web screens.")
        code = scr.export_test(name)
        slug = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")[:50]
        path = f"tests/e2e/test_{slug}.py"
        exists = (root / path).exists()
        if exists:
            session.workspace.read(path)
        session.workspace.create(path, code, overwrite=exists)
        return f"Wrote {path}. It needs pytest-playwright in the project's test environment:\n{code}"

    tools = [
        Tool("screen_open", "Open an app on a screen and see it. kind: web (URL), android (APK path or package), "
             "ios (bundle id or .app; needs Appium on a Mac), desktop (window title), vm (ISO/disk image). "
             "persona: " + ", ".join(
                 f"{k} ({p.title_tr})" for k, p in PERSONAS.items()),
             obj({"target": S, "kind": {"type": "string", "enum": ["web", "android", "ios", "desktop", "vm"]},
                  "persona": S}, ["target"]), screen_open, "exec", "operator"),
        Tool("screen_view", "Look at the screen: numbered elements, visible text, console errors, screenshot.",
             obj({}), screen_view, SAFE, "operator"),
        Tool("tap", "Click/tap element number n (from screen_view), like a person.",
             obj({"n": INT, "double": {"type": "boolean"}}, ["n"]), act("tap", lambda s, n, double=False: s.click(n, double)),
             "exec", "operator"),
        Tool("type", "Click element n and type text at human speed. submit=true presses Enter after.",
             obj({"n": INT, "text": S, "clear": {"type": "boolean"}, "submit": {"type": "boolean"}}, ["n", "text"]),
             act("type", lambda s, n, text, clear=True, submit=False: s.type(n, text, clear, submit)), "exec",
             "operator"),
        Tool("key", "Press a key or shortcut, e.g. Enter, Tab, Escape, Control+A.", obj({"keys": S}, ["keys"]),
             act("key", lambda s, keys: s.key(keys)), "exec", "operator"),
        Tool("scroll", "Scroll up or down.", obj({"direction": {"type": "string", "enum": ["up", "down"]},
                                                 "amount": INT}),
             act("scroll", lambda s, direction="down", amount=600: s.scroll(direction, amount)), "exec", "operator"),
        Tool("drag", "Drag element n_from onto element n_to.", obj({"n_from": INT, "n_to": INT}, ["n_from", "n_to"]),
             act("drag", lambda s, n_from, n_to: s.drag(n_from, n_to)), "exec", "operator"),
        Tool("select_option", "Choose an option in a dropdown (element n).", obj({"n": INT, "option": S}, ["n", "option"]),
             act("select_option", lambda s, n, option: s.select(n, option)), "exec", "operator"),
        Tool("go_back", "Go back (browser back / Android back button).", obj({}),
             act("go_back", lambda s: s.back()), "exec", "operator"),
        Tool("reload", "Reload the screen.", obj({}), act("reload", lambda s: s.reload()), "exec", "operator"),
        Tool("wait_for", "Wait until a text appears on screen.", obj({"text": S, "timeout": INT}, ["text"]),
             wait_for, SAFE, "operator"),
        Tool("a11y_check", "Automatic accessibility checks on the current screen (labels, contrast, tap size).",
             obj({}), a11y_check, SAFE, "operator"),
        Tool("journey_result", "Record whether a user journey from the spec worked end to end (with notes on "
             "problems found).", obj({"name": S, "passed": {"type": "boolean"}, "notes": S}, ["name", "passed"]),
             journey_result, SAFE, "operator"),
        Tool("journey_export", "Turn the actions done on this screen into an automated regression test.",
             obj({"name": S}, ["name"]), journey_export, "write", "operator"),
        Tool("screen_close", "Close the screen (saves the video).", obj({}), screen_close, SAFE, "operator"),
        Tool("tap_xy", "Click/tap a point by coordinates (for screens without element numbers, e.g. a VM).",
             obj({"x": INT, "y": INT}, ["x", "y"]), lambda x, y: as_result("tap_xy", _tap_xy(screen(), x, y)),
             "exec", "operator"),
        Tool("device", "Change the device like a user would (Android): rotate, portrait, dark_mode, light_mode, "
             "offline, online, home.", obj({"action": S}, ["action"]),
             lambda action: _device(screen(), action), "exec", "operator"),
    ]
    for t in tools:
        reg.register(t)
    session.close_hooks.append(screen_close)


@register_gate
def install_gate(session) -> None:
    def gate(engine) -> GateResult:
        ok, detail = journeys_gate_status(engine.root, engine.state.spec)
        return GateResult("user journeys done like a real user", ok, "" if ok else detail)

    def walk_journeys(engine) -> None:
        ok, detail = journeys_gate_status(engine.root, engine.state.spec)
        if ok:
            return
        engine.run_role("test_user", "Persona: first_time (İlk kez kullanan). Start the app with start_process if "
                        "it is not running, open it with screen_open, and walk through these journeys. Record each "
                        f"one with journey_result.\n{detail}")

    session.engine.extra_gates.append(gate)
    session.engine.pre_gate_hooks.append(walk_journeys)
