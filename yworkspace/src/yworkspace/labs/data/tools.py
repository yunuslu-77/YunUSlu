"""Data Lab tools. Every number shown to the user is computed here (or by code run in the sandbox) and logged."""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from ...core.errors import ToolError
from ...engine.engine import GateResult
from ...extensions import register, register_gate
from ...tools.registry import EXEC, SAFE, WRITE, Tool, obj
from . import core

S = {"type": "string"}
STRS = {"type": "array", "items": S}
OBJS = {"type": "array", "items": {"type": "object"}}
SOURCE = {"path": S, "sheet": S, "table": S}
REPORT_DIRS = ("reports", "report", "raporlar", "analysis")


@register
def install(session) -> None:
    reg, ws = session.registry, session.workspace
    ledger = core.Ledger(ws.root)

    def frame(path: str, sheet: str = "", table: str = ""):
        return core.load(ws.resolve(path), sheet or None, table or None)

    def write(path: str, content: str) -> None:
        full = ws.root / path
        if full.exists():
            if full.read_text("utf-8", "replace") == content:
                return
            ws.read(path)
        ws.create(path, content, overwrite=full.exists())

    def data_load(path: str, sheet: str = "", table: str = "") -> str:
        df = frame(path, sheet, table)
        text = core.profile(df)
        rid = ledger.add("data_load", f"load {path}", text, [len(df), len(df.columns)] + core.numbers_in(text))
        head = core.table_md(df, 8)
        return f"[{rid}] {path}\n{text}\n\nFirst rows:\n{head}"

    def data_clean(path: str, ops: list[dict], out: str = "", sheet: str = "") -> str:
        df = frame(path, sheet)
        before = len(df)
        df, log = core.clean(df, ops)
        target = out or re.sub(r"(\.\w+)$", r".clean.csv", path)
        dest = ws.resolve(target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        csv_text = df.to_csv(index=False)
        write(ws.rel(dest), csv_text)
        text = "\n".join(f"- {x}" for x in log) + f"\nRows: {before} → {len(df)}. Wrote {target}."
        rid = ledger.add("data_clean", json.dumps(ops, ensure_ascii=False), text, [before, len(df)] +
                         core.numbers_in(text))
        return f"[{rid}] Cleaning report (keep it in the final report):\n{text}"

    def data_query(path: str, metrics: list[dict], group_by: list[str] | None = None, filters: list[dict] | None = None,
                   sort: str = "", descending: bool = True, limit: int = 50, period: str = "", date_column: str = "",
                   sheet: str = "") -> str:
        df = frame(path, sheet)
        for c in [*(group_by or []), *[m.get("column") for m in metrics if m.get("column")], date_column or None]:
            if c and c not in df.columns:
                raise ToolError("no_column", f"No column {c!r}.", f"Columns: {', '.join(map(str, df.columns))}")
        res = core.query(df, group_by, metrics, filters, sort or None, descending, limit, period or None,
                         date_column or None)
        values = [float(v) for v in res.select_dtypes("number").to_numpy().ravel().tolist()]
        how = json.dumps({"path": path, "group_by": group_by, "metrics": metrics, "filters": filters,
                          "period": period}, ensure_ascii=False)
        rid = ledger.add("data_query", how, "", values)
        return f"[{rid}] {len(res)} rows\n{core.table_md(res, limit)}"

    def data_python(code: str, timeout: int = 600) -> str:
        """Free analysis in the sandbox; its printed output is the evidence."""
        d = ws.root / ".yw" / "data"
        d.mkdir(parents=True, exist_ok=True)
        n = len(list(d.glob("run_*.py"))) + 1
        script = d / f"run_{n:03d}.py"
        script.write_text(code, "utf-8")
        r = session.sandbox.run(f"python .yw/data/run_{n:03d}.py", timeout=timeout)
        rid = ledger.add("data_python", code, r.output if r.exit_code == 0 else "")
        if r.exit_code != 0:
            return f"FAILED (nothing recorded):\n{r.to_text()[-5000:]}"
        return f"[{rid}] (code saved as .yw/data/run_{n:03d}.py)\n{r.output[-12000:]}"

    def chart_svg(df, kind: str, x: str, y: str, title: str, unit: str) -> str:
        from ...studio.render import svg_chart
        return svg_chart(kind, [str(v) for v in df[x]], [float(v) for v in df[y]], title, unit=unit)

    def data_chart(path: str, x: str, y_column: str, agg: str = "sum", out: str = "", kind: str = "bar",
                   title: str = "", unit: str = "", period: str = "", limit: int = 24, sheet: str = "") -> str:
        df = frame(path, sheet)
        keys = [] if period else [x]
        res = core.query(df, keys, [{"column": y_column, "agg": agg, "as": "value"}], None,
                         None if period else "value", True, limit, period or None, x if period else None)
        xcol = period or x
        svg = chart_svg(res, kind, xcol, "value", title, unit)
        target = out or f"reports/charts/{re.sub(r'[^a-z0-9]+', '-', (title or y_column).lower()).strip('-')}"
        svg_path = ws.resolve(target).with_suffix(".svg")
        write(ws.rel(svg_path), svg)
        rid = ledger.add("data_chart", f"{agg}({y_column}) by {xcol} from {path}", "",
                         [float(v) for v in res["value"]])
        png = ""
        try:
            from ...studio.render import html_to_png
            p = html_to_png(svg, svg_path.with_suffix(".png"), 960, 540)
            png = f" and {ws.rel(p)}"
        except ToolError:
            pass
        return f"[{rid}] Wrote {ws.rel(svg_path)}{png}.\n{core.table_md(res, limit)}"

    def data_dashboard(path: str, title: str, kpis: list[dict], charts: list[dict] | None = None,
                       out: str = "reports/dashboard.html", sheet: str = "") -> str:
        df = frame(path, sheet)
        tiles, figs, values = [], [], [float(len(df))]
        for k in kpis:
            sub = df
            for f in k.get("filters", []):
                sub = sub[core._mask(sub, f)]
            res = core.query(sub, None, [{"column": k.get("column"), "agg": k.get("agg", "sum"), "as": "v"}])
            v = float(res["v"].iloc[0])
            values.append(v)
            tiles.append(f'<div class="kpi"><div class="v">{html.escape(k.get("prefix", ""))}{core._fmt(v)}'
                         f'{html.escape(k.get("suffix", ""))}</div><div class="l">{html.escape(k["label"])}</div></div>')
        for c in charts or []:
            period = c.get("period")
            res = core.query(df, [] if period else [c["x"]], [{"column": c["y"], "agg": c.get("agg", "sum"),
                                                                "as": "value"}], c.get("filters"),
                             None if period else "value", True, c.get("limit", 12), period, c["x"] if period else None)
            values += [float(v) for v in res["value"]]
            figs.append(f'<figure>{chart_svg(res, c.get("kind", "bar"), period or c["x"], "value", c.get("title", ""), c.get("unit", ""))}'
                        "</figure>")
        page = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
                f'initial-scale=1"><title>{html.escape(title)}</title><style>body{{font-family:system-ui,sans-serif;'
                "margin:0;background:#f4f6fa;color:#14202e}main{max-width:1100px;margin:auto;padding:24px}"
                ".kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}.kpi{background:"
                "#fff;border-radius:12px;padding:18px}.v{font-size:30px;font-weight:800}.l{color:#5d6f86}figure{"
                "background:#fff;border-radius:12px;margin:16px 0;padding:8px;overflow:auto}svg{max-width:100%;height:"
                "auto}</style></head>"
                f'<body><main><h1>{html.escape(title)}</h1><div class="kpis">{"".join(tiles)}</div>{"".join(figs)}'
                f'<p style="color:#6a7a8e;font-size:13px">Source: {html.escape(path)} · {len(df)} rows · every '
                "number computed by yWorkspace Data Lab</p></main></body></html>")
        write(out, page)
        rid = ledger.add("data_dashboard", json.dumps({"kpis": kpis, "charts": charts}, ensure_ascii=False), "",
                         values)
        return f"[{rid}] Wrote {out} with {len(tiles)} KPIs and {len(figs)} charts. Open it with screen_open to check."

    def data_model(path: str, target: str, features: list[str] | None = None, kind: str = "auto",
                   sheet: str = "") -> str:
        text = core.train_model(frame(path, sheet), target, features, kind)
        rid = ledger.add("data_model", f"{kind} model of {target} from {path}", text)
        return f"[{rid}] {text}"

    def data_report(name: str, title: str, markdown: str, format: str = "md") -> str:
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise ToolError("bad_name", "name: lowercase letters, digits and - only.")
        bad = core.unbacked_numbers(markdown, ledger.values())
        body = f"# {title}\n\n{markdown.strip()}\n"
        if format == "html":
            from ...launch.pages import md
            content = (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
                       "<style>body{font-family:system-ui,sans-serif;max-width:860px;margin:auto;padding:24px;"
                       "line-height:1.6}table{border-collapse:collapse}td,th{border:1px solid #ccd;padding:4px 8px}"
                       f"</style></head><body>{md(body)}</body></html>")
            out = f"reports/{name}.html"
        else:
            content, out = body, f"reports/{name}.md"
        write(out, content)
        if bad:
            return (f"Wrote {out}, BUT these numbers do not come from any computation: {', '.join(bad[:20])}.\n"
                    "Compute them (data_query / data_python) or remove them. The done gate will not pass otherwise.")
        return f"Wrote {out}. Every number in it matches a computed result."

    def data_notebook(cells: list[dict], out: str = "analysis.ipynb", execute: bool = True) -> str:
        nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"kernelspec": {"name": "python3",
                                                                               "display_name": "Python 3",
                                                                               "language": "python"}},
              "cells": []}
        for i, c in enumerate(cells):
            kind = c.get("type", "code")
            src = c.get("source", "")
            cell = {"cell_type": "markdown" if kind == "markdown" else "code", "id": f"c{i}", "metadata": {},
                    "source": src.splitlines(keepends=True)}
            if cell["cell_type"] == "code":
                cell.update(outputs=[], execution_count=None)
            nb["cells"].append(cell)
        write(out, json.dumps(nb, indent=1, ensure_ascii=False))
        if not execute:
            return f"Wrote {out} ({len(cells)} cells)."
        code = "\n\n".join(c.get("source", "") for c in cells if c.get("type", "code") == "code")
        r = session.sandbox.run(
            f"jupyter nbconvert --to notebook --execute --inplace {out}" if shutil.which("jupyter") else
            "python - <<'YW_NB'\n" + code + "\nYW_NB", timeout=900)
        if r.exit_code != 0:
            return f"Wrote {out}, but running it FAILED:\n{r.to_text()[-4000:]}"
        rid = ledger.add("data_notebook", code, r.output)
        return f"[{rid}] Wrote {out}; all cells ran top to bottom without errors.\n{r.output[-4000:]}"

    src = lambda extra, req: obj({**SOURCE, **extra}, ["path", *req])  # noqa: E731
    tools = [
        Tool("data_load", "Open a data file (CSV incl. Turkish Excel exports, TSV, Excel, JSON, JSONL, Parquet, "
             "SQLite) and profile it: rows, columns, types, missing values, ranges.", src({}, []), data_load, SAFE,
             "data"),
        Tool("data_clean", "Clean data and report every change. ops: drop_duplicates, strip, drop_missing, "
             "fill_missing{column,value:median|mean|mode|x}, to_number{column,decimal}, parse_dates, rename{from,to}, "
             "filter{column,cmp,value}, drop_columns{columns}, lowercase.",
             src({"ops": OBJS, "out": S}, ["ops"]), data_clean, WRITE, "data"),
        Tool("data_query", "Compute numbers: metrics [{column, agg: count|sum|mean|median|min|max|std|nunique, as}] "
             "grouped by columns and/or a time period (day|week|month|quarter|year of date_column), with filters "
             "[{column, cmp, value}].", src({"metrics": OBJS, "group_by": STRS, "filters": OBJS, "sort": S,
                                             "descending": {"type": "boolean"}, "limit": {"type": "integer"},
                                             "period": S, "date_column": S}, ["metrics"]), data_query, SAFE, "data"),
        Tool("data_python", "Run analysis code (pandas etc.) in the sandbox; print the results. Use for anything "
             "data_query cannot do.", obj({"code": S, "timeout": {"type": "integer"}}, ["code"]), data_python, EXEC,
             "data"),
        Tool("data_chart", "Chart of agg(y_column) by x (or by period of date column x): bar or line, SVG + PNG.",
             src({"x": S, "y_column": S, "agg": S, "out": S, "kind": S, "title": S, "unit": S, "period": S,
                  "limit": {"type": "integer"}}, ["x", "y_column"]), data_chart, WRITE, "data"),
        Tool("data_dashboard", "One-page HTML dashboard: KPI tiles [{label, column, agg, filters, prefix, suffix}] "
             "and charts [{x, y, agg, kind, title, period}], all computed.",
             src({"title": S, "kpis": OBJS, "charts": OBJS, "out": S}, ["title", "kpis"]), data_dashboard, WRITE,
             "data"),
        Tool("data_model", "Train a simple prediction model (regression or classification) and compare it with a "
             "baseline; says plainly if it is not reliable.", src({"target": S, "features": STRS, "kind": S},
                                                                  ["target"]), data_model, SAFE, "data"),
        Tool("data_report", "Write a report (Markdown or HTML) in plain language. Every number in it is checked "
             "against computed results.", obj({"name": S, "title": S, "markdown": S,
                                               "format": {"type": "string", "enum": ["md", "html"]}},
                                              ["name", "title", "markdown"]), data_report, WRITE, "data"),
        Tool("data_notebook", "Write a Jupyter notebook from cells [{type: code|markdown, source}] and run it top to "
             "bottom.", obj({"cells": OBJS, "out": S, "execute": {"type": "boolean"}}, ["cells"]), data_notebook,
             EXEC, "data"),
    ]
    for t in tools:
        reg.register(t)


@register_gate
def install_gate(session) -> None:
    def gate(engine) -> GateResult:
        ledger = core.Ledger(engine.root)
        if not ledger.path.exists():
            return GateResult("report numbers come from computations", True, "Data Lab not used.")
        known = ledger.values()
        problems = []
        for f in engine.changed_files():
            p = Path(f)
            if p.parts and p.parts[0] in REPORT_DIRS and p.suffix.lower() in (".md", ".html", ".txt"):
                text = (engine.root / f).read_text("utf-8", "replace")
                if p.suffix.lower() == ".html":
                    text = re.sub(r"<style.*?</style>|<script.*?</script>|<svg.*?</svg>|<[^>]+>", " ", text, flags=re.S)
                bad = core.unbacked_numbers(text, known)
                if bad:
                    problems.append(f"{f}: numbers without a computation: {', '.join(bad[:15])}")
        return GateResult("report numbers come from computations", not problems, "\n".join(problems))
    session.engine.extra_gates.append(gate)
