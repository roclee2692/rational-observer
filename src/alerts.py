"""异常检测 (Job 2)。只报真正值得停下来看的。宁缺毋滥。
返回告警行列表(空 = 今日无异常)。阈值见 config/settings.yaml。
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path
import yaml
from db import connect
from assets import load_assets

SETTINGS = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


def _cfg():
    with open(SETTINGS, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("alerts", {})


def check(today: str | None = None, con=None, cfg: dict | None = None,
          assets: list[dict] | None = None) -> list[str]:
    """检查今日异常。

    参数均为可选依赖注入，方便测试：
    - today:  指定日期字符串 (默认今天)
    - con:    DuckDB 连接 (默认连接生产库)
    - cfg:    告警配置 dict (默认从 settings.yaml 读取)
    - assets: 资产列表 (默认从 assets.yaml 读取)
    """
    today = today or dt.date.today().isoformat()
    if cfg is None:
        cfg = _cfg()
    if con is None:
        con = connect()
    if assets is None:
        assets = load_assets()

    names = {a["id"]: a.get("name", a["id"]) for a in assets}
    out: list[str] = []

    # 1) VIX 突破阈值
    vix = con.execute(
        "SELECT value FROM macro_indicators WHERE indicator='VIX' AND date=?", [today]
    ).fetchone()
    vix_threshold = cfg.get("vix_threshold", 30)
    if vix and vix[0] >= vix_threshold:
        out.append(f"⚠️ VIX={vix[0]:.1f} 突破 {vix_threshold} —— 市场恐慌升温")

    # 2) 任一资产单日波动 > 阈值
    thr = cfg.get("daily_move_pct", 3.0)
    rows = con.execute("SELECT asset_id, close FROM daily_prices WHERE date=?", [today]).fetchall()
    for asset_id, close in rows:
        prev = con.execute(
            "SELECT close FROM daily_prices WHERE asset_id=? AND date<? ORDER BY date DESC LIMIT 1",
            [asset_id, today],
        ).fetchone()
        if prev and prev[0]:
            pct = (close - prev[0]) / prev[0] * 100
            if abs(pct) >= thr:
                out.append(f"⚠️ {names.get(asset_id, asset_id)} 单日 {pct:+.1f}%(>{thr}%)")

    # 3) 配比漂移:需要真实持仓(portfolio_snapshots)。暂无则跳过。
    snap = con.execute(
        "SELECT COUNT(*) FROM portfolio_snapshots WHERE date=?", [today]
    ).fetchone()
    if snap and snap[0]:
        drift = cfg.get("drift_pct", 5.0)
        for asset_id, tgt, act in con.execute(
            "SELECT asset_id, target_pct, actual_pct FROM portfolio_snapshots WHERE date=?", [today]
        ).fetchall():
            if tgt and abs(act - tgt) >= drift:
                out.append(f"⚠️ {names.get(asset_id, asset_id)} 配比偏离: 实际{act:.1f}% vs 目标{tgt:.0f}%(考虑再平衡)")

    return out


if __name__ == "__main__":
    a = check()
    print("\n".join(a) if a else "✓ 今日无异常")
