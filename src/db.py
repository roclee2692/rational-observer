"""L0 时序库 (DuckDB) —— 事实层,永不压缩,永不删除 (架构第五节)。"""
from __future__ import annotations
from pathlib import Path
import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "observer.duckdb"

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_prices (
    date DATE, asset_id VARCHAR,
    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
    PRIMARY KEY (date, asset_id)
);
CREATE TABLE IF NOT EXISTS macro_indicators (
    date DATE, indicator VARCHAR, value DOUBLE,
    PRIMARY KEY (date, indicator)
);
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    date DATE, asset_id VARCHAR,
    target_pct DOUBLE, actual_pct DOUBLE, value DOUBLE,
    PRIMARY KEY (date, asset_id)
);
"""


def connect(path: Path = DB):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA)
    return con


def upsert_price(con, date, asset_id, o, h, l, c, v):
    con.execute(
        "INSERT OR REPLACE INTO daily_prices VALUES (?,?,?,?,?,?,?)",
        [date, asset_id, o, h, l, c, v],
    )


def period_returns(con, asset_id, end_date, periods=(1, 7, 30)) -> dict[int, float | None]:
    """Return percentage return over each period ending at end_date.

    For each N in periods, returns the return from the trading day N calendar
    days before end_date (or the nearest earlier trading day) to end_date.
    Returns None if insufficient data.
    """
    # Get the close on end_date
    cur = con.execute(
        "SELECT close FROM daily_prices WHERE asset_id=? AND date<=? "
        "ORDER BY date DESC LIMIT 1",
        [asset_id, end_date],
    ).fetchone()
    if not cur or cur[0] is None:
        return {n: None for n in periods}
    latest_close = cur[0]

    result: dict[int, float | None] = {}
    for n in periods:
        # Find the close approximately N days ago (nearest earlier trading day)
        row = con.execute(
            "SELECT close FROM daily_prices "
            "WHERE asset_id=? AND date <= ?::DATE - INTERVAL (?) DAYS "
            "ORDER BY date DESC LIMIT 1",
            [asset_id, end_date, n],
        ).fetchone()
        if row and row[0] and row[0] != 0:
            result[n] = (latest_close - row[0]) / row[0] * 100
        else:
            result[n] = None
    return result


if __name__ == "__main__":
    con = connect()
    print(f"✓ L0 时序库已就绪: {DB}")
    print(con.execute("SHOW TABLES").fetchall())
