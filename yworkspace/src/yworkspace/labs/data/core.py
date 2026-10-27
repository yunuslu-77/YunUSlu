"""Data Lab core. Rule: the AI never invents a number. Every figure comes from code that actually ran, and is
written to a ledger (.yw/data/ledger.jsonl) so reports can be checked against it."""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

from ...core.errors import ToolError


def pd():
    try:
        import pandas
        return pandas
    except ImportError as e:
        raise ToolError("no_pandas", "The Data Lab needs pandas.", 'pip install "yworkspace[data]"') from e


# ----------------------------------------------------------------------------- loading
def load(path: Path, sheet: str | None = None, table: str | None = None):
    p = pd()
    path = Path(path)
    ext = path.suffix.lower()
    if not path.exists():
        raise ToolError("not_found", f"{path.name} does not exist.")
    try:
        if ext in (".csv", ".txt"):
            raw = path.read_bytes()[:20000].decode("utf-8", "replace")
            sep = max([",", ";", "\t", "|"], key=raw.count)
            enc = "utf-8-sig"
            try:
                path.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                enc = "cp1254"  # Turkish Excel exports
            # Turkish/European CSVs use ; with decimal commas.
            return p.read_csv(path, sep=sep, encoding=enc, decimal="," if sep == ";" else ".")
        if ext == ".tsv":
            return p.read_csv(path, sep="\t")
        if ext in (".xlsx", ".xlsm", ".xls"):
            return p.read_excel(path, sheet_name=sheet or 0)
        if ext == ".json":
            data = json.loads(path.read_text("utf-8"))
            if isinstance(data, dict):
                key = next((k for k, v in data.items() if isinstance(v, list)), None)
                data = data[key] if key else [data]
            return p.json_normalize(data)
        if ext == ".jsonl":
            return p.read_json(path, lines=True)
        if ext == ".parquet":
            return p.read_parquet(path)
        if ext in (".db", ".sqlite", ".sqlite3"):
            import sqlite3
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
                if not tables:
                    raise ToolError("empty_db", "The database has no tables.")
                t = table or tables[0]
                if t not in tables:
                    raise ToolError("no_table", f"No table {t}.", f"Tables: {', '.join(tables)}")
                return p.read_sql_query(f'select * from "{t}"', con)
            finally:
                con.close()
    except ToolError:
        raise
    except Exception as e:  # noqa: BLE001 - parsers raise many kinds of errors
        raise ToolError("bad_data", f"{path.name} could not be read: {e}") from e
    raise ToolError("bad_format", f"Unsupported file type {ext}.", "Use csv, tsv, xlsx, json, jsonl, parquet or sqlite.")


def profile(df) -> str:
    rows = [f"{len(df)} rows × {len(df.columns)} columns; {int(df.duplicated().sum())} duplicate rows", "",
            "| column | type | missing | unique | example / range |", "|---|---|---|---|---|"]
    for c in df.columns:
        s = df[c]
        miss = int(s.isna().sum())
        kind = str(s.dtype)
        if s.dtype.kind in "if" and s.notna().any():
            ex = f"{_fmt(s.min())} … {_fmt(s.max())} (mean {_fmt(s.mean())})"
        else:
            vals = s.dropna().astype(str).unique()[:3]
            ex = ", ".join(v[:25] for v in vals)
        rows.append(f"| {c} | {kind} | {miss} ({miss / max(1, len(df)) * 100:.0f}%) | {s.nunique()} | {ex} |")
    numeric_text = [c for c in df.columns if _is_text(df[c]) and
                    df[c].dropna().astype(str).str.fullmatch(r"-?[\d.,]+").mean() > 0.8]
    if numeric_text:
        rows.append(f"\nColumns that look numeric but are text: {', '.join(map(str, numeric_text))} (use to_number).")
    return "\n".join(rows)


def _is_text(s) -> bool:
    return pd().api.types.is_string_dtype(s) or s.dtype == object


