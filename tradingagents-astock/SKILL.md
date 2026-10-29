---
name: tradingagents-astock
description: 对A股做多智能体投研分析：数据采集、七维研判、多空辩论与风险评级。
version: 0.4.0
author: simonlin1212 (simonlin1212), Hermes Agent
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [A股, 股票分析, 投研, 多智能体, 技术分析, 基本面分析, 资金流向, 龙虎榜, 解禁, 北向资金, 复盘, stock-analysis, A-share, multi-agent, trading]
---

# TradingAgents-Astock Skill

本技能让 Hermes 对 A 股标的做多智能体投研分析：用技能自带的免费直连数据脚本（新浪/腾讯/东财/同花顺/百度 HTTP，零 API key）获取真实数据，按七个维度独立研判，经多空辩论与风险管控后给出 Buy/Hold/Sell 评级与理由。**分析由 Hermes 自己完成，不需要配置或访问任何外部 LLM 服务**。

**本技能完全自包含**：`scripts/fetch_data.py` 只依赖 Python3 + requests，不依赖任何工程安装——整个 `skills/tradingagents-astock/` 目录拷贝到其他环境即可独立运行。产出只含方向、评级与理由，不构成投资建议。

## When to Use

- 用户要求对 A 股标的做投研/分析（技术面/基本面/情绪/资金/政策/解禁任一维度或整体）
- 需要 A 股行情、财报、龙虎榜、资金流、北向资金、新闻、解禁等真实数据
- 需要生成结构化投研报告或盘后复盘
- 需要批量分析多只标的，或对历史日期做回溯分析
- 需要评估某只 A 股的多空逻辑与风险点

**Don't use for:**
- 港股/美股等非 A 股标的（脚本拒绝 4~5 位数字 / `.HK` 代码）
- 盘中实时盯盘或分钟级决策（数据抓取与推理需要数分钟）
- 需要 15 分析师五阶段框架或结构化决策输出（含目标价/止损）时，用同仓库的 `tradingagents-analysis` 技能；需要双来源交叉验证时，用 `tradingagents-ensemble`

## 前提

- Python ≥ 3.10 且已装 `requests`（`terminal(command="pip install requests")`）。
- 数据脚本位于本技能目录下：`scripts/fetch_data.py`。从任意目录用完整路径运行，
  或先 `cd` 到技能目录再运行。以下命令以「技能目录 = `skills/tradingagents-astock/`、
  工作目录 = 工程根」为例，实际路径随技能安装位置变化。

## 快速上手

三步完成一次分析：

1. **采集数据**：`terminal(command="python skills/tradingagents-astock/scripts/fetch_data.py <6位代码或中文名> [--date YYYY-MM-DD] [--sections ...]")`
2. **七维研判**：按 `references/analysis-framework.md` 逐维度分析数据。
3. **辩论 + 风控 + 评级**：给出多空辩论、风险清单与 Buy/Hold/Sell 评级及理由。

## 工作流程

1. **确认标的与日期**：6 位代码或中文名（脚本内置新浪 suggest 搜索解析）；分析日期不晚于今天。历史日期分析时，无历史时点值的数据（实时估值、一致预期、北向、最新股东户数）会输出快照告警，**不得当作分析日当天的事实**。
2. **数据采集**：运行 `fetch_data.py`（默认抓全量数据块；`--sections quote,kline,reports,forecast,news,hot_stocks,fundflow,concept,shareholders` 等按需裁剪；`--out file.md` 存盘）。数据块独立容错，单个源失败只标记 `[数据获取失败]` 不中断整体。
3. **七维独立研判**（`references/analysis-framework.md`）：
   - 技术面（K线）→ 情绪面（新闻/热股题材）→ 新闻面（新闻/快讯）→ 基本面（行情估值/财报三表/一致预期/股东结构）→ 政策面（快讯/行业/概念）→ 资金面（资金流/北向/龙虎榜/概念）→ 解禁面（解禁/新闻）。
   - 每个维度给出独立结论，并注明依据哪个数据块。
4. **多空辩论**：围绕核心分歧点分别以多头、空头立场论证、互相反驳，给出阶段性裁决。
5. **风险管控**：以激进/保守/中立三方视角审视，输出风险清单（风险点 + 级别 + 描述）。
6. **综合决策**：输出 `Buy` / `Hold` / `Sell` 评级 + 方向 + 2~5 条可追溯理由 + 高风险项，附免责声明。

