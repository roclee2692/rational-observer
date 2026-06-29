"""历史回填 —— 把行情灌进 L0,让分析/可视化有数据。
yfinance 取 OHLCV(指数如 ^GSPC 可拉到 1927);CoinGecko 取每日收盘。
L0 是日线,极小:拉满全史也只是几 MB,不会挤爆库。

  python backfill.py            # 默认拉满全史 (period=max)
  python backfill.py 5y         # 或指定周期: max / 10y / 5y / 1y / 180(天)
"""
from __future__ import annotations
import sys, time, datetime as dt
from assets import enabled
from db import connect, upsert_price


def yf_history(ticker: str, period: str):
    import yfinance as yf
    h = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    out = []
    for idx, r in h.iterrows():
        out.append((idx.date().isoformat(), r.Open, r.High, r.Low, r.Close, float(r.Volume)))
    return out


def cg_history(coin_id: str, days):
    import requests
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    r = requests.get(url, params={"vs_currency": "usd", "days": days, "interval": "daily"}, timeout=40).json()
    out = []
    for ts, price in r.get("prices", []):
        d = dt.datetime.utcfromtimestamp(ts / 1000).date().isoformat()
        out.append((d, price, price, price, price, 0.0))
    return out


def _cg_days(period: str):
    """yfinance 风格 period -> CoinGecko days。"""
    if period == "max":
        return "max"
    if period.endswith("y"):
        return str(int(period[:-1]) * 365)
    if period.endswith("d"):
        return period[:-1]
    return period  # 纯数字按天


def run(period: str = "max"):
    cg_days = _cg_days(period)
    con = connect()
    for a in enabled():
        src = a["source"]
        if src == "manual":
            continue
        try:
            if src == "yfinance":
                rows = yf_history(a["ticker"], period if not period.isdigit() else f"{int(period)}d")
            elif src == "coingecko":
                rows = cg_history(a["coin_id"], cg_days)
                time.sleep(2)  # CoinGecko 免费限流,温柔点
            else:
                rows = []
            for d, o, h, l, c, v in rows:
                upsert_price(con, d, a["id"], o, h, l, c, v)
            span = f"{rows[0][0]}→{rows[-1][0]}" if rows else "-"
            print(f"  ✓ {a['id']:8} {len(rows):>5} 条  {span}")
        except Exception as e:
            print(f"  ✗ {a['id']:8} {e}")
    n = con.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
    print(f"L0 现有 {n} 条价格记录")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "max")
