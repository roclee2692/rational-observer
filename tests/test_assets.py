"""assets.py 校验器测试套件。

构造最小化的内存资产列表,验证每条校验规则都能正确触发 ——
不依赖真实 assets.yaml,快、确定、不污染生产配置。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from assets import (  # noqa: E402
    validate, load_assets, enabled, held,
    PORTFOLIO_LAYERS, OBSERVATION_LAYERS, VALID_LAYERS,
)


def _asset(**kwargs):
    """构造一个最小合法资产 (单仓 100%),可用 kwargs 覆盖任意字段。"""
    base = {
        "id": "TEST", "name": "测试资产", "layer": "equity",
        "source": "yfinance", "ticker": "TEST.SS",
        "target_pct": 100, "enabled": True,
    }
    base.update(kwargs)
    return base


def _valid_two():
    return [
        _asset(id="A", layer="defense", target_pct=40),
        _asset(id="B", layer="equity", target_pct=60),
    ]


# ---------- 正向 ----------

class TestValidatePass:
    def test_single_asset_100pct(self):
        validate([_asset()])

    def test_two_assets_sum_100(self):
        validate(_valid_two())

    def test_observation_zero_pct(self):
        validate([
            _asset(id="A", target_pct=100),
            _asset(id="OBS", target_pct=0, layer="commodity", ticker="USO"),
        ])

    def test_all_portfolio_layers_can_hold(self):
        for layer in PORTFOLIO_LAYERS:
            extra = {"source": "coingecko", "coin_id": "btc"} if layer == "crypto" else {}
            validate([_asset(layer=layer, target_pct=100, **extra)])

    def test_observation_layers_at_zero(self):
        """观察层资产 target_pct=0 合法。"""
        for layer in OBSERVATION_LAYERS:
            validate([
                _asset(id="HOLD", target_pct=100),
                _asset(id="OBS", layer=layer, target_pct=0, ticker="X"),
            ])

    def test_disabled_asset_excluded(self):
        validate([
            _asset(id="A", target_pct=100),
            _asset(id="B", target_pct=50, enabled=False),  # 停用 → 不计入配比
        ])

    def test_coingecko_with_coin_id(self):
        validate([_asset(source="coingecko", coin_id="bitcoin", layer="crypto", target_pct=100)])

    def test_manual_source_needs_no_ticker(self):
        a = _asset(source="manual", target_pct=100)
        a.pop("ticker", None)
        validate([a])


# ---------- 配比 / 范围 ----------

class TestAllocationValidation:
    def test_sum_less_than_100(self):
        with pytest.raises(ValueError, match="总和必须=100%"):
            validate([_asset(target_pct=90)])

    def test_sum_more_than_100(self):
        with pytest.raises(ValueError, match="总和必须=100%"):
            validate([_asset(id="A", target_pct=60), _asset(id="B", target_pct=50)])

    def test_observation_not_counted(self):
        validate([
            _asset(id="A", target_pct=100),
            _asset(id="OBS", target_pct=0, layer="ref", ticker="^GSPC"),
        ])

    def test_negative_target_pct(self):
        with pytest.raises(ValueError, match="越界"):
            validate([_asset(target_pct=-5)])

    def test_target_pct_over_100(self):
        with pytest.raises(ValueError, match="越界"):
            validate([_asset(target_pct=150)])


# ---------- 必填字段 ----------

class TestRequiredFields:
    @pytest.mark.parametrize("field", ["id", "layer", "source", "target_pct", "enabled"])
    def test_missing_field_raises(self, field):
        a = _asset()
        del a[field]
        with pytest.raises(ValueError, match=f"缺少必填字段.*{field}"):
            validate([a])

    def test_empty_list(self):
        with pytest.raises(ValueError, match="资产列表为空"):
            validate([])

    def test_non_dict_entry(self):
        with pytest.raises(ValueError, match="必须是字典"):
            validate(["not a dict"])


# ---------- 枚举 ----------

class TestEnumValidation:
    def test_invalid_layer(self):
        with pytest.raises(ValueError, match="layer.*不合法"):
            validate([_asset(layer="bogus")])

    def test_invalid_source(self):
        with pytest.raises(ValueError, match="source.*不合法"):
            validate([_asset(source="bogus")])

    def test_coingecko_missing_coin_id(self):
        with pytest.raises(ValueError, match="coin_id 必填"):
            validate([_asset(source="coingecko", layer="crypto")])

    def test_yfinance_missing_ticker(self):
        a = _asset(source="yfinance")
        del a["ticker"]
        with pytest.raises(ValueError, match="ticker 必填"):
            validate([a])


# ---------- 类型 ----------

class TestTypeValidation:
    def test_target_pct_not_number(self):
        with pytest.raises(ValueError, match="target_pct 必须是数字"):
            validate([_asset(target_pct="abc")])

    def test_target_pct_bool_rejected(self):
        with pytest.raises(ValueError, match="target_pct 必须是数字"):
            validate([_asset(target_pct=True)])

    def test_enabled_not_bool(self):
        with pytest.raises(ValueError, match="enabled 必须是布尔值"):
            validate([_asset(enabled="yes")])

    def test_empty_id(self):
        with pytest.raises(ValueError, match="id 必须是非空字符串"):
            validate([_asset(id="")])


# ---------- 重复 id ----------

class TestDuplicateIds:
    def test_duplicate_id_raises(self):
        with pytest.raises(ValueError, match="资产 id 重复"):
            validate([_asset(id="DUP", target_pct=50),
                      _asset(id="DUP", layer="defense", target_pct=50)])

    def test_unique_ids_pass(self):
        validate(_valid_two())


# ---------- 持仓 / 观察 层语义 ----------

class TestLayerSemantics:
    def test_observation_layer_cannot_hold(self):
        """观察层 (commodity/realestate/ref) 配实仓应报错。"""
        with pytest.raises(ValueError, match="观察层不允许配实仓"):
            validate([_asset(id="OIL", layer="commodity", target_pct=100)])

    def test_realestate_position_rejected(self):
        with pytest.raises(ValueError, match="观察层不允许配实仓"):
            validate([_asset(id="A", target_pct=50),
                      _asset(id="REIT", layer="realestate", target_pct=50, ticker="VNQ")])


# ---------- 辅助函数 ----------

class TestHelperFunctions:
    def test_enabled_filters_disabled(self):
        out = enabled([_asset(id="A", enabled=True), _asset(id="B", enabled=False)])
        assert [a["id"] for a in out] == ["A"]

    def test_held_filters_zero_pct(self):
        out = held([
            _asset(id="A", target_pct=100),
            _asset(id="B", target_pct=0, layer="commodity", ticker="USO"),
        ])
        assert [a["id"] for a in out] == ["A"]

    def test_held_excludes_disabled(self):
        assert held([_asset(id="A", target_pct=100, enabled=False)]) == []


# ---------- 真实配置冒烟 ----------

class TestRealConfig:
    def test_real_assets_yaml_validates(self):
        path = Path(__file__).resolve().parent.parent / "config" / "assets.yaml"
        if not path.exists():
            pytest.skip("真实 assets.yaml 不存在")
        assets = load_assets(path)
        validate(assets)
        assert len(assets) > 0
        assert len(held(assets)) > 0
        # 真实配置中所有持仓都应落在可持仓层
        assert all(a["layer"] in PORTFOLIO_LAYERS for a in held(assets))


# ---------- 错误消息质量 ----------

class TestErrorMessageQuality:
    def test_multiple_errors_collected(self):
        a = _asset(layer="bad", source="bad", target_pct="x", enabled="x")
        with pytest.raises(ValueError) as exc:
            validate([a])
        msg = str(exc.value)
        assert "layer" in msg and "不合法" in msg
        assert "source" in msg and "不合法" in msg
        assert "target_pct 必须是数字" in msg
        assert "enabled 必须是布尔值" in msg

    def test_error_mentions_asset_id(self):
        with pytest.raises(ValueError) as exc:
            validate([_asset(id="FIND_ME", layer="bad")])
        assert "FIND_ME" in str(exc.value)
