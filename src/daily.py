"""每日日报 (Job 1 输出)。先采集,再从 L0 出一份事实日报(含日涨跌)。
纯事实,无买卖建议 —— 观察者不决策。供 agent 整理后推送飞书。
"""
from __future__ import annotations
import datetime as dt
from assets import load_assets, enabled
import ingest
import macro
import alerts
from db import connect, period_returns

LAYER_CN = {"defense": "防守", "equity": "权益", "crypto": "加密",
            "commodity": "商品", "realestate": "房地产", "ref": "参考"}
LAYER_ORDER = ["防守", "权益", "加密", "商品", "房地产", "参考", "其他"]


def _fmt_ret(pct: float | None, prefix: str = "") -> str:
    """Format a percentage return with arrow. Returns '  —' if None."""
    if pct is None:
        return f"  {prefix}—"
    arrow = "🔺" if pct > 0 else ("🔻" if pct < 0 else "▪️")
    return f"  {prefix}{arrow}{pct:+.1f}%"


def report(today: str | None = None) -> str:
    today = today or dt.date.today().isoformat()
    # 1) 采集当日数据(价格 + 宏观)
    ingest.run(today)
    macro.run(today)
    con = connect()
    assets = {a["id"]: a for a in load_assets()}

    rows = con.execute(
        "SELECT asset_id, close FROM daily_prices WHERE date = ? ORDER BY asset_id", [today]
    ).fetchall()
    if not rows:
        return f"⚠️ {today} 无采集数据,请检查采集 Job。"

    lines = [f"📊 市场日报 · {today}", ""]
    by_layer: dict[str, list[str]] = {}
    for asset_id, close in rows:
        # 多期收益率 (1D/7D/30D)
        rets = period_returns(con, asset_id, today, periods=(1, 7, 30))
        chg_1d = _fmt_ret(rets.get(1))
        chg_7d = _fmt_ret(rets.get(7), prefix="7D:")
        chg_30d = _fmt_ret(rets.get(30), prefix="30D:")
        a = assets.get(asset_id, {})
        kind = "" if a.get("target_pct", 0) > 0 else " (观察)"
        layer = LAYER_CN.get(a.get("layer", ""), "其他")
        by_layer.setdefault(layer, []).append(
            f"  {a.get('name', asset_id)}{kind}: {close:,.2f}  {chg_1d}  {chg_7d}  {chg_30d}"
        )

    for layer in LAYER_ORDER:
        if layer in by_layer:
            lines.append(f"【{layer}】")
            lines.extend(by_layer[layer])
            lines.append("")

    # 宏观一行
    macros = con.execute(
        "SELECT indicator, value FROM macro_indicators WHERE date=? ORDER BY indicator", [today]
    ).fetchall()
    if macros:
        lines.append("【宏观】 " + "  ".join(f"{i}={v:.2f}" for i, v in macros))
        lines.append("")

    # 异常警报(有才显示)
    alarms = alerts.check(today)
    if alarms:
        lines.append("🚨 异常提醒:")
        lines.extend("  " + a for a in alarms)
        lines.append("")

    # 到期待复盘的预测(L4 台账)
    try:
        import ledger
        duep = ledger.con().execute(
            "SELECT id, prediction FROM predictions WHERE status='pending' AND target_date<=?", [today]
        ).fetchall()
        if duep:
            lines.append(f"📌 {len(duep)} 条预测到期待复盘(回我即可复盘):")
            lines.extend(f"  #{i} {p}" for i, p in duep)
            lines.append("")
    except Exception:
        pass

    lines.append("— 仅事实呈现,决策在你 ✨")
    text = "\n".join(lines)

    # 存入 L1 向量记忆(缺依赖则跳过,不影响出报)
    try:
        import memory
        memory.add(today, text, level="L1")
    except Exception as e:
        print(f"  (L1 记忆跳过: {e})")
    return text


if __name__ == "__main__":
    print(report())