def _fmt(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if math.isnan(f):
        return "NaN"
    return f"{f:,.0f}" if abs(f) >= 1000 or f == int(f) else f"{f:,.4g}"


# ----------------------------------------------------------------------------- cleaning
def clean(df, ops: list[dict]):
    p = pd()
    log = []
    for op in ops:
        kind = op.get("op")
        before = len(df)
        col = op.get("column")
        if col is not None and col not in df.columns:
            raise ToolError("no_column", f"No column {col!r}.", f"Columns: {', '.join(map(str, df.columns))}")
        if kind == "drop_duplicates":
            df = df.drop_duplicates(subset=op.get("columns") or None)
            log.append(f"drop_duplicates: removed {before - len(df)} rows")
        elif kind == "strip":
            cols = [col] if col else [c for c in df.columns if _is_text(df[c])]
            for c in cols:
                df[c] = df[c].astype("string").str.strip().astype(object).where(df[c].notna())
            log.append(f"strip: trimmed spaces in {len(cols)} columns")
        elif kind == "drop_missing":
            df = df.dropna(subset=op.get("columns") or ([col] if col else None))
            log.append(f"drop_missing: removed {before - len(df)} rows")
        elif kind == "fill_missing":
            n = int(df[col].isna().sum())
            how = op.get("value", "median")
            value = df[col].median() if how == "median" else df[col].mean() if how == "mean" else \
                df[col].mode().iloc[0] if how == "mode" else how
            df[col] = df[col].fillna(value)
            log.append(f"fill_missing {col}: filled {n} cells with {how} ({_fmt(value)})")
        elif kind == "to_number":
            s = df[col].astype(str).str.replace(r"[^\d,.\-]", "", regex=True)
            if op.get("decimal", ",") == ",":
                s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
            new = p.to_numeric(s, errors="coerce")
            bad = int((new.isna() & df[col].notna()).sum())
            df[col] = new
            log.append(f"to_number {col}: converted; {bad} values could not be read and became empty")
        elif kind == "parse_dates":
            new = p.to_datetime(df[col], errors="coerce", dayfirst=op.get("dayfirst", True))
            bad = int((new.isna() & df[col].notna()).sum())
            df[col] = new
            log.append(f"parse_dates {col}: {bad} values could not be read")
        elif kind == "rename":
            df = df.rename(columns={op["from"]: op["to"]})
            log.append(f"rename {op['from']} → {op['to']}")
        elif kind == "filter":
            df = df[_mask(df, op)]
            log.append(f"filter {col} {op.get('cmp', '==')} {op.get('value')!r}: removed {before - len(df)} rows")
        elif kind == "drop_columns":
            df = df.drop(columns=op["columns"])
            log.append(f"drop_columns: {', '.join(op['columns'])}")
        elif kind == "lowercase":
            df[col] = df[col].astype("string").str.lower().astype(object).where(df[col].notna())
            log.append(f"lowercase {col}")
        else:
            raise ToolError("bad_op", f"Unknown cleaning operation {kind!r}.",
                            "Use drop_duplicates, strip, drop_missing, fill_missing, to_number, parse_dates, rename, "
                            "filter, drop_columns, lowercase.")
    return df, log


def _mask(df, f: dict):
    col, cmp, value = f["column"], f.get("cmp", "=="), f.get("value")
    s = df[col]
    if cmp == "==":
        return s == value
    if cmp == "!=":
        return s != value
    if cmp in (">", ">=", "<", "<="):
        return {">": s > value, ">=": s >= value, "<": s < value, "<=": s <= value}[cmp]
    if cmp == "in":
        return s.isin(value)
    if cmp == "contains":
        return s.astype(str).str.contains(str(value), case=False, na=False)
    if cmp == "missing":
        return s.isna()
    if cmp == "present":
        return s.notna()
    raise ToolError("bad_filter", f"Unknown comparison {cmp}.", "Use == != > >= < <= in contains missing present.")


def query(df, group_by: list[str] | None, metrics: list[dict], filters: list[dict] | None = None,
          sort: str | None = None, descending: bool = True, limit: int = 50, period: str | None = None,
          date_column: str | None = None):
    p = pd()
    for f in filters or []:
        df = df[_mask(df, f)]
    keys = list(group_by or [])
    if period and date_column:
        d = p.to_datetime(df[date_column], errors="coerce")
        df = df.assign(**{period: d.dt.to_period({"day": "D", "week": "W", "month": "M", "quarter": "Q",
                                                   "year": "Y"}[period]).astype(str)})
        keys.append(period)
    aggs = {}
    for m in metrics:
        col, agg = m.get("column"), m.get("agg", "sum")
        name = m.get("as") or (f"{agg}_{col}" if col else agg)
        if agg == "count":
            aggs[name] = (col or df.columns[0], "count")
        elif agg in ("sum", "mean", "median", "min", "max", "std", "nunique"):
            aggs[name] = (col, agg)
        else:
            raise ToolError("bad_agg", f"Unknown aggregation {agg}.", "Use count sum mean median min max std nunique.")
    if keys:
        out = df.groupby(keys, dropna=False).agg(**aggs).reset_index()
    else:
        out = p.DataFrame({k: [getattr(df[c], a)()] for k, (c, a) in aggs.items()})
    if sort:
        out = out.sort_values(sort, ascending=not descending)
    elif period:
        out = out.sort_values(period)
    return out.head(limit)


def table_md(df, limit: int = 50) -> str:
    cols = [str(c) for c in df.columns]
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.head(limit).iterrows():
        rows.append("| " + " | ".join(_fmt(v) if isinstance(v, (int, float)) else str(v) for v in r.values) + " |")
    if len(df) > limit:
        rows.append(f"… {len(df) - limit} more rows")
    return "\n".join(rows)


# ----------------------------------------------------------------------------- ledger
NUM_RX = re.compile(r"(?<![\w.])-?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?(?![\w])|(?<![\w.])-?\d+(?:[.,]\d+)?(?![\w])")


def parse_number(tok: str) -> float | None:
    t = tok.strip()
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", t):
        t = t.replace(",", "")
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def numbers_in(text: str) -> list[float]:
    out = []
    for tok in NUM_RX.findall(text):
        v = parse_number(tok)
        if v is not None and not math.isnan(v):
            out.append(v)
    return out


class Ledger:
    def __init__(self, root: Path):
        self.path = Path(root) / ".yw" / "data" / "ledger.jsonl"

    def add(self, tool: str, how: str, result: str, values: list[float] | None = None) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entries = self.entries()
        eid = f"R{len(entries) + 1}"
        vals = values if values is not None else numbers_in(result)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": eid, "time": time.time(), "tool": tool, "how": how[:4000],
                                "values": vals[:5000]}, ensure_ascii=False) + "\n")
        return eid

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text("utf-8").splitlines() if x.strip()]

    def values(self) -> list[float]:
        return [v for e in self.entries() for v in e["values"]]


