---
name: tradingagents-ensemble
description: 股票/金融分析时并行调用两个A股投研技能并综合结论。
version: 0.1.0
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

- `tradingagents-astock`（本地）：免费直连数据 + Hermes 自研七维研判，零 API key。
- `tradingagents-analysis`（托管 API）：15 名 AI 分析师五阶段分析，需 `TRADINGAGENTS_TOKEN`。

两个来源视角不同（本地数据 + 自研推理 vs 托管多智能体），一致点增强置信，分歧点暴露盲区。

## When to Use

- 用户要求对 A 股标的做投研分析、买卖判断、风险评估、盘后复盘
- 需要本地数据分析和托管 AI 分析师**双视角交叉验证**的场合
- 单一技能结论存疑，需要第二来源确认

**Don't use for:**
- 只需要快速查行情/单维度数据（直接用 `tradingagents-astock` 的数据脚本即可）
- 非 A 股市场（两个子技能都只支持沪深 A 股）
- 盘中实时盯盘（整套分析需数分钟）

## 前提

- 两个子技能均可用：`tradingagents-astock`（Python3 + requests）、`tradingagents-analysis`（`TRADINGAGENTS_TOKEN` 已配置）。
- 本技能不重复两者的操作细节——执行时分别遵循两个子技能的指引。

## 工作流程

1. **统一输入**：从对话提取标的（6 位代码或中文名）与分析日期（默认今天）。两个子技能用同一输入。
2. **并行执行两个来源**：
   - **来源 A（本地，tradingagents-astock）**：按该技能流程抓数据并完成七维研判，产出评级（Buy/Hold/Sell）+ 方向 + 理由 + 风险清单。
   - **来源 B（托管 API，tradingagents-analysis）**：提交分析任务并轮询（1-5 分钟，用后台运行），产出 decision/direction/confidence/risk_items/key_metrics。
   - 建议：先后台提交 B，轮询期间完成 A，最后取 B 结果。
3. **结果对齐**：统一口径——评级映射到 Buy/Hold/Sell；方向映射到看多/看空/中性；理由与风险项逐条列出，标注来源。
4. **对比分析**：
   - **一致点**：两个来源共同支持的判断（含共同风险），列为"双源确认"。
   - **分歧点**：列出差异及可能原因（数据时点差异、视角差异、API 数据缺失等），不掩盖分歧。
5. **综合结论**：输出
   - `final_decision`（Buy/Hold/Sell）+ `direction` + `confidence`（0-100，双源一致时提高，分歧时降低）
   - `consistency`（双源一致点）、`divergence`（分歧点）
   - `reasons`：每条标注 `[本地]` / `[API]` / `[双源]`
   - `risk_items`：合并两个来源的风险清单（去重，注明来源）
   - 附免责声明。
6. **降级处理**（任一来源不可用时不中断）：
   - B 缺 token / API 不可达 → 只用 A，结论标注"单一来源（本地）"。
   - A 数据抓取失败 → 只用 B，标注"单一来源（API）"。
   - 两者都不可用 → 停止并告知用户需要哪个前置条件。

**完成判据**：综合报告包含两个来源各自的结论、一致点清单、分歧点清单、最终评级与置信度；每个理由/风险都注明来源；降级时明确标注单一来源。

## Quick Reference

| 目的 | 动作 |
|------|------|
| 加载两个子技能 | `skill_view("tradingagents-astock")` + `skill_view("tradingagents-analysis")` |
| 本地数据+研判（来源 A） | 按 astock 技能：`python <astock目录>/scripts/fetch_data.py <标的>` → 七维分析 |
| 托管 API 分析（来源 B） | 按 analysis 技能：`bash <analysis目录>/scripts/analyze.sh <标的>`（后台运行） |
| 综合输出 | 按上方「工作流程」第 3-5 步 |

## Pitfalls

- **两套评级口径**：本地用 Buy/Hold/Sell，API 用 BUY/SELL/HOLD + confidence + target_price/stop_loss。综合时统一到 Buy/Hold/Sell，不直接拼接。
- **耗时差异**：API 分析 1-5 分钟（轮询间隔 ≥15s）；本地数据+推理数分钟。先提交 API 再跑本地可隐藏等待。
- **时点差异**：两个来源的数据抓取时间不同，实时值（北向、资金流、估值）可能不一致；以较新者为准并注明。
- **API 无 token 时**：analysis 技能自带无令牌降级路径，但编排器按上述第 6 步处理即可，不要让单一来源的失败阻塞整体。
- **免责**：综合结论同样只给方向/评级/理由，不构成投资建议；输出保留免责声明。

## Verification

1. 单源自检：两个子技能各自能跑通（见各自技能的 Verification）。
2. 双源对比：对同一标的（如 `600519`）分别取得两来源结论，确认都能解析出评级与理由。
3. 综合完整性：输出含 `consistency`、`divergence`、`final_decision`、带来源标注的 `reasons` 与 `risk_items`。
