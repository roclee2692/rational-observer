# AGENTS.md — Rational Observer 运维手册(给 Hermes 自管自修用)

你(Hermes / Elysia)是这个项目的**运维**。在此目录被调度运行时,按本手册操作并自我修复。
项目定位:只观察/记忆/提醒,**绝不给买卖建议**;日报只呈现事实+涨跌。

## 项目结构
- `config/assets.yaml` — 资产宇宙定义。**注意:这台机器上的真实配置在 `config/assets.local.yaml`(gitignore,程序自动优先读它);`assets.yaml` 只是开源仓库里的通用示例。加减资产/改配比请改 `assets.local.yaml`,勿硬编码。**
- `config/settings.yaml` — 阈值/路径。飞书 chat_id 用环境变量 `OBSERVER_FEISHU_CHAT`(见 `~/.hermes/scripts/weekly_observer.sh`),仓库里 settings.yaml 留空。
- `src/assets.py` 校验 · `src/db.py` L0 库 · `src/ingest.py` 价格采集 · `src/macro.py` 宏观采集
- `src/alerts.py` 异常检测 · `src/memory.py` L1 向量记忆 · `src/daily.py` 日报(串起以上全部)
- `src/ledger.py` L4 预测台账(记录/到期/复盘/准确率,SQLite,见技能 prediction-ledger)
- `src/backfill.py` 历史回填(`backfill.py max` 拉满;指数如 ^GSPC 到 1927) · `src/viz.py` 图表(英文标签→`viz/*.png`,含百年专图 century.png、滚动相关性 rolling_corr.png)
- `src/weekly.py` 周报(生成图+综述+推飞书,用 `hermes send --to feishu:<chat> "MEDIA:<png>"`)
- 定时任务:每日 `rational-observer-daily`(9/21点 daily.py);每周日 `rational-observer-weekly`(21点,跑 `~/.hermes/scripts/weekly_observer.sh`→weekly.py,no-agent)。飞书 chat_id 在 settings.yaml `delivery.feishu_chat`。
- 数据源说明:股票/指数/商品用 yfinance(指数代码 ^GSPC/^IXIC 才有长史,ETF 只到上市)。加密长史用 yfinance 的 `BTC-USD/ETH-USD` 等(CoinGecko 免费版历史封顶,仅适合每日最新价);RENDER 的 RNDR-USD 已停更,长期用 CoinGecko `render-token`。
- L0 日线极小:百年×十几资产≈10万行≈15MB,**永不压缩、放心拉满**(怕膨胀的是向量记忆 L1-L3,不是 L0)。
- `data/ledger.sqlite` 预测台账(勿删) · `viz/` 图表输出(可重生成,不必备份)
- `.venv/` 项目虚拟环境 · `data/observer.duckdb` 时序库(勿删) · `data/l1_*.{json,npy}` L1 记忆(勿删)
- L1 向量记忆依赖本地嵌入模型:`~/.openclaw/workspace/.models/embeddinggemma-300M-Q8_0.gguf`(若缺,L1 会优雅跳过,不影响出报)

## 每天怎么跑(标准动作)
```bash
cd ~/Documents/Projects/rational-observer
.venv/bin/python src/daily.py
```
把它的 stdout 整理成简短中文日报发给我(Raelon)。**只给事实+涨跌,不要买卖建议。**

## 出错了怎么自查自修(按顺序试)
1. **`ModuleNotFoundError` / 缺包** → `.venv/bin/pip install -r requirements.txt`,重跑。
2. **`.venv` 损坏/不存在** → `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`。
3. **配比校验失败("总和≠100%")** → 看 `assets.yaml`,持仓资产 target_pct 总和必须=100;告诉我哪不对,**不要擅自改配比**(那是我的投资决定),只报告。
4. **某资产抓不到数据(yfinance/coingecko)**:
   - yfinance ticker 失效 → 报告该 ticker,建议我换;别瞎改。
   - CoinGecko `coin_id` 错 → 去 coingecko 查正确全小写 id,核对 `assets.yaml`。
   - CoinGecko 限流(429)→ 等 60s 重试一次即可,别狂刷。
5. **DuckDB 锁/损坏** → 确认没有别的进程占用;`data/observer.duckdb` **永不删除**(那是历史事实)。
6. **网络/超时** → 重试一次;仍失败就把当日采到的部分照常出报,并注明哪几个没取到。
7. 连续修复仍失败 → **停下,把错误 + 你已尝试的步骤汇报给我**,不要无限重试(遵守全局无进展硬停)。

## 红线(全局安全规范同样适用)
- `data/` 下的库文件**永不 `rm`**;要删用 safe-delete。
- 不改 `assets.yaml` 里的 `target_pct`(投资决策权在 Raelon),只报告异常。
- 日报里**绝不出现"买入/卖出/加仓/减仓"建议**——只给事实。

## 加资产 / 改配置(我让你做时)
改 `config/assets.local.yaml`(本机真实配置;加密查准 coin_id),保存后 `.venv/bin/python src/assets.py` 校验,通过再说。**不要改 `assets.yaml`**(那是开源示例,改了也不生效)。
