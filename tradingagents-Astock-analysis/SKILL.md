---
name: tradingagents-Astock-analysis
description: 对A股做21分析师六阶段投研分析并输出结构化决策。
version: 1.0.0
author: simonlin1212 (simonlin1212), Hermes Agent
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [A股, 股票分析, 投研, 21分析师, 六阶段, 多智能体, 权重, 七维, 博弈论, 多空辩论, 风险管控, 交叉验证, 结构化决策, 技术分析, 基本面分析, 资金流向, 龙虎榜, 解禁, 北向资金, 复盘, stock-analysis, A-share, multi-agent, trading]
---

# TradingAgents-Astock-Analysis Skill

本技能让 Hermes 对 A 股标的做**21 名分析师六阶段**多智能体投研分析：用技能自带的免费直连数据脚本
（新浪/腾讯/东财/同花顺/百度 HTTP，零 API key）获取真实数据，由 10 名分析师按七维权重独立研判，
经博弈裁判、多空辩论、交易执行、风险管控后，由独立复核官交叉验证、首席决策官给出
Buy/Hold/Sell 评级与结构化决策。**分析由 Hermes 自己完成，不需要配置或访问任何外部 LLM 服务**。

本技能是原 `tradingagents-astock`（数据 + 七维权重）、`tradingagents-analysis`（15 分析师五阶段）、
`tradingagents-ensemble`（双源交叉验证综合）三者的合并：数据脚本与七维权重、21 名专家六阶段、
多源交叉验证与置信度全部保留，专家数量从 15 增至 21。

**本技能完全自包含**：`scripts/fetch_data.py` 只依赖 Python3 + requests，不依赖任何工程安装——
整个 `skills/tradingagents-Astock-analysis/` 目录拷贝到其他环境即可独立运行。
产出只含方向、评级与理由，不构成投资建议。

## When to Use

- 用户询问股票、A 股、ETF、基金、港股、美股的行情、走势、表现、分析、评估、复盘、持仓、涨跌、资金流向、龙虎榜、解禁、北向资金等话题
- 用户指定某只标的（代码或中文名）要求做投研/分析
- 用户要求板块、概念、行业对比分析；需要批量分析多只标的；对历史日期做回溯分析
- 用户需要 21 分析师级深度投研（覆盖宏观、博弈论、多空辩论、风控、交叉验证全链条）
- 用户需要**长期投资视角**（2-3 年持有）的结构化分析，或短线快速研判（见「短线模式」）
- 用户需要生成结构化投研报告、盘后复盘、持仓标的风险评估，或评估多空逻辑与风险点
- 单一框架结论存疑，需要多维交叉验证确认的场合

**触发关键词**（出现任一即应触发）：
股票、A股、a股、沪深、港股、美股、行情、走势、表现、分析、评估、复盘、持仓、涨跌、涨幅、跌幅、K线、均线、MACD、RSI、量价、资金流、北向、龙虎榜、解禁、限售、股东、财报、估值、PE、PB、龙虎、资金、板块、概念、行业、ETF、基金、选股、推荐、买入、卖出、持有、做空、多空、多头、空头、涨停、跌停、停牌、复牌、减持、增持、北向资金、融资融券、游资、主力、散户、市值、流通市值、总市值、换手率、振幅、支撑位、压力位、三表、一致预期、十大股东、股东户数、筹码、题材、风口、热门、概念板块、市场情绪、舆情、长期、长期投资、长期持有、穿越周期

**注意：**
- **港股/美股**：`fetch_data.py` 的数据脚本仅支持 A 股标的（6 位代码 / 中文名，拒绝 `.HK` / `.US` 代码）。对港股/美股标的，**仍然触发本技能**执行六阶段分析框架，但数据采集会标记「数据获取失败」，Hermes 可基于已有信息（新闻、市场情绪、板块轮动等）补充定性分析。
- **盘中实时盯盘**：数据抓取与推理需要数分钟，不适合实时决策。

## 前提

- Python ≥ 3.10 且已装 `requests`（`terminal(command="pip install requests")`）。
- 数据脚本位于本技能目录下：`scripts/fetch_data.py`。从任意目录用完整路径运行，
  或先 `cd` 到技能目录再运行。以下命令以「技能目录 = `skills/tradingagents-Astock-analysis/`、
  工作目录 = 工程根」为例，实际路径随技能安装位置变化。
- **无需任何 API key 或环境变量。**

## 快速上手

三步完成一次分析：

1. **采集数据**：`terminal(command="python skills/tradingagents-Astock-analysis/scripts/fetch_data.py <6位代码或中文名> [--date YYYY-MM-DD] [--sections ...]")`
2. **六阶段研判**：按「工作流程」执行 21 名分析师六阶段分析（角色细节见 `references/analyst-roles.md`）。
3. **综合决策**：交叉验证后给出结构化 JSON（`decision` / `direction` / `confidence` / `risk_items` 等）与评级。

