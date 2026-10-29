---
name: tradingagents-ensemble
description: 股票/金融分析时并行调用两个A股投研技能并综合结论。
version: 0.2.0
author: simonlin1212 (simonlin1212), Hermes Agent
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [A股, 股票分析, 投研, 多技能综合, ensemble, 交叉验证, 买卖建议, stock-analysis, A-share, trading]
    related_skills: [tradingagents-astock, tradingagents-analysis]
---

# TradingAgents Ensemble Skill

本技能是**编排器**：当用户要求对 A 股/金融标的做投研分析时，同时运行两个独立的 A 股投研技能，把两者的结论对齐、对比、交叉验证，最终输出**综合结论**——而不是只依赖其中任何一个。

- `tradingagents-astock`：免费直连数据 + Hermes 七维研判，产出 Buy/Hold/Sell 评级与理由。
- `tradingagents-analysis`：免费直连数据 + Hermes 扮演 15 名分析师五阶段研判，产出结构化决策（含置信度、目标价/止损、风险项、关键指标）。

两个来源的**分析视角不同**（七维框架 vs 15 分析师五阶段框架），数据均来自同一套免费直连脚本——一致点增强置信，分歧点暴露盲区。全程**零 API key、零托管服务**。

## When to Use

- 用户询问股票、A 股、ETF、基金、港股、美股的行情、走势、表现、分析、评估、复盘、持仓、涨跌、资金流向、龙虎榜、解禁、北向资金等话题
- 用户要求对 A 股标的做投研分析、买卖判断、风险评估、盘后复盘
- 用户需要**两个独立分析框架交叉验证**的场合（七维 vs 15 分析师）
- 单一技能结论存疑，需要第二套框架确认

**触发关键词**（出现任一即应触发）：
股票、A股、a股、沪深、港股、美股、行情、走势、表现、分析、评估、复盘、持仓、涨跌、涨幅、跌幅、K线、均线、MACD、RSI、量价、资金流、北向、龙虎榜、解禁、限售、股东、财报、估值、PE、PB、龙虎、资金、板块、概念、行业、ETF、基金、选股、推荐、买入、卖出、持有、做空、多空、多头、空头、涨停、跌停、停牌、复牌、减持、增持、北向资金、融资融券、游资、主力、散户、市值、流通市值、总市值、换手率、振幅、支撑位、压力位、三表、一致预期、十大股东、股东户数、筹码、题材、风口、热门、概念板块、市场情绪、舆情

**注意：**
- **港股/美股**：两个子技能（astock + analysis）的数据脚本均仅支持 A 股。对非 A 股标的，仍触发本技能执行双源分析框架，但数据层会标记失败，Hermes 可基于已有信息交叉分析。
- **盘中实时盯盘**：整套分析需数分钟，不适合实时决策。
- **只需要快速查行情/单维度数据**时，直接用 `tradingagents-astock` 的数据脚本即可

## 前提

- Python ≥ 3.10 且已装 `requests`。
- 三个技能目录一起拷贝（`tradingagents-ensemble` + `tradingagents-astock` + `tradingagents-analysis`）——数据脚本在 astock 技能内，另两个技能数据层依赖它。
- 本技能不重复两者的操作细节——执行时分别遵循两个子技能的指引。

## 工作流程

1. **统一输入**：从对话提取标的（6 位代码或中文名）与分析日期（默认今天）。
2. **抓取一次数据**：`terminal(command="python <astock目录>/scripts/fetch_data.py <标的> [--date ...]")` 获取全量数据素材，两个来源复用同一份数据。
3. **并行执行两套分析**：
   - **来源 A（tradingagents-astock）**：按该技能流程做七维研判 + 多空辩论 + 风控，产出评级（Buy/Hold/Sell）+ 方向 + 理由 + 风险清单。
   - **来源 B（tradingagents-analysis）**：按该技能流程扮演 15 名分析师完成五阶段研判，产出结构化 JSON（decision/direction/confidence/target_price/stop_loss_price/risk_items/key_metrics/final_trade_decision）。
4. **结果对齐**：统一口径——B 的 decision（BUY/SELL/HOLD）映射到 Buy/Hold/Sell；方向映射到看多/看空/中性；理由与风险项逐条列出并标注来源（`[A]` 七维 / `[B]` 15分析师）。
5. **对比分析**：
   - **一致点**：两套框架共同支持的判断（含共同风险），列为"双源确认"。
   - **分歧点**：列出差异及可能原因（框架侧重不同、数据块缺失、时点差异等），不掩盖分歧。
6. **综合结论**：输出
   - `final_decision`（Buy/Hold/Sell）+ `direction` + `confidence`（0-100，双源一致时提高，分歧时降低）
   - `consistency`（双源一致点）、`divergence`（分歧点）
   - `reasons`：每条标注 `[A]` / `[B]` / `[双源]`
   - `risk_items`：合并两来源风险清单（去重，注明来源）；B 的 target/stop 仅作参考并标注不确定性
   - 附免责声明。
7. **降级处理**（任一来源不可用时不中断）：
   - 数据脚本不可用（网络受限/缺依赖）→ 两套分析都无法取数，停止并告知所需前置条件。
   - 某一套分析流程无法完成（如时间/上下文限制）→ 只用另一套，结论标注"单一来源"。
   - 两者都不可用 → 停止并说明原因。

**完成判据**：综合报告包含两套框架各自的结论、一致点清单、分歧点清单、最终评级与置信度；每个理由/风险都注明来源；降级时明确标注单一来源。

## Quick Reference

| 目的 | 动作 |
|------|------|
| 加载两个子技能 | `skill_view("tradingagents-astock")` + `skill_view("tradingagents-analysis")` |
| 抓数据（一次，两套分析复用） | `terminal(command="python <astock目录>/scripts/fetch_data.py <标的>")` |
| 来源 A：七维研判 | 按 astock 技能流程（`references/analysis-framework.md`） |
| 来源 B：15 分析师五阶段 | 按 analysis 技能流程（`references/analyst-roles.md`） |
| 综合输出 | 按上方「工作流程」第 4-6 步 |

## Pitfalls

- **两套评级口径**：来源 A 用 Buy/Hold/Sell，来源 B 用 BUY/SELL/HOLD + confidence + target_price/stop_loss。综合时统一到 Buy/Hold/Sell，不直接拼接。
- **数据同源**：两套分析共用同一份抓取数据，数据块失败时两套分析同一块都会缺失——不要误把"同源缺失"当"双源确认"。
- **时点差异**：若两套分析在不同时间抓数据，实时值（北向、资金流、估值）可能不一致；以较新者为准并注明。
- **B 的目标价/止损是估算**：基于支撑压力与 ATR，仅研究参考，不构成操作指令。
- **免责**：综合结论只给方向/评级/理由，不构成投资建议；输出保留免责声明。

## Verification

1. 单源自检：两个子技能各自能跑通（见各自技能的 Verification）。
2. 双源对比：对同一标的（如 `600519`）分别完成两套分析，确认都能解析出评级与理由。
3. 综合完整性：输出含 `consistency`、`divergence`、`final_decision`、带来源标注的 `reasons` 与 `risk_items`。
