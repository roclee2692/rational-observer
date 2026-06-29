"""alerts.py 测试套件。

使用内存 DuckDB 构造测试数据，覆盖：
- VIX 阈值告警（低于/等于/高于）
- 单日波动告警（正常/边界/上涨/下跌）
- 配比漂移告警（无快照/正常/边界/超标）
- 资产名称映射（已知/未知）
"""
from __future__ import annotations
import sys, os
import duckdb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import alerts

# ---------- helpers ----------

TEST_ASSETS = [
    {"id": "SPX", "name": "标普500", "layer": "equity", "source": "yfinance", "ticker": "VOO", "target_pct": 50, "enabled": True},
    {"id": "GOLD", "name": "黄金", "layer": "defense", "source": "yfinance", "ticker": "518880.SS", "target_pct": 10, "enabled": True},
    {"id": "BTC", "name": "Bitcoin", "layer": "crypto", "source": "coingecko", "coin_id": "bitcoin", "target_pct": 7, "enabled": True},
]

SCHEMA = """
CREATE TABLE daily_prices (date DATE, asset_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE);
CREATE TABLE macro_indicators (date DATE, indicator VARCHAR, value DOUBLE);
CREATE TABLE portfolio_snapshots (date DATE, asset_id VARCHAR, target_pct DOUBLE, actual_pct DOUBLE, value DOUBLE);
"""


def make_con():
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA)
    return con


def cfg(**overrides):
    base = {"vix_threshold": 30, "daily_move_pct": 3.0, "drift_pct": 5.0}
    base.update(overrides)
    return base


# ---------- VIX tests ----------