def backed(value: float, decimals: int, known: list[float]) -> bool:
    """A reported number is backed if some computed value rounds to it (also as a percentage or in thousands)."""
    if decimals == 0 and abs(value) <= 10:  # small counts, list numbers, "3 steps" - not checked
        return True
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    for k in known:
        for cand in (k, k * 100, k / 1000, k / 1_000_000):
            if abs(cand - value) <= tol:
                return True
    return False


def unbacked_numbers(text: str, known: list[float]) -> list[str]:
    text = re.sub(r"```.*?```", "", text, flags=re.S)  # code is evidence, not claims
    text = re.sub(r"\b(19|20)\d\d-\d\d(-\d\d)?\b", "", text)  # dates
    text = re.sub(r"\b(?:Q[1-4]|R\d+)\b", "", text)  # quarters and ledger ids
    bad = []
    for tok in NUM_RX.findall(text):
        v = parse_number(tok)
        if v is None:
            continue
        if re.fullmatch(r"(19|20)\d\d", tok):  # years
            continue
        dec = len(re.split(r"[.,]", tok)[-1]) if re.search(r"[.,]\d{1,2}$", tok) and \
            not re.fullmatch(r"-?\d{1,3}([.,]\d{3})+", tok) else 0
        if not backed(v, dec, known):
            bad.append(tok)
    return bad


