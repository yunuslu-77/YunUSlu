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
