"""CLI commands for the connection paths (MCP, browser extension, desktop bridge) and later stages."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from ..cli_ext import command


def _session(project: str, cfg, engine: bool = True):
    from ..app import build_session
    from ..engine.engine import Approver
    sess = build_session(project, cfg, Approver(), with_engine=engine)
    if sess.engine is not None:
        from .relay import add_check_done_tool
        add_check_done_tool(sess.registry, sess.engine)
    return sess


@command
def mcp_commands(sub, cfg) -> None:
    s = sub.add_parser("mcp", help="MCP sunucusu (Claude Desktop, Cursor, VS Code...) / MCP server")
    s.add_argument("-p", "--project", default=".")
    s.add_argument("--http", type=int, metavar="PORT", help="serve Streamable HTTP instead of stdio")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--token")

    def run(a, cfg) -> int:
        from .mcp_server import McpServer, default_prompts
        sess = _session(a.project, cfg)
        srv = McpServer(sess.registry, default_prompts(cfg.lang))
        if a.http:
            httpd, token = srv.make_http_server(a.host, a.http, a.token)
            print(f"MCP: http://{a.host}:{a.http}/mcp  (Authorization: Bearer {token})", file=sys.stderr)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
        else:
            srv.serve_stdio()
        return 0
    s.set_defaults(fn=run)

    s = sub.add_parser("mcp-config", help="Claude Desktop / Cursor için MCP ayarını yazdır / print MCP client config")
    s.add_argument("-p", "--project", default=".")

    def cfg_cmd(a, cfg) -> int:
        exe = shutil.which("yw") or f"{sys.executable} -m yworkspace.cli"
        parts = exe.split() if " " in exe else [exe]
        entry = {"command": parts[0], "args": parts[1:] + ["mcp", "-p", str(Path(a.project).resolve())]}
        print(json.dumps({"mcpServers": {"yworkspace": entry}}, indent=2))
        print("\nClaude Desktop: Settings → Developer → Edit Config, merge the block above, restart Claude.",
              file=sys.stderr)
        return 0
    s.set_defaults(fn=cfg_cmd)


@command
def bridge_commands(sub, cfg) -> None:
    s = sub.add_parser("bridge-web", help="tarayıcı eklentisi için yerel köprü / relay for the browser extension")
    s.add_argument("-p", "--project", default=".")
    s.add_argument("--port", type=int, default=8766)

    def web(a, cfg) -> int:
        from .relay import Relay, text_session_for
        sess = _session(a.project, cfg)
        relay = Relay(lambda goal: text_session_for(sess, goal, cfg.lang))
        httpd = relay.make_server(port=a.port)
        ext = Path(__file__).resolve().parent.parent / "extension" / "browser"
        print(f"Eşleşme kodu / pairing token: {relay.token}\nPort: {a.port}\n"
              f"Eklenti klasörü / extension folder (chrome://extensions → Load unpacked): {ext}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    s.set_defaults(fn=web)

    s = sub.add_parser("bridge-desktop", help="Masaüstü Köprüsü / desktop bridge")
    s.add_argument("app", help="profile: deepseek, chatgpt, claude, gemini, generic")
    s.add_argument("goal")
    s.add_argument("-p", "--project", default=".")

    def desk(a, cfg) -> int:
        from ..bridge.desktop import AppProfile, BridgeRunner, BridgeStopped, SystemDriver
        from .relay import text_session_for
        profile = AppProfile.load(a.app)
        print(f"{profile.name}: Acil durdurma / emergency stop = Ctrl+Shift+Q (or move the mouse to a screen corner)")
        sess = _session(a.project, cfg)
        try:
            driver = SystemDriver()
        except ImportError as e:
            print(f"Missing package for the desktop bridge: {e}. Install: pip install \"yworkspace[bridge]\"")
            return 2
        runner = BridgeRunner(driver, profile, text_session_for(sess, a.goal, cfg.lang))
        try:
            print(runner.run())
        except BridgeStopped as e:
            print(f"Stopped: {e}")
            return 1
        return 0
    s.set_defaults(fn=desk)


@command
def web_command(sub, cfg) -> None:
    s = sub.add_parser("web", help="web arayüzünü aç / open the web interface")
    s.add_argument("--port", type=int, default=8700)
    s.add_argument("--lan", action="store_true", help="telefondan erişim için yerel ağa aç / allow phones on your Wi-Fi")
    s.add_argument("--no-browser", action="store_true")

    def run(a, cfg) -> int:
        from .web.server import serve
        serve(cfg, "0.0.0.0" if a.lan else "127.0.0.1", a.port, not a.no_browser)
        return 0
    s.set_defaults(fn=run)


@command
def setup_command(sub, cfg) -> None:
    s = sub.add_parser("setup", help="kurulum sihirbazı / setup wizard")
    s.add_argument("--status", action="store_true", help="only show the status of each step")
    s.add_argument("--yes", action="store_true", help="run every automatic action without asking")

    def run(a, cfg) -> int:
        import getpass

        from ..setup.wizard import STEPS, Wizard
        if not a.status and not a.yes and sys.stdin.isatty():
            lang = input("Dil / Language [tr/en] (tr): ").strip().lower() or "tr"
            cfg.lang = "en" if lang.startswith("e") else "tr"
            cfg.save()
        w = Wizard(cfg)
        tr = cfg.lang == "tr"
        print(("Bilgisayarınız: " if tr else "Your computer: ") + w.ctx.info.describe())
        for item in w.status():
            mark = "✓" if item["ok"] else ("–" if item["skipped"] else "✗")
            print(f"{mark} {item['title_tr' if tr else 'title_en']}: {item['detail']}")
        if a.status:
            return 0
        for step in STEPS:
            st = step.check(w.ctx)
            if st.ok or w.done.get(step.id) == "skipped":
                continue
            title = step.title_tr if tr else step.title_en
            print(f"\n=== {title} ===")
            if step.id == "model" and not a.yes:
                choice = input("Model [deepseek-chat / gemini-flash / claude-opus / ollama] "
                               f"({cfg.model}): ").strip() or cfg.model
                cfg.model = choice
                cfg.save()
                from ..models.profiles import get_profile
                prof = get_profile(choice)
                if prof.key_env and not prof.local:
                    w.ctx.answers[prof.key_env] = getpass.getpass(f"{prof.key_env}: ").strip()
            if step.id == "folder" and not a.yes:
                w.ctx.answers["projects_dir"] = input(f"Klasör / folder ({cfg.projects_dir}): ").strip() or None
            actions = w.plan(step.id)
            for act in actions:
                cmd = act.command if isinstance(act.command, str) else " ".join(act.command or [])
                print(f"- {act.describe}" + (f"\n    $ {cmd}" if cmd else "") + (f"\n    {act.manual}" if act.manual else ""))
            if a.yes:
                ans = "e"
            else:
                ans = input("Uygulansın mı? [E/h/atla] " if tr else "Apply? [Y/n/skip] ").strip().lower()
            if ans in ("atla", "skip", "s"):
                w.mark(step.id, "skipped")
                continue
            if ans in ("h", "n", "no", "hayır"):
                continue
            for act in actions:
                try:
                    out = w.run_action(act)
                    print("  " + out.strip().replace("\n", "\n  ")[-2000:])
                    if "REBOOT REQUIRED" in out:
                        return 0
                except Exception as e:
                    print(f"  ✗ {e}")
                    break
            w.mark(step.id, step.check(w.ctx).ok)
        print("\n" + ("Kurulum tamam. Başlamak için: yw web" if tr else "Setup finished. To start: yw web"))
        return 0
    s.set_defaults(fn=run)


@command
def skills_command(sub, cfg) -> None:
    s = sub.add_parser("skills", help="skill kütüphanesi / skill library")
    s.add_argument("action", choices=["list", "show", "match", "export"])
    s.add_argument("arg", nargs="?", help="skill name (show), task text (match) or output folder (export)")
    s.add_argument("--format", action="append", choices=["claude", "chatgpt", "gemini", "deepseek", "prompt"])
    s.add_argument("--lang", action="append", choices=["tr", "en"])
    s.add_argument("--role", default="developer")

    def run(a, cfg) -> int:
        from ..skills import load_all, select
        from ..skills.export import FORMATS, export
        if a.action == "list":
            for sk in load_all():
                print(f"{sk.category:10} {sk.name:20} {sk.title_tr if cfg.lang == 'tr' else sk.title_en}")
        elif a.action == "show":
            sk = next((x for x in load_all() if x.name == a.arg), None)
            if not sk:
                print(f"No skill {a.arg}")
                return 1
            print(sk.text(cfg.lang))
        elif a.action == "match":
            for sk in select(a.role, a.arg or "", Path.cwd()):
                print(sk.name)
        else:
            out = Path(a.arg or "skills-export")
            files = export(out, a.format or FORMATS, a.lang or ("tr", "en"))
            print(f"{len(files)} files written to {out.resolve()}")
        return 0
    s.set_defaults(fn=run)


@command
def plugin_commands(sub, cfg) -> None:
    s = sub.add_parser("plugin", help="eklentiler / plugins")
    s.add_argument("action", choices=["list", "install", "remove", "enable", "disable", "new", "catalog"])
    s.add_argument("arg", nargs="?")
    s.add_argument("--yes", action="store_true")

    def run(a, cfg) -> int:
        from ..sdk import loader
        if a.action == "list":
            items = loader.installed()
            for m in items:
                print(("● " if m.enabled else "○ ") + m.summary())
            if not items:
                print("No plugins installed.")
        elif a.action == "install":
            def approve(meta) -> bool:
                print(meta.summary())
                if meta.entry:
                    print("  ⚠ This plugin contains Python code that runs with yWorkspace's rights. "
                          "Install only plugins you trust.")
                return a.yes or input("Install? [y/N] ").strip().lower() in ("y", "yes", "e", "evet")
            m = loader.install_plugin(a.arg, approve)
            print(f"Installed {m.name} {m.version}")
        elif a.action == "remove":
            loader.remove_plugin(a.arg)
            print(f"Removed {a.arg}")
        elif a.action in ("enable", "disable"):
            loader.set_enabled(a.arg, a.action == "enable")
            print(f"{a.arg}: {a.action}d")
        elif a.action == "new":
            d = loader.scaffold(Path.cwd(), a.arg or "my-plugin")
            print(f"Created {d}. Edit plugin.yaml / plugin.py, then: yw plugin install {d}")
        else:
            cat = Path(loader.__file__).parent / "catalog.json"
            for item in json.loads(cat.read_text("utf-8")):
                print(f"{item['name']:24} {item['description']}  ({item['source']})")
        return 0
    s.set_defaults(fn=run)


@command
def automation_commands(sub, cfg) -> None:
    s = sub.add_parser("automations", help="otomasyonlar / automations")
    s.add_argument("action", choices=["list", "daemon", "tick", "autostart"])
    s.add_argument("--project", default=".")
    s.add_argument("--interval", type=int, default=60)

    def run(a, cfg) -> int:
        import time as _time

        from ..automations import runner as rn
        sess = _session(a.project, cfg, engine=a.action in ("daemon", "tick"))
        try:
            if a.action == "list":
                print(sess.registry.call("automation_list", {}).text)
            elif a.action == "autostart":
                print(sess.registry.call("automation_autostart", {}).text)
            else:
                r = rn.Runner(sess)
                while True:
                    for line in r.tick():
                        print(f"[{_time.strftime('%H:%M')}] {line}", flush=True)
                    if a.action == "tick":
                        break
                    _time.sleep(max(15, a.interval))
        except KeyboardInterrupt:
            pass
        finally:
            sess.close()
        return 0
    s.set_defaults(fn=run)


@command
def bench_commands(sub, cfg) -> None:
    s = sub.add_parser("bench", help="yWorkspace Bench: modelleri yWorkspace ile ve onsuz ölç / measure models")
    s.add_argument("--models", default="", help="comma-separated presets (default: your configured model)")
    s.add_argument("--modes", default="bare,balanced", help="bare, economy, balanced, max")
    s.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    s.add_argument("--out", default="bench-results")

    def run(a, cfg) -> int:
        import copy

        from ..app import provider_factory
        from ..bench import runner as br
        from ..bench import tasks as bt
        from ..skills import skills_for
        models = {}
        for preset in [m.strip() for m in (a.models or cfg.model).split(",") if m.strip()]:
            c = copy.deepcopy(cfg)
            c.model, c.role_models = preset, {}
            models[preset] = provider_factory(c)[0]
        tasks = [bt.get(t.strip()) for t in a.tasks.split(",") if t.strip()] or None
        modes = tuple(m.strip() for m in a.modes.split(",") if m.strip())
        print(f"Running {len(tasks or bt.TASKS)} tasks × {len(models)} models × {len(modes)} modes. "
              "This uses your API keys and costs money.")
        res = br.run_suite(models, tasks, modes, Path(a.out),
                           lambda preset: (lambda role, text: skills_for(role, text, cfg.lang, None, preset)))
        print(br.markdown(res))
        return 0
    s.set_defaults(fn=run)