## 工作流程

1. **确认标的与日期**：6 位代码或中文名（脚本内置新浪 suggest 搜索解析）；分析日期不晚于今天。历史日期分析时，无历史时点值的数据（实时估值、一致预期、北向、最新股东户数）会输出快照告警，**不得当作分析日当天的事实**。
2. **数据采集**：运行 `fetch_data.py`（默认抓全量数据块；`--sections quote,kline,reports,forecast,news,hot_stocks,fundflow,concept,shareholders` 等按需裁剪；`--out file.md` 存盘）。数据块独立容错，单个源失败只标记 `[数据获取失败]` 不中断整体。
3. **阶段一 · 分析团队（10 名）**：按 `references/analyst-roles.md` 由 10 名分析师依七维权重独立研判（经营30% → 政策25% → 估值20% → 资金10% → 技术10%辅助 → 情绪5%辅助 → 解禁并入资金），每个维度给出独立结论并注明依据的数据块。
4. **阶段二 · 博弈裁判**：博弈论管理者判断主力与散户的预期差。
5. **阶段三 · 多空辩论**：多头、空头研究员围绕核心分歧点交锋，裁判逐条裁决并给出综合投资计划。
6. **阶段四 · 交易执行**：交易员在 A 股约束（T+1/涨跌停/手数）下给出交易方案与参考价位区间。
7. **阶段五 · 风险管控**：激进/中性/保守分析师三方审视，组合经理汇总成风险清单与最终评级。
8. **阶段六 · 综合决策**：独立复核官对照权重表交叉验证（一致点 `consistency`、分歧点 `divergence`、置信度 `confidence`），首席决策官输出最终评级与结构化 JSON（见「输出结构」），附免责声明。综合决策细节见 `references/decision-synthesis.md`。

**完成判据**：报告覆盖六阶段与 21 名分析师结论；含多空辩论、风险清单与交叉验证；评级为独立词（`Buy`/`Hold`/`Sell`）；每条理由可追溯到分析师与数据块；JSON 含全部输出字段。

## 输出结构

```json
{
  "decision": "BUY | HOLD | SELL",
  "direction": "看多 | 看空 | 中性",
  "confidence": 0,
  "target_price": null,
  "stop_loss_price": null,
  "risk_items": [
    {"name": "估值偏高", "level": "medium", "description": "当前 PE 处于历史 75 分位"}
  ],
  "key_metrics": [
    {"name": "PE", "value": "20.8x", "status": "neutral"}
  ],
  "final_trade_decision": "综合技术面与基本面，...",
  "consistency": ["①经营+③估值共同确认...", "..."],
  "divergence": ["③估值看空 vs ①经营看多：..."],
  "reasons": [
    {"text": "...", "source": "[①经营+③估值]"}
  ]
}
```

- `target_price` / `stop_loss_price`：由交易员基于支撑/压力位与 ATR 估算，**仅为研究参考，标注不确定性**，不构成操作指令。
- 评级用独立词（`BUY`/`SELL`/`HOLD`），避免 `Buyer interest`、`Sell-off` 这类延续词被误读。
- `confidence`（0-100）由独立复核官给出，多源一致时提高、分歧时降低。
- 报告末尾保留免责声明：内容由 AI 基于公开数据自动生成，仅供研究，不构成投资建议。

## 短线模式

用户说"分析 XX 短线"时：只用 `kline`、`quote`、`fundflow`、`lhb` 数据块，技术窗口 14 天，
跳过财报与解禁，重点放技术面与资金面，速度更快；阶段一可缩减为技术/资金/情绪三个维度重点研判。

## 长期模式

用户说"分析 XX 长期"或提到"长期投资""长期持有"时：启用长期视角（2-3 年持有），
维度权重为经营状态与基本面30% · 政治局势与公司前景25% · 基本面估值20% · 资金面10% ·
技术面10%(辅助) · 情绪面与新闻面5%(辅助)。重点研判：经营竞争力、产业方向、政策前景、成长预期、估值安全边际。
技术面仅作辅助参考。**未说"短线"时默认即长期模式。**

## References

- `references/analyst-roles.md` — 21 名分析师职责、输入数据块与分析要点（含数据块速查表）。
- `references/analysis-framework.md` — 七维权重分配与各维度分析方法、多空辩论、风险管控。
- `references/decision-synthesis.md` — 综合决策：交叉验证（一致/分歧）、置信度、降级处理。
- `references/data-tools.md` — 数据块清单（15 块，全免费 HTTP 零 key）、各数据源的接口/字段/限流、历史日期语义与常用命令。
- `references/a-share-rules.md` — A 股制度语境：代码规则、T+1、涨跌停、龙虎榜、限售解禁、北向资金。

