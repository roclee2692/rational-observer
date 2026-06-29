"""L1 理解层 —— 每日简报的向量记忆,可语义检索 (架构第四节)。
本地 embeddinggemma 嵌入(离线、无 key)。L1 = 近期日志;后续 L2/L3 同机制。

  python memory.py add "2026-06-16" "今日简报全文..."
  python memory.py search "最近市场怎样" [k]
"""
from __future__ import annotations
import sys, os, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.path.expanduser("~/.openclaw/workspace/.models/embeddinggemma-300M-Q8_0.gguf")
META = ROOT / "data" / "l1_meta.json"
VEC = ROOT / "data" / "l1_vectors.npy"

DOC = lambda t: f"title: none | text: {t}"
QRY = lambda q: f"task: search result | query: {q}"


def _llm():
    from llama_cpp import Llama
    return Llama(model_path=MODEL, embedding=True, n_ctx=2048, verbose=False)


def _embed(llm, text: str) -> np.ndarray:
    e = llm.embed(text)
    if isinstance(e[0], list):
        e = np.mean(np.array(e), axis=0)
    v = np.array(e, dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def add(date: str, text: str, level: str = "L1"):
    meta = json.loads(META.read_text()) if META.exists() else []
    # 同 date+level 去重(覆盖)
    meta = [m for m in meta if not (m["date"] == date and m["level"] == level)]
    vecs = list(np.load(VEC)) if VEC.exists() else []
    if vecs and len(meta) != len(vecs):
        vecs = vecs[: len(meta)]  # 对齐(防漂移)
    llm = _llm()
    meta.append({"date": date, "level": level, "text": text})
    vecs.append(_embed(llm, DOC(text)))
    np.save(VEC, np.vstack(vecs))
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"✓ {level} 记忆已存 {date}({len(meta)} 条)")


def search(query: str, k: int = 3, level: str | None = None):
    if not META.exists():
        print("(无记忆)"); return
    meta = json.loads(META.read_text())
    mat = np.load(VEC)
    idx_all = [i for i, m in enumerate(meta) if level is None or m["level"] == level]
    if not idx_all:
        print("(无匹配层级)"); return
    llm = _llm()
    q = _embed(llm, QRY(query))
    sims = mat[idx_all] @ q
    order = np.argsort(-sims)[:k]
    for j in order:
        i = idx_all[j]
        print(f"[{meta[i]['level']} {meta[i]['date']}] ({sims[j]:.3f})")
        print("  " + meta[i]["text"].replace("\n", " ")[:120])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "add":
        add(sys.argv[2], sys.argv[3])
    elif cmd == "search":
        search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3)
    else:
        print(__doc__)
