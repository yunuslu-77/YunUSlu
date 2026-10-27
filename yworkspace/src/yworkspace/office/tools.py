"""Office tools: Word, Excel and PowerPoint files for every AI - read, create, edit precisely, check visually."""

from __future__ import annotations

import base64
import platform
import shutil
import subprocess
import time
from pathlib import Path

from ..core.errors import ToolError
from ..extensions import register
from ..tools.registry import EXEC, SAFE, WRITE, Tool, ToolResult, obj
from . import files as of

S = {"type": "string"}
OBJS = {"type": "array", "items": {"type": "object"}}
KINDS = {".docx": "docx", ".xlsx": "xlsx", ".xlsm": "xlsx", ".pptx": "pptx"}


@register
def install(session) -> None:
    reg, ws = session.registry, session.workspace

    def P(path: str, must_exist: bool = False, ext: tuple[str, ...] = ()) -> Path:
        p = ws.resolve(path)
        if ext and p.suffix.lower() not in ext:
            raise ToolError("bad_type", f"{path} must be a {' or '.join(ext)} file.")
        if must_exist and not p.exists():
            raise ToolError("not_found", f"{path} does not exist.", "Use list or glob to find it.")
        return p

    def backup(p: Path) -> str:
        """Office files are binary, so the text history cannot undo them: keep a copy before every change."""
        if not p.exists():
            return ""
        d = ws.root / ".yw" / "office-backup"
        d.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest, n = d / f"{p.stem}.{stamp}{p.suffix}", 1
        while dest.exists():  # several changes in the same second must not overwrite each other
            n += 1
            dest = d / f"{p.stem}.{stamp}-{n}{p.suffix}"
        shutil.copy2(p, dest)
        return f" (previous version saved as {ws.rel(dest)})"

    def office_read(path: str, sheet: str = "", cell_range: str = "") -> str:
        p = P(path, True, (".docx", ".xlsx", ".xlsm", ".pptx", ".doc", ".xls", ".ppt", ".odt", ".ods", ".odp"))
        kind = KINDS.get(p.suffix.lower())
        if kind is None:  # old or OpenDocument formats: convert a temporary copy first
            target = {".doc": "docx", ".odt": "docx", ".xls": "xlsx", ".ods": "xlsx", ".ppt": "pptx",
                      ".odp": "pptx"}[p.suffix.lower()]
            tmp = ws.root / ".yw" / "office-tmp"
            p = of.convert(p, target, tmp)
            kind = target
        if kind == "docx":
            return of.read_docx(p)
        if kind == "xlsx":
            return of.read_xlsx(p, sheet, cell_range)
        return of.read_pptx(p)

    def office_docx_create(path: str, markdown: str = "", blocks: list[dict] | None = None, title: str = "",
                           template: str = "", overwrite: bool = False) -> str:
        p = P(path, ext=(".docx",))
        if p.exists() and not overwrite:
            raise ToolError("exists", f"{path} exists.", "Edit it with office_docx_edit, or set overwrite=true.")
        for b in blocks or []:
            if b.get("type") == "image":
                b["path"] = str(P(b["path"], True))
        note = backup(p)
        of.create_docx(p, blocks, markdown, title, base=P(template, True) if template else None)
        return f"Wrote {path}{note}. Check it with office_render before delivering."

    def office_docx_edit(path: str, edits: list[dict]) -> str:
        p = P(path, True, (".docx",))
        note = backup(p)
        report = of.edit_docx(p, edits)
        return f"Edited {path}, formatting kept{note}:\n" + "\n".join(report)

    def office_xlsx_write(path: str, cells: dict, sheet: str = "", widths: dict | None = None,
                          bold_rows: list[int] | None = None, number_formats: dict | None = None) -> str:
        p = P(path, ext=(".xlsx",))
        note = backup(p)
        results, recalculated = of.write_xlsx(p, sheet, cells, widths, bold_rows, number_formats)
        text = f"Wrote {len(cells)} cells to {path}{note}."
        if results:
            text += ("\nFormula results (calculated by LibreOffice):\n" if recalculated else
                     "\nFormulas are saved; install LibreOffice to calculate and check them here:\n") + "\n".join(results)
            errors = [r for r in results if any(e in r for e in of.ERRORS)]
            if errors:
                text += "\nFORMULA ERRORS - fix them:\n" + "\n".join(errors)
        return text

    def office_pptx_create(path: str, slides: list[dict], title: str = "", template: str = "",
                           overwrite: bool = False) -> str:
        p = P(path, ext=(".pptx",))
        if p.exists() and not overwrite:
            raise ToolError("exists", f"{path} exists.", "Set overwrite=true to replace it.")
        for s in slides:
            if s.get("image"):
                s["image"] = str(P(s["image"], True))
        note = backup(p)
        warnings = of.create_pptx(p, slides, title, P(template, True) if template else None)
        return (f"Wrote {path} with {len(slides)} slides{note}." +
                ("\nFix:\n- " + "\n- ".join(warnings) if warnings else "") +
                "\nLook at every slide with office_render.")

    def office_convert(path: str, to: str) -> str:
        p = P(path, True)
        dest = of.convert(p, to, p.parent)
        return f"Wrote {ws.rel(dest)}."

    def office_render(path: str, max_pages: int = 6) -> ToolResult:
        p = P(path, True)
        out = ws.root / ".yw" / "office-render" / p.stem
        if out.exists():
            shutil.rmtree(out)
        pages = of.render_pages(p, out, max_pages)
        imgs = [base64.b64encode(x.read_bytes()).decode() for x in pages[:max_pages]]
        return ToolResult("office_render", f"Rendered {len(pages)} page(s) of {path}. Look for overflowing or cut "
                                           "text, empty pages, broken tables and unreadable contrast.", images=imgs)

    def office_open(path: str) -> str:
        """Open the file in yOffice (if configured) or the computer's default office app."""
        p = P(path, True)
        app = getattr(session.config, "office_app", "") or ""
        if app:
            subprocess.Popen([app, str(p)])
            return f"Opened {path} in {Path(app).name}."
        system = platform.system()
        cmd = ["open", str(p)] if system == "Darwin" else ["cmd", "/c", "start", "", str(p)] if system == "Windows" \
            else ["xdg-open", str(p)]
        subprocess.Popen(cmd)
        return f"Opened {path} with the default app."

    tools = [
        Tool("office_read", "Read a Word, Excel or PowerPoint file (also .doc/.xls/.ppt/.odt): paragraphs with ids, "
             "tables, cell values and formulas, slides and notes.", obj({"path": S, "sheet": S, "cell_range": S},
                                                                        ["path"]), office_read, SAFE, "office"),
        Tool("office_docx_create", "Create a Word document from Markdown (headings, **bold**, lists, | tables |, "
             "---pagebreak---) or blocks [{type: heading|paragraph|bullet|numbered|table|image|page_break}]. "
             "template: a .docx whose styles to use.",
             obj({"path": S, "markdown": S, "blocks": OBJS, "title": S, "template": S, "overwrite": {"type": "boolean"}},
                 ["path"]), office_docx_create, WRITE, "office"),
        Tool("office_docx_edit", "Change text in a Word document without breaking its formatting (body, tables, "
             "headers, footers). edits: [{find, replace, all}] - find must be exact and unique unless all=true.",
             obj({"path": S, "edits": OBJS}, ["path", "edits"]), office_docx_edit, WRITE, "office"),
        Tool("office_xlsx_write", "Write cells (values or =formulas) to an Excel file; formulas are calculated and "
             "checked for errors. cells: {\"A1\": \"Ürün\", \"B5\": \"=SUM(B2:B4)\"}.",
             obj({"path": S, "cells": {"type": "object"}, "sheet": S, "widths": {"type": "object"},
                  "bold_rows": {"type": "array", "items": {"type": "integer"}}, "number_formats": {"type": "object"}},
                 ["path", "cells"]), office_xlsx_write, WRITE, "office"),
        Tool("office_pptx_create", "Create a PowerPoint deck (16:9). slides: [{layout: title|content|section|image, "
             "title, subtitle, bullets (indent sub-points with two spaces), image, notes}].",
             obj({"path": S, "slides": OBJS, "title": S, "template": S, "overwrite": {"type": "boolean"}},
                 ["path", "slides"]), office_pptx_create, WRITE, "office"),
        Tool("office_convert", "Convert office files: to pdf, docx, xlsx, pptx, odt, ods, odp, html, md "
             "(Markdown ↔ Word via pandoc).", obj({"path": S, "to": S}, ["path", "to"]), office_convert, WRITE,
             "office"),
        Tool("office_render", "Render pages/slides of an office file or PDF as images to check how they look.",
             obj({"path": S, "max_pages": {"type": "integer"}}, ["path"]), office_render, SAFE, "office"),
        Tool("office_open", "Open a file in yOffice (if set in settings) or the default office app, for the user.",
             obj({"path": S}, ["path"]), office_open, EXEC, "office"),
    ]
    for t in tools:
        reg.register(t)
