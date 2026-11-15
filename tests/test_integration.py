"""Gerçek ağ: uvicorn sunucusu + gerçek websockets istemcisiyle çalışan telefon köprüsü."""
import asyncio
import socket
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_phone import FakeRunner  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phone_bridge"))
from bridge import Bridge  # noqa: E402

from bot.dashboard import create_app  # noqa: E402
from bot.tools import ToolContext  # noqa: E402
from bot.tools import phone as phone_tools  # noqa: E402


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


async def test_real_websocket_bridge(app):
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(app), host="127.0.0.1", port=port, log_level="error"))
    srv = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    runner = FakeRunner()
    bridge = Bridge({"SERVER_URL": f"ws://127.0.0.1:{port}/phone/ws", "PHONE_TOKEN": app.cfg.phone_token,
                     "DEVICE_NAME": "Gerçek Test"}, runner)
    br = asyncio.create_task(bridge.forever())
    try:
        for _ in range(100):
            if app.phone.online:
                break
            await asyncio.sleep(0.05)
        assert app.phone.online
        ctx = ToolContext(app, 42)
        assert (await phone_tools.phone_status(ctx))["battery"]["percentage"] == 80
        await phone_tools.phone_screen_control(ctx, 1, "test")
        look = await phone_tools.phone_screen_look(ctx, "?", send_to_user=True)  # ikili dosya aktarımı
        assert look["width"] == 1080
    finally:
        br.cancel()
        server.should_exit = True
        await srv
