# Rational Observer · 理性观察者

[![CI](https://github.com/roclee2692/rational-observer/actions/workflows/ci.yml/badge.svg)](https://github.com/roclee2692/rational-observer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Not Financial Advice](https://img.shields.io/badge/⚠️-not%20financial%20advice-red.svg)](#disclaimer)

> A resident, purely rational **"observer version of you"** — it watches the markets you have no time to watch, remembers the changes you have no time to track, and surfaces accumulated understanding when you need it.
> **Not a trading bot. Not a prediction engine.** A tool to **expand your cognitive bandwidth**.
>
> 一个常驻的、纯理性的「观察者版本的你」——替你看你没时间看的市场,记你没时间记的变化,在你需要时把积累的认知呈现给你。**不是交易机器人,不是预测系统**,而是**扩展你认知带宽**的工具。

**[English](#english) · [中文](#中文)**

---

## English

### What it is

Rational Observer is a long-running agent that **observes / remembers / reminds / tracks** — and never decides. The decision is always yours; the system only gives you **facts + state**, never "buy / sell" signals.

Four design principles: **lossless data · layered memory · decisions leave a trail · cognition is auditable.**

### Architecture at a glance

```
Interaction (Feishu)  →  Agent scheduling (Hermes/Haiku)  →  Analysis  →  Memory  →  Ingestion
Layered memory:
  L0  Time-series (DuckDB)     facts, never compressed     — prices / indicators
  L1  Journal   (vector DB)    full text kept 90 days
  L2  Weekly    (vector DB)    kept 1 year
  L3  Themes    (vector DB)    narrative threads, forever
  L4  Prediction ledger (SQLite)  forecast + outcome + review, forever — the core of cognitive iteration
```

The single most important idea: **separate facts from understanding.** Prices/indicators (facts) are never compressed and live in L0. News interpretation/narrative (understanding) can be compressed and lives in L1–L3. Mixing the two is how ~90% of agent memory systems fail. Full design in [`docs/architecture.md`](docs/architecture.md).

### Memory layers

| Layer | Store | Content | Policy |
|---|---|---|---|
| L0 raw | DuckDB | daily OHLCV + macro indicators | never compress / delete |
| L1 journal | vector DB | daily brief (~200 chars) | full text, 90 days |
| L2 weekly | vector DB | weekly threads + key changes (~300 chars) | 1 year |
| L3 themes | vector DB | long narrative threads (e.g. "USD weakening") | forever |
| L4 ledger | SQLite | prediction + reasoning + confidence + outcome + review | forever |

### Layout

```
config/   assets.yaml (the asset universe · single source of truth) + settings.yaml (thresholds)
src/      assets.py (registry + validator)  db.py (L0 schema + period returns)  ingest.py (price job)
          macro.py  alerts.py  memory.py (L1 vectors)  daily.py  weekly.py  ledger.py (L4)  viz.py  backfill.py
tests/    pytest suite — assets validator / alerts engine / period returns
data/     runtime databases (gitignored — your data never leaves your machine)
viz/      chart output (PNG)
docs/     architecture
```

### Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/assets.py     # 1) validate the asset config — ALWAYS the first step
python src/db.py         # 2) init the L0 time-series store
python src/ingest.py     # 3) ingest today's data once
```

**`assets.yaml` is always step one** — it is the single source of truth. Add any asset by editing the YAML only; never touch code.

### Everyday use

```bash
.venv/bin/python src/daily.py                 # full daily pipeline (ingest → brief → alerts → 1D/7D/30D returns)
.venv/bin/python src/memory.py search "how have markets been lately"   # semantic recall over L1
.venv/bin/python src/ledger.py add "..." --reason "..." --conf 6 --target 2026-09-16   # log a prediction
.venv/bin/python src/ledger.py stats          # prediction accuracy by category / confidence
.venv/bin/python src/backfill.py 180          # backfill history into L0
.venv/bin/python src/viz.py                   # render charts → viz/*.png
```

### Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v        # 65 tests: assets validator, alerts engine, period returns
```

Tests use in-memory DuckDB — no network, no local embedding model, fully deterministic. CI runs them on Python 3.11 / 3.12 on every push.

### Roadmap

- **Phase 0 ✅** assets.yaml + validator + L0 time-series + price ingest + Feishu daily report (cron 09:00 / 21:00)
- **Phase 1 ✅** macro ingest (VIX/DXY/US10Y) + anomaly alerts (VIX>30 / daily move >3% / allocation drift) + L1 vector memory (local embeddings, semantic recall)
- **L4 ledger ✅** record predictions → compare against L0 at maturity → review → accuracy curves. Turns "pain + reflection = progress" into a measurable thing.
- **Phase 2 ✅** visualization (normalized / correlation / **rolling correlation** / volatility / drawdown / **century S&P chart**) + history backfill (S&P 1927, NASDAQ 1971, BTC 2014; L0 ~100k rows ≈ 15MB) + **auto-push weekly chart pack to Feishu** (Sundays 21:00)
- **Hardening ✅** tamper-proof config validator (survives `python -O`), **multi-period returns (1D/7D/30D)** in the daily report, and the project's first **test suite (65 cases) + CI**
- **Phase 3** L2/L3 layered compression (weekly → thematic narrative)

### What makes it different

Layered memory (FinMem), holdings tracking (Ghostfolio/Wealthfolio), and vector memory (Mem0) each exist separately. The unique combination here is **a non-deciding rational observer + fact/understanding separation + L3 narrative memory + L4 prediction ledger + compounding cognition.** Borrow parts from those projects; the positioning is different.

### Disclaimer

**NOT FINANCIAL ADVICE.** This software observes, remembers, and reminds. It does not give buy/sell signals, place orders, or make decisions. Markets carry risk; every decision is yours. Provided "as is" under the [MIT License](LICENSE).

---

## 中文

### 它是什么

理性观察者是一个常驻 agent,只做四件事:**观察 / 记忆 / 提醒 / 追踪**——永不决策。决策永远是你做的;系统只给你**事实 + 状态**,绝不出现"买/卖"信号。

四条设计原则:**数据无损 · 记忆分层 · 决策留痕 · 认知可追溯。**

### 架构一览

```
交互层 (飞书)  →  Agent 调度 (Hermes/Haiku)  →  分析层  →  记忆层  →  采集层
记忆分层:
  L0 时序库(DuckDB)    事实,永不压缩      —— 价格/指标
  L1 日志(向量库)      保留 90 天全文
  L2 周报(向量库)      保留 1 年
  L3 主题(向量库)      叙事线,永久
  L4 预测台账(SQLite)  预测+结果+复盘,永久 —— 认知迭代核心
```

最重要的一条:**事实 vs 理解 分离。** 价格/指标(事实)永不压缩,存 L0;新闻解读/叙事(理解)可分层压缩,存 L1–L3。两者混在一起,是 ~90% agent 记忆系统失败的根源。完整设计见 [`docs/architecture.md`](docs/architecture.md)。

### 记忆分层

| 层 | 存储 | 内容 | 策略 |
|---|---|---|---|
| L0 原始 | DuckDB | 每日 OHLCV + 宏观指标 | 永不压缩/删除 |
| L1 日志 | 向量库 | 每日简报(~200字) | 全文保留 90 天 |
| L2 周报 | 向量库 | 本周主线+关键变化(~300字) | 保留 1 年 |
| L3 主题 | 向量库 | 长期叙事线(如"美元走弱进程") | 永久 |
| L4 台账 | SQLite | 预测+理由+置信度+结果+复盘 | 永久 |

### 目录

```
config/   assets.yaml(资产宇宙·唯一定义) + settings.yaml(阈值)
src/      assets.py(注册表+校验)  db.py(L0 schema + 多期收益)  ingest.py(价格采集)
          macro.py  alerts.py  memory.py(L1向量)  daily.py  weekly.py  ledger.py(L4)  viz.py  backfill.py
tests/    pytest 测试套件 —— 资产校验器 / 异常引擎 / 多期收益
data/     运行时数据库(gitignore —— 你的数据永不离开本机)
viz/      图表输出(PNG)
docs/     架构文档
```

### 快速开始

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/assets.py     # 1) 校验资产配置 —— 永远是第一步
python src/db.py         # 2) 初始化 L0 时序库
python src/ingest.py     # 3) 采集一次当日数据
```

**第一步永远是 `assets.yaml`** —— 它是单一事实来源,加任何资产只改它,不碰代码。

### 日常使用

```bash
.venv/bin/python src/daily.py                 # 全流程(采集→简报→警报→1D/7D/30D 收益)
.venv/bin/python src/memory.py search "最近市场怎样"     # L1 语义检索
.venv/bin/python src/ledger.py add "..." --reason "..." --conf 6 --target 2026-09-16   # 记预测
.venv/bin/python src/ledger.py stats          # 按类别/置信度看准确率
.venv/bin/python src/backfill.py 180          # 回填历史到 L0
.venv/bin/python src/viz.py                   # 出图 → viz/*.png
```

### 测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -v        # 65 个测试:资产校验器、异常引擎、多期收益
```

测试用内存 DuckDB 构造数据 —— 不联网、不跑本地嵌入、完全确定。CI 在每次 push 时于 Python 3.11 / 3.12 上运行。

### 路线图

- **Phase 0 ✅** assets.yaml + 校验 + L0 时序库 + 价格采集 + 飞书日报(cron 每天 9:00/21:00)
- **Phase 1 ✅** 宏观采集(VIX/DXY/US10Y) + 异常警报(VIX>30 / 单日>3% / 配比漂移) + L1 向量记忆(本地嵌入,语义检索)
- **L4 预测台账 ✅** 记录预测 → 到期对照 L0 → 复盘 → 准确率曲线。把"痛苦+反思=进步"量化。
- **Phase 2 ✅** 可视化(归一化/相关性/**滚动相关性**/波动率/回撤/**标普百年图**) + 历史回填(标普1927、纳指1971、BTC2014;L0 ~10万行≈15MB) + **周报自动推图到飞书**(每周日 21:00)
- **加固 ✅** 防篡改校验器(`python -O` 下仍生效)、日报里的**多期收益(1D/7D/30D)**,以及项目首个**测试套件(65 例)+ CI**
- **Phase 3** L2/L3 分层压缩(周报→主题叙事)

### 它和开源社区的区别

分层记忆(FinMem)、持仓追踪(Ghostfolio/Wealthfolio)、向量记忆(Mem0)单独都有,但「**不决策的理性观察者 + 事实/理解分离 + L3 叙事记忆 + L4 预测台账 + 认知复利**」这个组合与理念是独特的。可借鉴这些项目的部件,但定位不同。

### 免责声明

**本项目不构成任何投资建议。** 它只观察、记忆、提醒,不给买卖信号、不下单、不做决策。市场有风险,每一个决定都由你做出。按 [MIT 许可证](LICENSE) "按原样"提供。
