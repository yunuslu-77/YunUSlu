"""Botun kendi bilgisayarı: çalışma klasöründe dosyalar ve (onaylı) terminal komutları."""
from __future__ import annotations

import asyncio
from pathlib import Path

from .registry import P, ToolContext, tool


def _safe(ctx: ToolContext, path: str) -> Path:
    root = ctx.app.cfg.workspace.resolve()
    p = (root / path.lstrip("/")).resolve()
    if p != root and root not in p.parents:
        raise ValueError("Çalışma klasörü dışına çıkılamaz")
    return p


@tool("list_files", "Botun çalışma klasöründeki dosyaları listeler.", "computer",
      {"path": P(str, "Alt klasör (boş = kök)", required=False)})
async def list_files(ctx: ToolContext, path: str = ""):
    p = _safe(ctx, path)
    if not p.exists():
        return {"error": "Klasör yok"}
    return [{"name": c.name + ("/" if c.is_dir() else ""), "size": c.stat().st_size} for c in sorted(p.iterdir())][:200]


@tool("read_file", "Çalışma klasöründen dosya okur.", "computer", {"path": P(str, "Dosya yolu")})
async def read_file(ctx: ToolContext, path: str):
    p = _safe(ctx, path)
    if not p.is_file():
        return {"error": "Dosya yok"}
    return {"text": p.read_text("utf-8", "ignore")[:20000]}


@tool("write_file", "Çalışma klasörüne dosya yazar (varsa üzerine yazar).", "computer",
      {"path": P(str, "Dosya yolu"), "content": P(str, "İçerik")})
async def write_file(ctx: ToolContext, path: str, content: str):
    p = _safe(ctx, path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, "utf-8")
    return {"written": str(p.relative_to(ctx.app.cfg.workspace.resolve())), "bytes": len(content.encode())}


@tool("send_file", "Çalışma klasöründeki bir dosyayı kullanıcıya Telegram'dan gönderir.", "computer",
      {"path": P(str, "Dosya yolu")})
async def send_file(ctx: ToolContext, path: str):
    p = _safe(ctx, path)
    if not p.is_file():
        return {"error": "Dosya yok"}
    await ctx.app.notifier.send_document(p.read_bytes(), p.name)
    return {"sent": p.name}


@tool("run_shell", "Sunucuda, çalışma klasöründe terminal komutu çalıştırır (Python betiği, dosya işlemleri, hesaplama). "
      "60 saniye zaman aşımı vardır.", "computer", {"command": P(str, "Bash komutu")}, approval=True,
      summary=lambda a: f"💻 Terminal komutu çalıştır:\n{a['command']}")
async def run_shell(ctx: ToolContext, command: str):
    if not ctx.app.cfg.shell_enabled:
        return {"error": "Terminal kapalı (SHELL_ENABLED=false)"}
    proc = await asyncio.create_subprocess_shell(
        command, cwd=str(ctx.app.cfg.workspace), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "Zaman aşımı (60 sn)"}
    return {"exit_code": proc.returncode, "output": out.decode("utf-8", "ignore")[-8000:]}
