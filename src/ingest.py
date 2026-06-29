"""每日采集 (Job 1, Phase 0 骨架)。
遍历 enabled 资产,按 source 调对应 API,写入 L0 时序库。
观察资产(target=0)同样采集 —— 它们进时序库、可分析,只是不计入组合。
"""
from __future__ import annotations
import datetime as dt
from assets import enabled
from db import connect, upsert_price


def fetch_yfinance(ticker: str):
    import yfinance as yf
    h = yf.Ticker(ticker).history(period="1d")
    if h.empty:
        return None
    r = h.iloc[-1]
    return dict(o=r.Open, h=r.High, l=r.Low, c=r.Close, v=float(r.Volume))


def fetch_coingecko(coin_id: str):
    import requests
    url = "https://api.coingecko.com/api/v3/simple/price"
    r = requests.get(url, params={"ids": coin_id, "vs_currencies": "usd"}, timeout=20).json()
    px = r.get(coin_id, {}).get("usd")
    if px is None:
        return None
    return dict(o=px, h=px, l=px, c=px, v=0.0)  # simple endpoint = close only


def run(today: str | None = None):
    today = today or dt.date.today().isoformat()
    con = connect()
    ok = skip = 0
    for a in enabled():
        src = a["source"]
        if src == "manual":
            continue  # CASH 等手工资产不抓
        try:
            if src == "yfinance":
                d = fetch_yfinance(a["ticker"])
            elif src == "coingecko":
                d = fetch_coingecko(a["coin_id"])
            else:
                d = None
            if d:
                upsert_price(con, today, a["id"], d["o"], d["h"], d["l"], d["c"], d["v"])
                print(f"  ✓ {a['id']:7} {d['c']:.2f}")
                ok += 1
            else:
                print(f"  ⚠ {a['id']:7} 无数据"); skip += 1
        except Exception as e:
            print(f"  ✗ {a['id']:7} {e}"); skip += 1
    print(f"采集完成 {today}: 成功 {ok} / 跳过 {skip}")


if __name__ == "__main__":
    run()