# ----------------------------------------------------------------------------- simple machine learning
def train_model(df, target: str, features: list[str] | None, kind: str = "auto", seed: int = 7) -> str:
    """Honest small models with numpy: linear regression or logistic regression, compared to a baseline."""
    import numpy as np
    p = pd()
    if target not in df.columns:
        raise ToolError("no_column", f"No column {target!r}.")
    features = features or [c for c in df.columns if c != target]
    data = df[[*features, target]].dropna()
    if len(data) < 20:
        raise ToolError("too_small", f"Only {len(data)} complete rows: too few to train a model honestly.")
    X = p.get_dummies(data[features], drop_first=True, dtype=float)
    y_raw = data[target]
    if kind == "auto":
        kind = "classification" if y_raw.dtype == object or y_raw.nunique() <= 10 else "regression"
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(data))
    cut = int(len(data) * 0.8)
    tr, te = idx[:cut], idx[cut:]
    Xv = X.to_numpy(float)
    mu, sd = Xv[tr].mean(0), Xv[tr].std(0) + 1e-9
    Xs = np.hstack([np.ones((len(Xv), 1)), (Xv - mu) / sd])
    lines = [f"Model: {kind}; {len(tr)} training rows, {len(te)} test rows (random 80/20 split, seed {seed})."]
    if kind == "regression":
        y = y_raw.to_numpy(float)
        w, *_ = np.linalg.lstsq(Xs[tr], y[tr], rcond=None)
        pred = Xs[te] @ w
        base = np.full(len(te), y[tr].mean())

        def r2(yhat):
            ss = ((y[te] - y[te].mean()) ** 2).sum()
            return 1 - ((y[te] - yhat) ** 2).sum() / ss if ss else 0.0
        mae, bmae = np.abs(y[te] - pred).mean(), np.abs(y[te] - base).mean()
        lines += [f"Test R²: {r2(pred):.3f} (baseline that always predicts the mean: {r2(base):.3f})",
                  f"Test mean absolute error: {mae:.4g} (baseline {bmae:.4g})"]
        coefs = sorted(zip(X.columns, w[1:], strict=True), key=lambda x: -abs(x[1]))[:8]
        lines.append("Strongest effects (per 1 standard deviation): " +
                     ", ".join(f"{c} {v:+.3g}" for c, v in coefs))
        good = r2(pred) > 0.3 and mae < bmae * 0.9
    else:
        classes = sorted(y_raw.astype(str).unique())
        if len(classes) < 2:
            raise ToolError("one_class", "The target has only one value.")
        Y = np.array([[1.0 if v == c else 0.0 for c in classes] for v in y_raw.astype(str)])
        W = np.zeros((Xs.shape[1], len(classes)))
        for _ in range(800):
            z = Xs[tr] @ W
            z -= z.max(1, keepdims=True)
            P = np.exp(z)
            P /= P.sum(1, keepdims=True)
            W -= 0.3 * (Xs[tr].T @ (P - Y[tr]) / len(tr) + 1e-3 * W)
        pred = (Xs[te] @ W).argmax(1)
        truth = Y[te].argmax(1)
        acc = (pred == truth).mean()
        majority = Y[tr].sum(0).argmax()
        bacc = (truth == majority).mean()
        lines += [f"Test accuracy: {acc:.3f} (baseline that always predicts '{classes[majority]}': {bacc:.3f})"]
        for i, c in enumerate(classes[:10]):
            tp = int(((pred == i) & (truth == i)).sum())
            prec = tp / max(1, int((pred == i).sum()))
            rec = tp / max(1, int((truth == i).sum()))
            lines.append(f"  {c}: precision {prec:.2f}, recall {rec:.2f}")
        good = acc > bacc + 0.05
    lines.append("Verdict: " + ("useful - clearly better than the baseline." if good else
                                "NOT reliable - barely better than guessing. Do not make decisions with it; get more "
                                "or better data."))
    if len(te) < 50:
        lines.append(f"Caution: the test set has only {len(te)} rows, so these scores are rough.")
    return "\n".join(lines)
