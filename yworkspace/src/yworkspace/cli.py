"""yw — the yWorkspace command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import Config, home, set_secret
from .engine.engine import Approver
from .engine.loop import LoopEvent
from .i18n import t

COLORS = {"assistant": "\033[36m", "tool_call": "\033[33m", "tool_result": "\033[90m", "error": "\033[31m",
          "info": "\033[35m", "done": "\033[32m"}
RESET = "\033[0m"


def _color() -> bool:
    return sys.stdout.isatty()


def print_event(ev: LoopEvent, verbose: bool = False) -> None:
    c = COLORS.get(ev.kind, "") if _color() else ""
    r = RESET if c else ""
    if ev.kind == "tool_call":
        args = json.dumps(ev.data.get("args", {}), ensure_ascii=False)
        print(f"{c}→ {ev.text} {args[:200]}{r}")
    elif ev.kind == "tool_result":
        text = ev.text if verbose else ev.text.split("\n")[0][:200]
        mark = "✗" if ev.data.get("is_error") else "✓"
        print(f"{c}  {mark} {text}{r}")
    elif ev.kind in ("assistant", "done"):
        if ev.text:
            print(f"{c}{ev.text}{r}")
    else:
        print(f"{c}[{ev.kind}] {ev.text}{r}")


class CliApprover(Approver):
    def __init__(self, lang: str):
        self.lang = lang

    def approve(self, kind: str, summary: str) -> tuple[bool, str]:
        print(f"\n=== {t('approve_' + kind, self.lang)} ===\n{summary}\n")
        ans = input(t("approve_prompt", self.lang)).strip()
        if ans.lower() in ("", "e", "evet", "y", "yes"):
            return True, ""
        if ans.lower() in ("h", "hayır", "n", "no"):
            return False, ""
        return False, ans

    def question(self, text: str) -> str | None:
        print(f"\n? {text}")
        return input("> ").strip() or None


def read_multiline(prompt: str) -> str:
    print(prompt)
    lines = []
    for line in sys.stdin:
        if line.rstrip("\n") == "///":
            break
        lines.append(line)
    return "".join(lines)


# ------------------------------------------------------------------ commands
def cmd_init(a, cfg: Config) -> int:
    root = Path(a.path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    from .core.workspace import Workspace
    Workspace(root)
    if not (root / ".git").exists():
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=root)
    gi = root / ".gitignore"
    if not gi.exists():
        gi.write_text(".yw/\n.env\nnode_modules/\n__pycache__/\n", "utf-8")
    print(t("init_done", cfg.lang).format(path=root))
    return 0


def cmd_do(a, cfg: Config) -> int:
    for k in ("model", "autonomy", "quality", "sandbox"):
        if getattr(a, k, None):
            setattr(cfg, k, getattr(a, k))
    if a.budget is not None:
        cfg.budget_usd = a.budget
    from .app import build_session
    sess = build_session(a.project, cfg, CliApprover(cfg.lang), lambda e: print_event(e, a.verbose))
    try:
        report = sess.engine.run(a.goal)
    except KeyboardInterrupt:
        print("\n" + t("stopped", cfg.lang))
        return 130
    finally:
        sess.close()
    print("\n" + report.text())
    return 0 if report.finished else 1


def cmd_manual(a, cfg: Config) -> int:
    from .app import build_session
    from .core import clipboard
    from .engine.roles import ROLES, system_prompt
    from .protocol.session import TextSession
    sess = build_session(a.project, cfg, with_engine=False)
    ts = TextSession(sess.registry, system_prompt(ROLES["developer"], cfg.lang).replace(
        "You work on exactly ONE task (given below).", "Complete the task below."), a.goal, cfg.lang)
    opening = ts.opening()
    use_clip = clipboard.available() and not a.no_clipboard
    print(t("manual_intro", cfg.lang))
    for part in ts.split(opening):
        print("\n" + "=" * 70 + "\n" + part + "\n" + "=" * 70)
        if use_clip:
            clipboard.copy(part)
            input(t("manual_copied", cfg.lang))
    while True:
        if use_clip:
            input(t("manual_wait_clip", cfg.lang))
            reply = clipboard.paste() or ""
        else:
            reply = read_multiline(t("manual_paste", cfg.lang))
        if not reply.strip():
            break
        res = ts.handle(reply)
        if res.done:
            print(t("manual_done", cfg.lang))
            print(res.prose)
            break
        print(t("manual_ran", cfg.lang).format(calls=res.calls, errors=res.errors))
        for part in ts.split(res.reply_to_ai):
            print("\n" + "=" * 70 + "\n" + part + "\n" + "=" * 70)
            if use_clip:
                clipboard.copy(part)
                input(t("manual_copied", cfg.lang))
    sess.close()
    return 0


def cmd_tools(a, cfg: Config) -> int:
    from .app import build_session
    sess = build_session(a.project, cfg, with_engine=a.all)
    for tool in sess.registry.all():
        print(f"{tool.name:22} [{tool.category}/{tool.risk}] {tool.description.split('. ')[0]}")
    return 0


def cmd_call(a, cfg: Config) -> int:
    from .app import build_session
    sess = build_session(a.project, cfg, with_engine=False)
    res = sess.registry.call(a.tool, json.loads(a.args or "{}"))
    print(res.text)
    return 1 if res.is_error else 0


def cmd_models(a, cfg: Config) -> int:
    from .config import get_secret
    from .models.profiles import PRESETS
    for p in PRESETS.values():
        key = "local" if p.local else ("key ✓" if p.key_env and get_secret(p.key_env) else f"needs {p.key_env}")
        price = f"${p.price_in}/{p.price_out}" if p.price_in is not None else "price ?"
        mark = "*" if p.id == cfg.model else " "
        print(f"{mark} {p.id:18} {p.model:28} ctx={p.context_window:>9,} {p.tier:8} {price:14} {key}")
    return 0


def cmd_config(a, cfg: Config) -> int:
    if a.key is None:
        print(json.dumps(cfg.__dict__, indent=2, ensure_ascii=False))
        return 0
    if a.value is None:
        print(getattr(cfg, a.key))
        return 0
    current = getattr(cfg, a.key)
    value: object = a.value
    if isinstance(current, bool):
        value = a.value.lower() in ("1", "true", "yes", "evet")
    elif isinstance(current, int):
        value = int(a.value)
    elif isinstance(current, float):
        value = float(a.value)
    elif isinstance(current, dict):
        value = json.loads(a.value)
    setattr(cfg, a.key, value)
    cfg.save()
    print(f"{a.key} = {value}")
    return 0


def cmd_key(a, cfg: Config) -> int:
    where = set_secret(a.name, a.value)
    print(t("key_saved", cfg.lang).format(name=a.name, where=where))
    return 0


def cmd_status(a, cfg: Config) -> int:
    from .engine.state import ProjectState
    st = ProjectState.load(Path(a.project))
    print(st.summary())
    print(st.tasks_text())
    print("\n" + st.progress(15))
    return 0


def cmd_doctor(a, cfg: Config) -> int:
    from .setup.doctor import run_doctor
    ok = True
    for item in run_doctor(cfg):
        print(("✓ " if item.ok else "✗ ") + item.name + (f" — {item.detail}" if item.detail else ""))
        ok = ok and (item.ok or not item.required)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    cfg = Config.load()
    p = argparse.ArgumentParser(prog="yw", description="yWorkspace — " + t("tagline", cfg.lang))
    p.add_argument("--version", action="version", version=f"yWorkspace {__version__}")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("init", help=t("help_init", cfg.lang))
    s.add_argument("path", nargs="?", default=".")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("do", help=t("help_do", cfg.lang))
    s.add_argument("goal")
    s.add_argument("-p", "--project", default=".")
    s.add_argument("-m", "--model")
    s.add_argument("--autonomy", choices=["steps", "milestones", "auto"])
    s.add_argument("--quality", choices=["economy", "balanced", "max"])
    s.add_argument("--sandbox", choices=["docker", "local"])
    s.add_argument("--budget", type=float)
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_do)

    s = sub.add_parser("manual", help=t("help_manual", cfg.lang))
    s.add_argument("goal")
    s.add_argument("-p", "--project", default=".")
    s.add_argument("--no-clipboard", action="store_true")
    s.set_defaults(fn=cmd_manual)

    s = sub.add_parser("tools", help=t("help_tools", cfg.lang))
    s.add_argument("-p", "--project", default=".")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_tools)

    s = sub.add_parser("call", help=t("help_call", cfg.lang))
    s.add_argument("tool")
    s.add_argument("args", nargs="?")
    s.add_argument("-p", "--project", default=".")
    s.set_defaults(fn=cmd_call)

    sub.add_parser("models", help=t("help_models", cfg.lang)).set_defaults(fn=cmd_models)

    s = sub.add_parser("config", help=t("help_config", cfg.lang))
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    s.set_defaults(fn=cmd_config)

    s = sub.add_parser("key", help=t("help_key", cfg.lang))
    s.add_argument("name")
    s.add_argument("value")
    s.set_defaults(fn=cmd_key)

    s = sub.add_parser("status", help=t("help_status", cfg.lang))
    s.add_argument("-p", "--project", default=".")
    s.set_defaults(fn=cmd_status)

    sub.add_parser("doctor", help=t("help_doctor", cfg.lang)).set_defaults(fn=cmd_doctor)

    from .cli_ext import add_commands
    add_commands(sub, cfg)

    a = p.parse_args(argv)
    if not getattr(a, "fn", None):
        p.print_help()
        print(f"\n{t('home_dir', cfg.lang)}: {home()}")
        return 0
    return a.fn(a, cfg)


if __name__ == "__main__":
    sys.exit(main())