## Quick Reference

（以下命令假设工作目录在工程根、技能目录为 `skills/tradingagents-Astock-analysis/`；技能拷贝到别处时改用实际路径。）

| 目的 | 命令 |
|------|------|
| 单股全量数据（分析日=今天） | `terminal(command="python skills/tradingagents-Astock-analysis/scripts/fetch_data.py 600519")` |
| 中文名 + 历史日期 | `terminal(command="python skills/tradingagents-Astock-analysis/scripts/fetch_data.py 贵州茅台 --date 2026-05-12")` |
| 只抓关键块 | `terminal(command="python skills/tradingagents-Astock-analysis/scripts/fetch_data.py 600519 --sections quote,kline,reports,news")` |
| 基本面+预期视角 | `terminal(command="python skills/tradingagents-Astock-analysis/scripts/fetch_data.py 600519 --sections reports,forecast,shareholders")` |
| 题材热点视角 | `terminal(command="python skills/tradingagents-Astock-analysis/scripts/fetch_data.py 600519 --sections hot_stocks,concept,industry")` |
| 资金+解禁视角 | `terminal(command="python skills/tradingagents-Astock-analysis/scripts/fetch_data.py 600519 --sections fundflow,lhb,lockup,northbound")` |
| 保存为文件 | `terminal(command="python skills/tradingagents-Astock-analysis/scripts/fetch_data.py 600519 --out /tmp/600519_data.md")` |
| 批量多只 | 循环调用脚本（注意东财限流，见 Pitfalls） |
| 21 分析师细节 | `read_file` 本技能 `references/analyst-roles.md` |
| 权重与维度要点 | `read_file` 本技能 `references/analysis-framework.md` |

## Pitfalls

- **只认 A 股**：6 位数字或中文名；港股（如 `00700`）与美股代码会被拒，用其它市场代码会得到看似正常但无意义的结果。
- **历史日期**：实时估值、一致预期、北向资金、最新股东户数等无历史时点值的数据在历史分析时会告警，必须标注为"抓取当下快照"，不得写入分析日事实。
- **财报已公布截断**：`reports` 块按"公告日/入库时间早于分析日，或逾期则按法定披露截止日"判断，宁可晚放不可早放（未来函数防护）。
- **一致预期**：`forecast` 是"当前"机构预测汇总（含每股收益与净利润），无历史快照；机构数 <3 时覆盖不足，谨慎引用。
- **热股题材**：`hot_stocks` 按日期取数但只保留近期交易日（历史太久返回空）；题材是编辑人工标注，解读时注意只反映近期风口。
- **数据块可能失败**：部分源（如东财 push2、财联社）在某些网络/代理环境不可达，脚本会标记该块失败并继续。对失败块换一个等价数据或重试。
- **东财限流**：东财数据默认 ≥1s 间隔节流，批量抓多只时设 `EM_MIN_INTERVAL=1.5~2` 降速，避免临时封 IP。
- **涨跌停/T+1 语境**：涨停封死、跌停无法卖出会扭曲当日量价，解读时结合 `references/a-share-rules.md`。
- **北向资金**：仅实时快照，无历史日度序列（上游 2024-08 起停止更新），历史分析时不可用。
- **权重纪律**：高权重维度（经营30%/政策25%/估值20%）决定评级方向，辅助维度（技术/情绪）结论不得反向压过；权重与评级相悖时必须解释。
- **多源确认 vs 同源缺失**：21 名专家共用同一份抓取数据，某数据块失败时多个专家会同时缺该块——不要误把"同源缺失"当"多源确认"。
- **目标价/止损是估算**：基于支撑压力与 ATR，仅研究参考，不构成操作指令。
- **免责**：分析由 AI 基于公开数据生成，仅供研究，不构成投资建议；输出应保留免责声明。

## Verification

1. 独立运行自检（从**工程外**目录执行，验证自包含）：`terminal(command="cd /tmp && python <技能目录>/scripts/fetch_data.py 600519 --sections quote --out /tmp/_smoke.md")` 产出含 `Name:` 的非空文件。
2. 中文名解析：`terminal(command="python <技能目录>/scripts/fetch_data.py 贵州茅台 --sections quote")` 输出 `Name: 贵州茅台`。
3. 数据块可用性：`terminal(command="python <技能目录>/scripts/fetch_data.py 600519 --sections forecast,hot_stocks,shareholders")` 输出应含"一致预期 · 每股收益"、题材列表与"十大股东"。
4. 报告结构：按「工作流程」产出的报告含六阶段、21 名分析师结论、多空辩论、风险清单、交叉验证与评级；JSON 含全部输出字段；每条理由可追溯到分析师与数据块。