class TestVIXAlert:
    def test_vix_below_threshold_no_alert(self):
        con = make_con()
        con.execute("INSERT INTO macro_indicators VALUES ('2026-06-20', 'VIX', 15.0)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert result == []

    def test_vix_above_threshold_triggers_alert(self):
        con = make_con()
        con.execute("INSERT INTO macro_indicators VALUES ('2026-06-20', 'VIX', 32.5)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert len(result) == 1
        assert "VIX=32.5" in result[0]
        assert "突破 30" in result[0]

    def test_vix_at_threshold_exactly_triggers(self):
        """>= 比较，等于阈值应触发"""
        con = make_con()
        con.execute("INSERT INTO macro_indicators VALUES ('2026-06-20', 'VIX', 30.0)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert len(result) == 1
        assert "VIX=30.0" in result[0]

    def test_vix_no_data_no_alert(self):
        con = make_con()
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert result == []

    def test_vix_custom_threshold(self):
        con = make_con()
        con.execute("INSERT INTO macro_indicators VALUES ('2026-06-20', 'VIX', 22.0)")
        # 阈值设为 20，22 > 20 应触发
        result = alerts.check("2026-06-20", con=con, cfg=cfg(vix_threshold=20), assets=TEST_ASSETS)
        assert len(result) == 1
        assert "突破 20" in result[0]


# ---------- daily move tests ----------

class TestDailyMoveAlert:
    def test_no_move_no_alert(self):
        con = make_con()
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'SPX', 100, 101, 99, 100, 1000000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'SPX', 100, 101, 99, 100.5, 1000000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # 0.5% 波动 < 3% 阈值
        assert result == []

    def test_large_gain_triggers_alert(self):
        con = make_con()
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'BTC', 30000, 31000, 29000, 30000, 1000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'BTC', 31000, 32000, 30500, 31500, 1000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # (31500 - 30000) / 30000 * 100 = 5.0% > 3%
        assert len(result) == 1
        assert "Bitcoin" in result[0]
        assert "+5.0%" in result[0]

    def test_large_drop_triggers_alert(self):
        con = make_con()
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'GOLD', 10, 10.1, 9.9, 10.0, 10000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'GOLD', 9.5, 9.7, 9.3, 9.5, 10000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # (9.5 - 10.0) / 10.0 * 100 = -5.0%
        assert len(result) == 1
        assert "黄金" in result[0]
        assert "-5.0%" in result[0]

    def test_at_threshold_exactly_triggers(self):
        """abs(pct) >= thr，等于阈值应触发"""
        con = make_con()
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'SPX', 100, 101, 99, 100, 10000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'SPX', 103, 103.5, 102, 103, 10000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # 正好 3.0%
        assert len(result) == 1

    def test_below_threshold_no_alert(self):
        con = make_con()
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'SPX', 100, 101, 99, 100, 10000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'SPX', 102.9, 103, 102, 102.9, 10000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # 2.9% < 3%
        assert result == []

    def test_no_previous_day_no_alert(self):
        """只有当日数据，无前日收盘价，不触发"""
        con = make_con()
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'SPX', 100, 105, 95, 105, 10000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert result == []

    def test_unknown_asset_uses_id_in_message(self):
        """资产不在列表中时，用 id 显示"""
        con = make_con()
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'UNKNOWN', 100, 101, 99, 100, 10000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'UNKNOWN', 110, 111, 109, 110, 10000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert len(result) == 1
        assert "UNKNOWN" in result[0]

    def test_multiple_assets_both_trigger(self):
        """多个资产同时触发波动告警"""
        con = make_con()
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'SPX', 100, 101, 99, 100, 10000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'BTC', 30000, 31000, 29000, 30000, 1000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'SPX', 105, 105.5, 104, 105, 10000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'BTC', 32000, 32500, 31000, 32000, 1000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # SPX +5%, BTC +6.67% — 两个都触发
        assert len(result) == 2


# ---------- drift tests ----------

class TestDriftAlert:
    def test_no_snapshots_skips_drift(self):
        """无 portfolio_snapshots 数据时跳过配比检查"""
        con = make_con()
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert result == []

    def test_within_drift_no_alert(self):
        con = make_con()
        con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-06-20', 'SPX', 50, 52, 52000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # 偏差 2% < 5%
        assert result == []

    def test_above_drift_triggers(self):
        con = make_con()
        con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-06-20', 'BTC', 7, 13, 13000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # 偏差 6% > 5%
        assert len(result) == 1
        assert "Bitcoin" in result[0]
        assert "实际13.0% vs 目标7%" in result[0]

    def test_at_drift_exactly_triggers(self):
        """>= drift 边界，等于阈值应触发"""
        con = make_con()
        con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-06-20', 'GOLD', 10, 15, 15000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # 偏差正好 5%
        assert len(result) == 1

    def test_below_target_drift(self):
        """实际低于目标的漂移也应触发"""
        con = make_con()
        con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-06-20', 'SPX', 50, 43, 43000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # 偏差 7% > 5%
        assert len(result) == 1
        assert "标普500" in result[0]

    def test_zero_target_skipped(self):
        """target_pct=0 的观察资产不应触发漂移告警"""
        con = make_con()
        con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-06-20', 'SPX', 0, 55, 55000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # tgt=0 → if tgt and ... → False，跳过
        assert result == []

    def test_multiple_assets_drift(self):
        con = make_con()
        con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-06-20', 'SPX', 50, 58, 58000)")
        con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-06-20', 'BTC', 7, 2, 2000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        # SPX +8%, BTC -5% — 两个都触发
        assert len(result) == 2


# ---------- combined / integration ----------

class TestCombinedAlerts:
    def test_all_three_alert_types_together(self):
        con = make_con()
        # VIX 高
        con.execute("INSERT INTO macro_indicators VALUES ('2026-06-20', 'VIX', 35.0)")
        # 单日大跌
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-19', 'SPX', 100, 101, 99, 100, 10000)")
        con.execute("INSERT INTO daily_prices VALUES ('2026-06-20', 'SPX', 95, 96, 94, 95, 10000)")
        # 配比漂移
        con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-06-20', 'BTC', 7, 14, 14000)")
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert len(result) == 3  # VIX + 单日波动 + 配比漂移
        assert any("VIX" in r for r in result)
        assert any("标普500" in r for r in result)
        assert any("Bitcoin" in r for r in result)

    def test_empty_database_no_crash(self):
        """完全空的数据库不应崩溃，返回空列表"""
        con = make_con()
        result = alerts.check("2026-06-20", con=con, cfg=cfg(), assets=TEST_ASSETS)
        assert result == []
