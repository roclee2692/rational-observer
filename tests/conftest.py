"""Pytest 共享配置:让 ``src/`` 包内的模块可以直接 ``import assets``。

项目历史上一直把 src 当作 sys.path 加入 (见 src/alerts.py 等的 ``from db import …``)。
测试沿用同样约定即可。
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
