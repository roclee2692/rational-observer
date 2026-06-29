"""L4 预测台账 (架构第八节) —— 记录你的预测+结果+复盘,迭代判断力。
纯 SQLite(无额外依赖)。判断对错由 agent 结合 L0 实际走势完成,这里只管存取。

  ledger.py add "预测内容" --reason "理由" --conf 6 --target 2026-09-16 [--cat macro]
  ledger.py list [pending|reviewed|all]
  ledger.py due [today]                      # 到期待复盘
  ledger.py review <id> <correct|wrong|partial> "复盘文字"
  ledger.py stats                            # 准确率(总/按类别/按置信度)
"""
from __future__ import annotations
import sys, argparse, datetime as dt, sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "ledger.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_date DATE, prediction TEXT, reasoning TEXT,
    confidence INTEGER, category TEXT,
    target_date DATE, outcome TEXT, review TEXT,
    status TEXT DEFAULT 'pending'
);
"""


def con():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB); c.execute(SCHEMA); return c


def add(prediction, reasoning, confidence, target_date, category="general"):
    c = con()
    cur = c.execute(
        "INSERT INTO predictions(created_date,prediction,reasoning,confidence,category,target_date,status)"
        " VALUES(?,?,?,?,?,?,'pending')",
        [dt.date.today().isoformat(), prediction, reasoning, int(confidence), category, target_date],
    )
    c.commit()
    print(f"✓ 预测 #{cur.lastrowid} 已记录,到期 {target_date}(置信度 {confidence}/10, 类别 {category})")


def show(status="all"):
    c = con()
    q = "SELECT id,created_date,target_date,confidence,category,status,outcome,prediction FROM predictions"
    if status in ("pending", "reviewed"):
        q += f" WHERE status='{status}'"
    q += " ORDER BY target_date"
    rows = c.execute(q).fetchall()
    if not rows:
        print("(无记录)"); return
    for r in rows:
        oid, cd, td, cf, cat, st, oc, pred = r
        mark = {"correct": "✅", "wrong": "❌", "partial": "◐", None: "⏳"}.get(oc, "⏳")
        print(f"#{oid} {mark} [{cat}] 置信{cf} 立{cd}→到期{td} {st}")
        print(f"    {pred}")


def due(today=None):
    today = today or dt.date.today().isoformat()
    c = con()
    rows = c.execute(
        "SELECT id,created_date,target_date,prediction,reasoning FROM predictions"
        " WHERE status='pending' AND target_date<=? ORDER BY target_date", [today],
    ).fetchall()
    if not rows:
        print("(无到期待复盘的预测)"); return rows
    print(f"📌 {len(rows)} 条预测到期待复盘:")
    for oid, cd, td, pred, reason in rows:
        print(f"#{oid} (立于{cd}, 到期{td}) {pred}  | 当初理由: {reason}")
    return rows


def review(pid, outcome, text):
    assert outcome in ("correct", "wrong", "partial"), "outcome 必须是 correct/wrong/partial"
    c = con()
    c.execute("UPDATE predictions SET outcome=?,review=?,status='reviewed' WHERE id=?", [outcome, text, pid])
    c.commit()
    print(f"✓ 预测 #{pid} 复盘已记录: {outcome}")


def stats():
    c = con()
    done = c.execute("SELECT outcome,confidence,category FROM predictions WHERE status='reviewed'").fetchall()
    if not done:
        print("尚无已复盘预测,无法统计准确率。"); return
    def acc(rows):
        n = len(rows); good = sum(1 for o, *_ in rows if o == "correct")
        part = sum(1 for o, *_ in rows if o == "partial")
        return f"{good}/{n} 全对 + {part} 部分对 = {(good+0.5*part)/n*100:.0f}% 加权准确率"
    print(f"总体: {acc(done)}")
    from collections import defaultdict
    bycat = defaultdict(list); byconf = defaultdict(list)
    for o, cf, cat in done:
        bycat[cat].append((o,)); byconf["高(7-10)" if cf >= 7 else "中低(1-6)"].append((o,))
    print("按类别:"); [print(f"  {k}: {acc(v)}") for k, v in bycat.items()]
    print("按置信度:"); [print(f"  {k}: {acc(v)}") for k, v in byconf.items()]
    print("\n💡 若'高置信度'准确率反而不高 → 过度自信(Kahneman),需校准。")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add"); a.add_argument("prediction"); a.add_argument("--reason", default="")
    a.add_argument("--conf", type=int, default=5); a.add_argument("--target", required=True); a.add_argument("--cat", default="general")
    l = sub.add_parser("list"); l.add_argument("status", nargs="?", default="all")
    d = sub.add_parser("due"); d.add_argument("today", nargs="?", default=None)
    r = sub.add_parser("review"); r.add_argument("id", type=int); r.add_argument("outcome"); r.add_argument("text")
    sub.add_parser("stats")
    args = p.parse_args()
    if args.cmd == "add": add(args.prediction, args.reason, args.conf, args.target, args.cat)
    elif args.cmd == "list": show(args.status)
    elif args.cmd == "due": due(args.today)
    elif args.cmd == "review": review(args.id, args.outcome, args.text)
    elif args.cmd == "stats": stats()
    else: print(__doc__)
