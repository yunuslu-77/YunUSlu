from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from bot.budget import BudgetExceeded, price_of
from bot.timeparse import WhenError, next_run, parse_when

TZ = ZoneInfo("Europe/Istanbul")
NOW = datetime(2026, 11, 15, 10, 0, tzinfo=TZ)  # Pazar


@pytest.mark.parametrize("text,cron", [
    ("08:00", "0 8 * * *"),
    ("her gün 08:00", "0 8 * * *"),
    ("hafta içi 08:30", "30 8 * * 1-5"),
    ("hafta sonu 10:00", "0 10 * * 0,6"),
    ("pzt,çar,cum 07:15", "15 7 * * 1,3,5"),
    ("her pazartesi 09:00", "0 9 * * 1"),
    ("cumaları 18:00", "0 18 * * 5"),
    ("0 8 * * *", "0 8 * * *"),
])
def test_cron(text, cron):
    assert parse_when(text, TZ, NOW) == {"cron": cron}


def test_relative_and_absolute():
    assert parse_when("+30dk", TZ, NOW)["run_at"] == NOW.timestamp() + 1800
    assert parse_when("2 saat sonra", TZ, NOW)["run_at"] == NOW.timestamp() + 7200
    assert parse_when("+1gün", TZ, NOW)["run_at"] == NOW.timestamp() + 86400
    assert parse_when("yarın 09:00", TZ, NOW)["run_at"] == datetime(2026, 11, 16, 9, 0, tzinfo=TZ).timestamp()
    assert parse_when("bugün 18:00", TZ, NOW)["run_at"] == datetime(2026, 11, 15, 18, 0, tzinfo=TZ).timestamp()
    assert parse_when("2026-12-01 14:30", TZ, NOW)["run_at"] == datetime(2026, 12, 1, 14, 30, tzinfo=TZ).timestamp()
    assert parse_when("01.12.2026 14:30", TZ, NOW)["run_at"] == datetime(2026, 12, 1, 14, 30, tzinfo=TZ).timestamp()


def test_errors():
    for bad in ("bugün 09:00", "2020-01-01 10:00", "merhaba", "25:00"):
        with pytest.raises(WhenError):
            parse_when(bad, TZ, NOW)


def test_next_run():
    assert next_run("0 8 * * *", TZ, NOW) == datetime(2026, 11, 16, 8, 0, tzinfo=TZ).timestamp()


def test_budget(app):
    b = app.budget
    cost = b.record("gemini-3.5-flash-lite", 1_000_000, 100_000)
    assert cost == pytest.approx(0.30 + 0.25)
    cached = b.record("gemini-3.5-flash-lite", 1_000_000, 0, cached_tokens=1_000_000)
    assert cached == pytest.approx(0.03)
    assert price_of("tanımsız-model") == (2.0, 12.0)
    assert b.spent_today() == pytest.approx(0.58)
    # günlük limit aşıldı → akıllı model yerine ucuz model
    assert b.choose_model("smart") == app.cfg.model_fast
    app.cfg.daily_limit_usd = 10
    assert b.choose_model("smart") == app.cfg.model_smart
    app.cfg.monthly_limit_usd = 0.5
    with pytest.raises(BudgetExceeded):
        b.choose_model("fast")
    assert "Bu ay" in b.report()
