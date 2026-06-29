"""Tests for period_returns utility and daily report integration."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb
from db import connect, upsert_price, period_returns


def _seed(con, asset_id, data):
    """Seed test data: list of (date_str, close)."""
    for date_str, close in data:
        upsert_price(con, date_str, asset_id, close, close, close, close, 0.0)


def test_period_returns_basic():
    """Test 1D and 7D returns with clean daily data."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE daily_prices (
            date DATE, asset_id VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            PRIMARY KEY (date, asset_id)
        )
    """)

    # 10 days of data: day 0 = 100, day 7 = 110, day 9 = 120
    # Using real dates spaced by 1 day
    base = 100.0
    data = []
    for i in range(10):
        date = f"2026-01-{i+1:02d}"
        price = base + i * 2.0  # 100, 102, 104, ... 118
        data.append((date, price))
    # Make day 9 (2026-01-10) price = 120 for clean 10% over 10 days
    data[-1] = ("2026-01-10", 120.0)
    # Make day 2 (2026-01-03) price = 100 for testing 7D return from day 9
    data[2] = ("2026-01-03", 100.0)

    _seed(con, "TEST", data)

    rets = period_returns(con, "TEST", "2026-01-10", periods=(1, 7, 30))

    # 1D return: from 2026-01-09 (116) to 2026-01-10 (120) = (120-116)/116*100 = 3.448...%
    assert rets[1] is not None
    assert abs(rets[1] - 3.45) < 0.1, f"1D return expected ~3.45%, got {rets[1]:.2f}%"

    # 7D return: from 2026-01-03 (100) to 2026-01-10 (120) = 20%
    assert rets[7] is not None
    assert abs(rets[7] - 20.0) < 0.1, f"7D return expected 20%, got {rets[7]:.2f}%"

    # 30D return: no data 30 days ago → None
    assert rets[30] is None, f"30D should be None, got {rets[30]}"


def test_period_returns_no_data():
    """Returns None for all periods when asset has no data."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE daily_prices (
            date DATE, asset_id VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            PRIMARY KEY (date, asset_id)
        )
    """)
    rets = period_returns(con, "NOPE", "2026-01-10", periods=(1, 7, 30))
    assert all(v is None for v in rets.values()), f"Expected all None, got {rets}"


def test_period_returns_negative():
    """Test negative returns."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE daily_prices (
            date DATE, asset_id VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            PRIMARY KEY (date, asset_id)
        )
    """)
    _seed(con, "DOWN", [
        ("2026-01-01", 100.0),
        ("2026-01-08", 80.0),  # -20% over ~7 days
    ])
    rets = period_returns(con, "DOWN", "2026-01-08", periods=(7,))
    assert rets[7] is not None
    assert rets[7] < 0, f"Expected negative return, got {rets[7]}"
    assert abs(rets[7] - (-20.0)) < 0.1, f"Expected ~-20%, got {rets[7]:.2f}%"


def test_period_returns_zero():
    """Test zero return."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE daily_prices (
            date DATE, asset_id VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            PRIMARY KEY (date, asset_id)
        )
    """)
    _seed(con, "FLAT", [
        ("2026-01-01", 50.0),
        ("2026-01-08", 50.0),
    ])
    rets = period_returns(con, "FLAT", "2026-01-08", periods=(7,))
    val = rets[7]
    assert val is not None
    assert abs(val) < 0.001


def test_period_returns_weekend_gap():
    """Test that the function finds the nearest earlier trading day for weekends."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE daily_prices (
            date DATE, asset_id VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            PRIMARY KEY (date, asset_id)
        )
    """)
    # 2026-01-01 (Thu) = 100, 2026-01-02 (Fri) = 105
    # 2026-01-05 (Mon) = 110 (weekend skipped)
    _seed(con, "WEEKEND", [
        ("2026-01-01", 100.0),
        ("2026-01-02", 105.0),
        ("2026-01-05", 110.0),
    ])
    # On Monday Jan 5, 3-day return should look back to Friday Jan 2
    rets = period_returns(con, "WEEKEND", "2026-01-05", periods=(3,))
    assert rets[3] is not None
    # From 105 (Jan 2) to 110 (Jan 5) = 4.76%
    assert abs(rets[3] - 4.76) < 0.1, f"Expected ~4.76%, got {rets[3]:.2f}%"


if __name__ == "__main__":
    import traceback
    tests = [
        test_period_returns_basic,
        test_period_returns_no_data,
        test_period_returns_negative,
        test_period_returns_zero,
        test_period_returns_weekend_gap,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