**完成判据**：报告覆盖七个维度、含多空辩论与风险清单；评级为独立词（`Buy`/`Hold`/`Sell`，避免 `Buyer interest`、`Sell-off` 这类延续词）；每条理由可追溯到数据块。

## References

- `references/data-tools.md` — 数据块清单（15 块，全免费 HTTP 零 key）、各数据源的接口/字段/限流、历史日期语义与常用命令。
- `references/analysis-framework.md` — 七维度分析方法、多空辩论、风险管控与最终输出格式。
- `references/a-share-rules.md` — A 股制度语境：代码规则、T+1、涨跌停、龙虎榜、限售解禁、北向资金。

## Quick Reference

（以下命令假设工作目录在工程根、技能目录为 `skills/tradingagents-astock/`；技能拷贝到别处时改用实际路径。）

| 目的 | 命令 |
|------|------|
| 单股全量数据（分析日=今天） | `terminal(command="python skills/tradingagents-astock/scripts/fetch_data.py 600519")` |
| 中文名 + 历史日期 | `terminal(command="python skills/tradingagents-astock/scripts/fetch_data.py 贵州茅台 --date 2026-05-12")` |
| 只抓关键块 | `terminal(command="python skills/tradingagents-astock/scripts/fetch_data.py 600519 --sections quote,kline,reports,news")` |
| 基本面+预期视角 | `terminal(command="python skills/tradingagents-astock/scripts/fetch_data.py 600519 --sections reports,forecast,shareholders")` |
| 题材热点视角 | `terminal(command="python skills/tradingagents-astock/scripts/fetch_data.py 600519 --sections hot_stocks,concept,industry")` |
| 保存为文件 | `terminal(command="python skills/tradingagents-astock/scripts/fetch_data.py 600519 --out /tmp/600519_data.md")` |
| 批量多只 | 循环调用脚本（注意东财限流，见 Pitfalls） |

## Pitfalls

- **只认 A 股**：6 位数字或中文名；港股（如 `00700`）与美股代码会被拒，用其它市场代码会得到看似正常但无意义的结果。
- **历史日期**：实时估值、一致预期、北向资金、最新股东户数等无历史时点值的数据在历史分析时会告警，必须标注为"抓取当下快照"，不得写入分析日事实。
- **财报已公布截断**：`reports` 块按"公告日/入库时间早于分析日，或逾期则按法定披露截止日"判断，宁可晚放不可早放（未来函数防护）。
- **一致预期**：`forecast` 是"当前"机构预测汇总（含每股收益与净利润），无历史快照；机构数 <3 时覆盖不足，谨慎引用。
- **热股题材**：`hot_stocks` 按日期取数但只保留近期交易日（历史太久返回空）；题材是编辑人工标注，含当日涨停/强势股，解读时注意只反映近期风口。
- **数据块可能失败**：部分源（如东财 push2、财联社）在某些网络/代理环境不可达，脚本会标记该块失败并继续。对失败块换一个等价数据（如资金流失败则用 K线+新闻推断）或重试。
- **东财限流**：东财数据默认 ≥1s 间隔节流，批量抓多只时设 `EM_MIN_INTERVAL=1.5~2` 降速，避免临时封 IP。
- **涨跌停/T+1 语境**：涨停封死、跌停无法卖出会扭曲当日量价，解读时结合 `references/a-share-rules.md`。
- **北向资金**：仅实时快照，无历史日度序列（上游 2024-08 起停止更新），历史分析时不可用。
- **免责**：分析由 AI 基于公开数据生成，仅供研究，不构成投资建议；输出应保留免责声明。

## Verification

1. 独立运行自检（从**工程外**目录执行，验证自包含）：`terminal(command="cd /tmp && python <技能目录>/scripts/fetch_data.py 600519 --sections quote --out /tmp/_smoke.md")` 产出含 `Name:` 的非空文件。
2. 中文名解析：`terminal(command="python <技能目录>/scripts/fetch_data.py 贵州茅台 --sections quote")` 输出 `Name: 贵州茅台`。
3. 新增块可用性：`terminal(command="python <技能目录>/scripts/fetch_data.py 600519 --sections forecast,hot_stocks,shareholders")` 输出应含"一致预期 · 每股收益"、题材列表与"十大股东"。
4. 报告结构：按「工作流程」产出的报告含七维研判、多空辩论、风险清单与评级。
