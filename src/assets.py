"""资产注册表加载与校验 (架构第三节)。
所有模块都从这里读取资产宇宙 —— 一处定义,处处生效。

校验器用 ``ValueError`` 而非 ``assert``,确保在 ``python -O`` 模式下依然生效;
一次收集全部错误后统一抛出,而不是发现一个就退出。
"""
from __future__ import annotations
import sys
from collections import defaultdict
from pathlib import Path
import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG = _CONFIG_DIR / "assets.yaml"
# 私有配置覆盖:存在 assets.local.yaml 时优先读取它(已 gitignore,不进开源仓库)。
CONFIG_LOCAL = _CONFIG_DIR / "assets.local.yaml"

# 合法的 layer 白名单。
#   前三层 = 40/50/10 框架中"可持仓"的核心层;
#   其余仅作观察/参考用 —— target_pct 必须为 0,不允许配实仓。
PORTFOLIO_LAYERS = {"defense", "equity", "crypto"}
OBSERVATION_LAYERS = {"commodity", "realestate", "ref"}
VALID_LAYERS = PORTFOLIO_LAYERS | OBSERVATION_LAYERS

VALID_SOURCES = {"manual", "yfinance", "coingecko"}
REQUIRED_FIELDS = {"id", "layer", "source", "target_pct", "enabled"}


def load_assets(path: Path | None = None) -> list[dict]:
    if path is None:
        path = CONFIG_LOCAL if CONFIG_LOCAL.exists() else CONFIG
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    assets = data.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("assets.yaml 顶层 'assets' 字段必须是列表")
    return assets


def validate(assets: list[dict]) -> None:
    """启动时校验 (防呆)。失败抛 :class:`ValueError`,消息里列出全部问题。

    校验内容:
      1) 每条资产是字典、必填字段齐全。
      2) ``id`` 非空且全局唯一。
      3) ``layer`` / ``source`` 在白名单内。
      4) ``target_pct`` 是 [0, 100] 内的数值; ``enabled`` 是布尔。
      5) 数据源标识符必填 (yfinance→ticker, coingecko→coin_id)。
      6) 持仓 (target_pct>0 且 enabled) 只能落在 PORTFOLIO_LAYERS —— 观察层不许配实仓。
      7) 持仓 target_pct 总和 = 100%。
    """
    errors: list[str] = []

    if not assets:
        errors.append("资产列表为空 —— 检查 config/assets.yaml")

    # 1) 逐条:类型 / 必填 / 枚举 / 范围
    for i, a in enumerate(assets):
        if not isinstance(a, dict):
            errors.append(f"<第{i}项>: 资产条目必须是字典")
            continue

        label = a.get("id", f"<第{i}项>")

        missing = REQUIRED_FIELDS - a.keys()
        if missing:
            errors.append(f"{label}: 缺少必填字段 {', '.join(sorted(missing))}")
            continue  # 后续检查依赖这些字段

        if not isinstance(a["id"], str) or not a["id"].strip():
            errors.append(f"{label}: id 必须是非空字符串")

        if a["layer"] not in VALID_LAYERS:
            errors.append(f"{a['id']}: layer '{a['layer']}' 不合法,允许值 {sorted(VALID_LAYERS)}")

        if a["source"] not in VALID_SOURCES:
            errors.append(f"{a['id']}: source '{a['source']}' 不合法,允许值 {sorted(VALID_SOURCES)}")

        tp = a["target_pct"]
        if not isinstance(tp, (int, float)) or isinstance(tp, bool):
            errors.append(f"{a['id']}: target_pct 必须是数字")
        elif tp < 0 or tp > 100:
            errors.append(f"{a['id']}: target_pct={tp} 越界 —— 必须在 [0, 100] 内")

        if not isinstance(a["enabled"], bool):
            errors.append(f"{a['id']}: enabled 必须是布尔值")

        if a["source"] == "coingecko" and not a.get("coin_id"):
            errors.append(f"{a['id']}: source=coingecko 时 coin_id 必填")
        if a["source"] == "yfinance" and not a.get("ticker"):
            errors.append(f"{a['id']}: source=yfinance 时 ticker 必填")

    # 2) id 唯一
    ids = [a["id"] for a in assets if isinstance(a, dict) and "id" in a]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        errors.append(f"资产 id 重复: {', '.join(dupes)}")

    # 3) 持仓 (字段完整且 target_pct>0 且 enabled) 的语义校验
    def _is_held(a: dict) -> bool:
        return (
            isinstance(a, dict)
            and isinstance(a.get("target_pct"), (int, float))
            and not isinstance(a.get("target_pct"), bool)
            and a.get("target_pct", 0) > 0
            and a.get("enabled") is True
            and a.get("layer") in VALID_LAYERS
        )

    held_assets = [a for a in assets if _is_held(a)]

    # 3a) 观察层不允许配实仓
    for a in held_assets:
        if a["layer"] in OBSERVATION_LAYERS:
            errors.append(
                f"{a['id']}: 是持仓 (target_pct={a['target_pct']}%) 但 layer='{a['layer']}' "
                f"属于观察层 —— 观察层不允许配实仓"
            )

    # 3b) 持仓配比总和 = 100%
    layers: defaultdict[str, float] = defaultdict(float)
    if held_assets:
        total = sum(a["target_pct"] for a in held_assets)
        if abs(total - 100) > 0.01:
            errors.append(f"持仓资产 target_pct 总和必须=100%,当前={total}%")
        for a in held_assets:
            layers[a["layer"]] += a["target_pct"]

    if errors:
        raise ValueError("assets.yaml 校验失败:\n  • " + "\n  • ".join(errors))

    print(f"✓ assets.yaml 校验通过 — 持仓 {len(held_assets)} / 观察 {len(assets)-len(held_assets)}")
    if layers:
        print("  " + " ".join(f"{k}={v:.0f}%" for k, v in sorted(layers.items())))


def enabled(assets: list[dict] | None = None) -> list[dict]:
    return [a for a in (assets or load_assets()) if a.get("enabled")]


def held(assets: list[dict] | None = None) -> list[dict]:
    """参与配比/再平衡的持仓资产 (target_pct > 0 且 enabled=True)。"""
    return [a for a in enabled(assets) if a.get("target_pct", 0) > 0]


if __name__ == "__main__":
    a = load_assets()
    try:
        validate(a)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)
    print("\n采集清单 (enabled):")
    for x in enabled(a):
        kind = "持仓" if x.get("target_pct", 0) > 0 else "观察"
        ref = x.get("ticker") or x.get("coin_id") or "-"
        print(f"  [{kind}] {x['id']:7} {x['source']:9} {ref:16} target={x.get('target_pct',0)}%")
