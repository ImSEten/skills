# A 股数据工具参考

数据获取由本技能自带的 `scripts/fetch_data.py` 完成：仅依赖 Python3 + `requests`，
免费直连新浪/腾讯/东财/同花顺/百度等公开 HTTP 接口，**零 API key、零工程依赖**。
把整个 `skills/tradingagents-astock/` 目录拷贝到任何环境即可独立运行。

## 前提与运行

- `terminal(command="pip install requests")`。
- 运行：`terminal(command="python <技能目录>/scripts/fetch_data.py <标的> [--date YYYY-MM-DD] [--sections ...] [--lookback N] [--out file.md]")`。
- 标的可为 6 位代码、带前缀代码（`sh600519`）或中文名（内置新浪 suggest 搜索解析）。
- 数据块独立容错：单个源失败只输出 `[数据获取失败] ...`，不影响其余块。

## 数据块清单

| 数据块 | 内容 | 数据源 |
|--------|------|--------|
| `overview` | 名称 + 实时行情/估值 | 腾讯 qt.gtimg.cn |
| `quote` | 实时行情/估值：价格、涨跌幅、PE(TTM)/静态 PE、PB、市值、换手率、涨跌停价 | 腾讯 qt.gtimg.cn |
| `kline` | 日 K 线 OHLCV（CSV） | 新浪 CN_MarketData |
| `reports` | 财报三表（资产负债表/利润表/现金流量表），科目 × 最近 4 期转置，按已公布截断 | 新浪 FinanceReport |
| `forecast` | 机构一致预期：每股收益 + 净利润预测汇总（年度/机构数/最小/均值/最大/行业平均） | 同花顺 worth 页 |
| `news` | 个股新闻（标题/摘要/链接），按时间窗口过滤 | 东财搜索（新浪兜底） |
| `global_news` | 财经快讯 | 财联社 + 东财 7x24 |
| `hot_stocks` | 热门强势股题材：当日涨停/强势股 + 编辑人工标注题材原因 + 题材热度 TOP15 | 同花顺 涨停事件库 |
| `lhb` | 龙虎榜：上榜记录、买卖席位 TOP5、机构动向 | 东财 datacenter |
| `lockup` | 限售解禁：历史记录 + 未来 90 天待解禁 | 东财 datacenter |
| `shareholders` | 股东动态：十大股东、十大流通股东（按报告期截断）+ 最新股东户数（含变动/筹码集中度） | 东财 datacenter |
| `industry` | 全行业涨跌排名（涨跌前 N） | 东财 push2 |
| `fundflow` | 个股资金流：实时分钟（主力/大单/超大单）+ 历史日线 20 交易日（按分析日截断） | 东财 push2/push2his |
| `concept` | 行业/概念/地域板块归属 + 当日涨跌 | 百度股市通 |
| `northbound` | 北向资金实时（沪深股通累计净买入） | 同花顺 hsgtApi |

说明：以上数据块全部来自**免费直连的公开 HTTP 接口，零 API key**。原工程中依赖
mootdx TCP 的**同花顺 EPS 一致预期、热门强势股题材**已改用同花顺公开 HTTP 接口
（`basic.10jqka.com.cn` worth 页 / `zx.10jqka.com.cn` 涨停事件库）；**股东 F10 动态**
改用东财 datacenter 的股东研究报表（替代 mootdx F10 股东研究）。分析时用上述块即可覆盖，
无需任何 TCP 服务或密钥。

## 历史日期语义（重要）

- 指定 `--date`（早于今天）时：
  - `kline`/`news`/`lhb`/`lockup`/`industry` 按日期范围取数。
  - `reports` 按"已公布"截断：公告日或入库时间早于分析日才出现；原始日期丢失时
    按法定披露截止日（一季报/三季报 +1 个月、半年报 +2 个月、年报 +4 个月）判断，
    **宁可晚放不可早放**（未来函数防护）。
  - `fundflow` 略去实时分钟段（那是今天的盘中数据），历史日线截断到分析日。
  - `shareholders` 的十大股东/流通股东按报告期（`END_DATE`）截断到分析日；
    股东户数只有"最新一期"，历史分析日输出**快照告警**。
  - `hot_stocks` 按日期取数（同花顺涨停事件库保留近期交易日），日期太早会返回空。
  - `quote`/`forecast`/`northbound` 等无历史时点值的数据输出**快照告警**，必须视为
    "抓取当下的快照"，**不得当作分析日当天的事实**写入报告。

## 限流与批量

- 所有指向东方财富的请求统一走内置节流（串行 ≥1s + 0.1~0.5s 随机抖动 + 会话复用），
  多标的连续抓取不会触发临时封 IP。`shareholders`（3 个东财报表）和 `lhb`/`lockup`
  一样走该入口。
- 批量场景设环境变量 `EM_MIN_INTERVAL=1.5~2` 进一步降速。
- 其余源（新浪/腾讯/同花顺/百度）不限流；批量循环时建议每只之间 sleep 1~2s。
- 同花顺 worth 页与涨停事件库是 HTML/JSON 直连，无鉴权；若返回空或 403，多为
  网络/代理环境问题，重试或换等价数据块。

## 常见组合

| 场景 | 命令 |
|------|------|
| 单股全量数据 | `python <技能目录>/scripts/fetch_data.py 600519` |
| 中文名 + 历史日期 | `python <技能目录>/scripts/fetch_data.py 贵州茅台 --date 2026-05-12` |
| 只看关键块 | `python <技能目录>/scripts/fetch_data.py 600519 --sections quote,kline,reports,news` |
| 基本面+预期视角 | `python <技能目录>/scripts/fetch_data.py 600519 --sections reports,forecast,shareholders` |
| 题材热点视角 | `python <技能目录>/scripts/fetch_data.py 600519 --sections hot_stocks,concept,industry` |
| 资金+解禁视角 | `python <技能目录>/scripts/fetch_data.py 600519 --sections fundflow,lhb,lockup,northbound` |
| 保存为文件 | `python <技能目录>/scripts/fetch_data.py 600519 --out /tmp/600519_data.md` |
