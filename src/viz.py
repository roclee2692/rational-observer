"""统计可视化 (架构第六节)。从 L0 出图,英文标签(防中文缺字)。
图存到 viz/。用 pandas 对齐不同资产的交易日,稳健处理缺口。

  python viz.py            # 生成全部图表
"""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from db import connect

OUT = Path(__file__).resolve().parent.parent / "viz"
OUT.mkdir(exist_ok=True)
MIN_PTS = 5
RECENT_DAYS = 504  # 跨资产对比/相关性用最近~2年的共同窗口(避免混不同时代 regime)


def load_df() -> pd.DataFrame:
    """返回 DataFrame: index=date, columns=asset_id, values=close。"""
    con = connect()
    df = con.execute(
        "SELECT date, asset_id, close FROM daily_prices ORDER BY date"
    ).df()
    if df.empty:
        return df
    wide = df.pivot_table(index="date", columns="asset_id", values="close")
    wide.index = pd.to_datetime(wide.index)
    # 只保留有足够数据的资产
    keep = [c for c in wide.columns if wide[c].notna().sum() >= MIN_PTS]
    return wide[keep].sort_index()


def _recent(df):
    """最近 RECENT_DAYS 个交易日里、所有资产都有数据的共同窗口。"""
    tail = df.tail(RECENT_DAYS)
    return tail.dropna(axis=1, how="any") if not tail.empty else tail


def chart_normalized(df, out=OUT / "normalized.png"):
    d = _recent(df).ffill()
    norm = d / d.apply(lambda s: s[s.first_valid_index()]) * 100
    fig, ax = plt.subplots(figsize=(11, 5))
    for c in sorted(norm.columns):
        ax.plot(norm.index, norm[c], label=c, linewidth=1.5)
    ax.set_title("Normalized Performance (rebased to 100)")
    ax.set_ylabel("Index (start=100)"); ax.legend(ncol=3, fontsize=8); ax.grid(alpha=0.3)
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return out


def chart_correlation(df, out=OUT / "correlation.png"):
    # 用最近~2年共同窗口(短周期相关性才反映"当下regime";长期相关性是时变的,
    # 真要看演变应做滚动相关性)。pandas .corr() 处理成对完整观测。
    corr = _recent(df).pct_change(fill_method=None).corr()
    ids = list(corr.columns)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(ids))); ax.set_xticklabels(ids, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(ids))); ax.set_yticklabels(ids, fontsize=8)
    for i in range(len(ids)):
        for j in range(len(ids)):
            v = corr.values[i, j]
            ax.text(j, i, "—" if pd.isna(v) else f"{v:.2f}", ha="center", va="center", fontsize=7)
    ax.set_title("Return Correlation Matrix")
    fig.colorbar(im, fraction=0.046); fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return out


def chart_drawdown(df, out=OUT / "drawdown.png"):
    d = df.ffill()
    dd = (d / d.cummax() - 1) * 100
    fig, ax = plt.subplots(figsize=(11, 5))
    for c in sorted(dd.columns):
        ax.plot(dd.index, dd[c], label=c, linewidth=1.2)
    ax.set_title("Drawdown from Peak (%)"); ax.set_ylabel("Drawdown %")
    ax.legend(ncol=3, fontsize=8); ax.grid(alpha=0.3)
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return out


def chart_volatility(df, out=OUT / "volatility.png", window=30):
    rets = df.pct_change(fill_method=None)
    vol = rets.rolling(window).std() * (252 ** 0.5) * 100
    fig, ax = plt.subplots(figsize=(11, 5))
    for c in sorted(vol.columns):
        ax.plot(vol.index, vol[c], label=c, linewidth=1.2)
    ax.set_title(f"Rolling {window}d Annualized Volatility (%)"); ax.set_ylabel("Vol %")
    ax.legend(ncol=3, fontsize=8); ax.grid(alpha=0.3)
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return out


def chart_century(df, assets=("SP500", "NASDAQ"), out=OUT / "century.png"):
    """长历史专图:上=对数价格(看百年复利),下=标普回撤(看历次崩盘)。"""
    cols = [a for a in assets if a in df.columns]
    if not cols:
        return None
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    for a in cols:
        s = df[a].dropna()
        ax1.plot(s.index, s.values, label=a, linewidth=1)
    ax1.set_yscale("log"); ax1.set_title("US Equity — Full History (log scale)")
    ax1.set_ylabel("Price (log)"); ax1.legend(fontsize=9); ax1.grid(alpha=0.3, which="both")
    # 标普回撤
    sp = df[cols[0]].dropna()
    dd = (sp / sp.cummax() - 1) * 100
    ax2.fill_between(dd.index, dd.values, 0, color="crimson", alpha=0.4)
    ax2.set_title(f"{cols[0]} Drawdown (%) — 1929 / 2008 / 2020 visible")
    ax2.set_ylabel("Drawdown %"); ax2.grid(alpha=0.3)
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return out


def chart_rolling_corr(df, pairs=(("SP500", "BTC"), ("GOLD", "SP500"),
                                  ("BTC", "ETH"), ("BOND", "SP500")),
                       window=90, out=OUT / "rolling_corr.png"):
    """关键资产对的滚动相关性随时间变化 —— 看关系如何演变(时变的!)。"""
    fig, ax = plt.subplots(figsize=(12, 5))
    drew = False
    for a, b in pairs:
        if a in df.columns and b in df.columns:
            sub = df[[a, b]].dropna()           # 先对齐到两者共同交易日
            if len(sub) < window + 10:
                continue
            r = sub.pct_change(fill_method=None)
            rc = r[a].rolling(window).corr(r[b]).dropna()
            if len(rc) > 5:
                ax.plot(rc.index, rc.values, label=f"{a}↔{b}", linewidth=1.3)
                drew = True
    if not drew:
        plt.close(fig); return None
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.set_ylim(-1, 1)
    ax.set_title(f"Rolling {window}d Correlation (how relationships drift over time)")
    ax.set_ylabel("Correlation"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return out


def generate_all():
    df = load_df()
    if df.empty or df.shape[1] == 0:
        print(f"数据不足(每资产需≥{MIN_PTS}天)。先 backfill 或多跑几天。")
        return []
    paths = [chart_normalized(df), chart_drawdown(df), chart_volatility(df)]
    if df.shape[1] >= 2:
        paths.append(chart_correlation(df))
    c = chart_century(df)
    if c:
        paths.append(c)
    rc = chart_rolling_corr(df)
    if rc:
        paths.append(rc)
    for p in paths:
        print(f"  ✓ {p}")
    return paths


if __name__ == "__main__":
    generate_all()
