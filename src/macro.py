"""宏观指标采集 → L0 macro_indicators 表。
VIX(恐慌)/ DXY(美元)/ US10Y(美债收益率)—— 训练宏观直觉、驱动警报。
"""
from __future__ import annotations
import datetime as dt
from db import connect

# indicator -> yfinance ticker
INDICATORS = {
    "VIX": "^VIX",        # 恐慌指数
    "DXY": "DX-Y.NYB",    # 美元指数
    "US10Y": "^TNX",      # 美债10年收益率(注意是 x10 的报价)
}


def run(today: str | None = None):
    import yfinance as yf
    today = today or dt.date.today().isoformat()
    con = connect()
    ok = 0
    for name, ticker in INDICATORS.items():
        try:
            h = yf.Ticker(ticker).history(period="1d")
            if h.empty:
                print(f"  ⚠ {name} 无数据"); continue
            val = float(h.iloc[-1].Close)
            con.execute(
                "INSERT OR REPLACE INTO macro_indicators VALUES (?,?,?)",
                [today, name, val],
            )
            print(f"  ✓ {name:6} {val:.2f}")
            ok += 1
        except Exception as e:
            print(f"  ✗ {name:6} {e}")
    print(f"宏观采集 {today}: {ok}/{len(INDICATORS)}")


if __name__ == "__main__":
    run()
