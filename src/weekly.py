"""周报 (Job 3) —— 生成图表 + 本周综述,推送到飞书。
deterministic,无需 LLM。每周日由 cron 触发。
"""
from __future__ import annotations
import subprocess, datetime as dt, os, shutil
from pathlib import Path
import yaml

HERMES = shutil.which("hermes") or os.path.expanduser("~/.local/bin/hermes")
import viz
from db import connect
from assets import load_assets, held

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "config" / "settings.yaml"
# 周报推送的图(按重要性)
CHARTS = ["normalized.png", "correlation.png", "rolling_corr.png", "century.png"]


def _target():
    """飞书推送目标。优先环境变量 OBSERVER_FEISHU_CHAT,其次 settings.yaml。
    都为空则返回 None(不推送,只本地生成图表)。"""
    chat = os.environ.get("OBSERVER_FEISHU_CHAT", "").strip()
    if not chat:
        s = yaml.safe_load(open(SETTINGS, encoding="utf-8")) or {}
        chat = ((s.get("delivery") or {}).get("feishu_chat") or "").strip()
    return f"feishu:{chat}" if chat else None


def _pct_7d(con, asset_id):
    rows = con.execute(
        "SELECT close FROM daily_prices WHERE asset_id=? ORDER BY date DESC LIMIT 6", [asset_id]
    ).fetchall()
    if len(rows) < 2:
        return None
    now, week_ago = rows[0][0], rows[-1][0]
    return (now - week_ago) / week_ago * 100 if week_ago else None


def summary() -> str:
    con = connect()
    names = {a["id"]: a.get("name", a["id"]) for a in load_assets()}
    today = dt.date.today().isoformat()
    lines = [f"📈 周报 · {today}", "", "【持仓·近5日变动】"]
    moves = []
    for a in held():
        p = _pct_7d(con, a["id"])
        if p is not None:
            moves.append((a["id"], p))
            lines.append(f"  {names.get(a['id'], a['id'])}: {p:+.1f}%")
    if moves:
        best = max(moves, key=lambda x: x[1]); worst = min(moves, key=lambda x: x[1])
        lines += ["", f"本周最强 {names.get(best[0],best[0])} {best[1]:+.1f}% · "
                      f"最弱 {names.get(worst[0],worst[0])} {worst[1]:+.1f}%"]
    lines += ["", "📊 附图:归一化对比 / 相关性 / 滚动相关性 / 标普百年",
              "— 仅事实呈现,决策在你 ✨"]
    return "\n".join(lines)


def send(target, text=None, media=None):
    args = [HERMES, "send", "--to", target]
    msg = f"MEDIA:{media}" if media else text
    subprocess.run(args + [msg], check=False)


def run():
    print("生成图表 ..."); viz.generate_all()
    tgt = _target()
    if not tgt:
        print("⚠ 未配置飞书 chat(OBSERVER_FEISHU_CHAT 或 settings.yaml delivery.feishu_chat)"
              " —— 只本地生成图表,跳过推送。")
        print(summary())
        return
    print("推送文字综述 ..."); send(tgt, text=summary())
    for c in CHARTS:
        p = ROOT / "viz" / c
        if p.exists():
            print(f"推送 {c} ..."); send(tgt, media=str(p))
    print("✓ 周报已推送")


if __name__ == "__main__":
    run()
