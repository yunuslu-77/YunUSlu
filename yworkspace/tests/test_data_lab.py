import json

import pytest

pytest.importorskip("pandas")

from yworkspace.app import build_session  # noqa: E402
from yworkspace.config import Config  # noqa: E402
from yworkspace.labs.data import core  # noqa: E402

CSV = ("tarih;şube;ürün;adet;tutar\n"
       "05.01.2026;Kadıköy;Kahve;3;135,50\n"
       "05.01.2026;Kadıköy;Kahve;3;135,50\n"
       "12.01.2026; Beşiktaş ;Çay;10;150,00\n"
       "03.02.2026;Kadıköy;Kek;2;\n"
       "15.02.2026;Beşiktaş;Kahve;5;225,00\n"
       "20.03.2026;Kadıköy;Çay;8;120,00\n")


def session(tmp_path, monkeypatch, engine=False):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    sess = build_session(tmp_path / "veri", Config(sandbox="local"), with_engine=engine)
    (sess.workspace.root / "satis.csv").write_text(CSV, encoding="cp1254")
    return sess


def test_turkish_csv_clean_query_report(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch, engine=True)
    call = sess.registry.call
    prof = call("data_load", {"path": "satis.csv"}).text
    assert "6 rows × 5 columns; 1 duplicate rows" in prof and "tutar" in prof
    cl = call("data_clean", {"path": "satis.csv", "out": "temiz.csv", "ops": [
        {"op": "drop_duplicates"}, {"op": "strip"}, {"op": "fill_missing", "column": "tutar", "value": 0},
        {"op": "parse_dates", "column": "tarih"}]}).text
    assert "removed 1 rows" in cl and "filled 1 cells" in cl and "Rows: 6 → 5" in cl
    q = call("data_query", {"path": "temiz.csv", "group_by": ["şube"],
                            "metrics": [{"column": "tutar", "agg": "sum", "as": "ciro"},
                                        {"column": "adet", "agg": "sum"}], "sort": "ciro"}).text
    assert "| Beşiktaş | 375 | 15 |" in q and "| Kadıköy | 255.5 | 13 |" in q, q
    m = call("data_query", {"path": "temiz.csv", "metrics": [{"column": "tutar", "agg": "sum"}], "period": "month",
                            "date_column": "tarih"}).text
    assert "2026-01" in m and "2026-03" in m
    ok = call("data_report", {"name": "ocak", "title": "Satış raporu", "markdown":
                              "Beşiktaş 375 TL ciro yaptı, Kadıköy 255,5 TL. Toplam 15 + 13 adet. Kayıt: R3."}).text
    assert "Every number" in ok, ok
    bad = call("data_report", {"name": "uydurma", "title": "Rapor", "markdown": "Ciro %37 arttı, 1.250 TL oldu."}).text
    assert "do not come from any computation: 37, 1.250" in bad, bad
    gate = next(g for g in sess.engine.extra_gates if g(sess.engine).name == "report numbers come from computations")
    monkeypatch.setattr(sess.engine, "changed_files", lambda: ["reports/ocak.md", "reports/uydurma.md"])
    res = gate(sess.engine)
    assert not res.passed and "uydurma.md" in res.detail and "ocak.md" not in res.detail


def test_python_chart_dashboard_notebook(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch)
    call = sess.registry.call
    root = sess.workspace.root
    py = call("data_python", {"code": "import pandas as pd\nprint(round(17 / 3, 4))"}).text
    assert "5.6667" in py and (root / ".yw/data/run_001.py").exists()
    assert core.Ledger(root).entries()[-1]["values"] == [5.6667]
    ch = call("data_chart", {"path": "satis.csv", "x": "şube", "y_column": "adet", "title": "Adet"}).text
    assert "reports/charts/adet.svg" in ch and (root / "reports/charts/adet.svg").read_text(encoding="utf-8").count("<rect") == 4
    d = call("data_dashboard", {"path": "satis.csv", "title": "Panel", "kpis": [
        {"label": "Toplam adet", "column": "adet", "agg": "sum"},
        {"label": "Kahve satışı", "column": "adet", "agg": "sum",
         "filters": [{"column": "ürün", "cmp": "==", "value": "Kahve"}]}],
        "charts": [{"x": "ürün", "y": "adet", "title": "Ürünler"}]}).text
    assert "2 KPIs and 1 charts" in d
    page = (root / "reports/dashboard.html").read_text(encoding="utf-8")
    assert ">31<" in page and ">11<" in page
    nb = call("data_notebook", {"out": "analiz.ipynb", "cells": [
        {"type": "markdown", "source": "# Analiz"}, {"source": "x = 2 + 2"}, {"source": "print('sonuç', x * 10)"}]}).text
    assert "ran top to bottom" in nb and "sonuç 40" in nb
    data = json.loads((root / "analiz.ipynb").read_text(encoding="utf-8"))
    assert data["nbformat"] == 4 and data["cells"][0]["cell_type"] == "markdown"
    broken = call("data_notebook", {"out": "bozuk.ipynb", "cells": [{"source": "1/0"}]}).text
    assert "FAILED" in broken


def test_models_are_honest():
    import numpy as np
    pd = core.pd()
    rng = np.random.default_rng(1)
    x = rng.uniform(0, 10, 200)
    df = pd.DataFrame({"x": x, "noise": rng.normal(size=200), "y": 3 * x + rng.normal(size=200)})
    good = core.train_model(df, "y", ["x"], "regression")
    assert "Verdict: useful" in good and "Test R²: 0.9" in good
    df2 = pd.DataFrame({"a": rng.normal(size=200), "label": rng.choice(["evet", "hayır"], 200)})
    bad = core.train_model(df2, "label", ["a"])
    assert "classification" in bad and "NOT reliable" in bad
    sep = pd.DataFrame({"a": np.r_[rng.normal(-3, 1, 100), rng.normal(3, 1, 100)], "label": ["x"] * 100 + ["y"] * 100})
    assert "Verdict: useful" in core.train_model(sep, "label", ["a"])


def test_number_parsing():
    assert core.parse_number("1.250") == 1250 and core.parse_number("1,250.5") == 1250.5
    assert core.parse_number("255,5") == 255.5
    assert core.unbacked_numbers("Toplam %45,3 ve 2026-01-05 tarihinde 2025 yılında 3 adım", [0.4531]) == []
    assert core.unbacked_numbers("12,4 milyon", [12_400_000]) == []
