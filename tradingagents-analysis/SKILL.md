---
name: tradingagents-analysis
description: 对A股做15分析师五阶段投研分析并输出结构化决策。
version: 1.0.0
author: simonlin1212 (simonlin1212), Hermes Agent
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [A股, 股票分析, 投研, 15分析师, 五阶段, 多智能体, 博弈论, 多空辩论, 风险管控, 结构化决策, stock-analysis, A-share, trading]
    related_skills: [tradingagents-astock]
---

# TradingAgents-Analysis Skill

本技能让 Hermes **扮演 15 名 AI 分析师**，按五阶段框架（分析团队 → 博弈裁判 → 多空辩论 → 交易执行 → 风险管控）对 A 股标的做深度投研，最终输出**结构化决策 JSON**（decision / direction / confidence / target_price / stop_loss_price / risk_items / key_metrics / final_trade_decision）。

数据获取全部来自**免费直连的公开 HTTP 接口**（复用同仓库 `tradingagents-astock` 技能的自包含数据脚本），**零 API key、零托管服务、零 token**。

## When to Use

- 用户要求对 A 股做 15 分析师级深度投研（覆盖宏观、博弈论、多空辩论、风控全链条）
- 需要**结构化决策输出**（评级 + 置信度 + 目标价/止损 + 风险项 + 关键指标）
- 盘后复盘、持仓标的风险评估
- 短线快速研判（14 天窗口、跳过财报，见「短线模式」）

**Don't use for:**
- 非 A 股市场（数据层拒绝非 A 股代码）
- 盘中实时盯盘（完整分析需数分钟）
- 仅查行情/单维度数据（直接用 `tradingagents-astock` 的数据脚本即可）

## 前提

- Python ≥ 3.10 且已装 `requests`。
- 同仓库的 `tradingagents-astock` 技能可用（本技能数据层依赖它的 `scripts/fetch_data.py`；拷贝时两个技能目录一起拷贝）。
- **无需任何 API key 或环境变量。**

## 数据获取

复用 `tradingagents-astock` 的免费直连脚本：

```bash
python <astock技能目录>/scripts/fetch_data.py <6位代码或中文名> [--date YYYY-MM-DD] [--sections ...] [--lookback N]
```

默认抓全量数据块。15 个分析师各自使用哪些数据块见 `references/analyst-roles.md`。
数据接口细节（字段、限流、历史日期语义）见 `tradingagents-astock/references/data-tools.md`。

## 工作流程

1. **提取标的与日期**：6 位代码或中文名；日期不晚于今天（历史分析时注意快照告警）。
2. **数据采集**：运行上述脚本获取全量数据素材（或按分析需要裁剪 `--sections`）。
3. **阶段一 · 分析团队**：6 名分析师（市场/新闻/情绪/基本面/宏观/聪明钱）各自基于数据独立产出报告，每份注明依据的数据块。
4. **阶段二 · 博弈裁判**：博弈论管理者判断主力与散户的预期差。
5. **阶段三 · 多空辩论**：多头、空头研究员交锋，裁判逐条裁决并给出综合投资计划。
6. **阶段四 · 交易执行**：交易员在 A 股约束（T+1/涨跌停/手数）下给出交易方案与参考价位区间。
7. **阶段五 · 风险管控**：激进/中性/保守分析师三方审视，组合经理汇总成风险清单与最终评级。
8. **输出结构化决策**：聚合为下述 JSON，附免责声明。

**完成判据**：五阶段报告齐全；输出 JSON 含全部 8 个字段；评级与方向一致；每个论据可追溯到数据块；风险项逐条有数据或事实支撑。

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
  "final_trade_decision": "综合技术面与基本面，..."
}
```

- `target_price` / `stop_loss_price`：由交易员基于支撑/压力位与 ATR 估算，**仅为研究参考，标注不确定性**，不构成操作指令。
- 评级用独立词（`BUY`/`SELL`/`HOLD`），避免 `Buyer interest`、`Sell-off` 这类延续词被误读。
- 报告末尾保留免责声明：内容由 AI 基于公开数据自动生成，仅供研究，不构成投资建议。

## 短线模式

用户说"分析 XX 短线"时：只用 `kline`、`quote`、`fundflow`、`lhb` 数据块，技术窗口 14 天，
跳过财报与解禁，重点放技术面与资金面，速度更快。

## References

- `references/analyst-roles.md` — 15 名分析师职责、输入数据块与分析要点（含数据块速查表）。
- 数据层细节：`tradingagents-astock/references/data-tools.md`（接口/限流/历史语义）、`tradingagents-astock/references/a-share-rules.md`（A 股制度语境）。

## Quick Reference

| 目的 | 动作 |
|------|------|
| 数据采集 | `terminal(command="python <astock技能目录>/scripts/fetch_data.py <标的>")` |
| 只看关键块 | `terminal(command="python <astock技能目录>/scripts/fetch_data.py <标的> --sections kline,quote,fundflow,lhb")` |
| 15 分析师细节 | `read_file` 本技能 `references/analyst-roles.md` |
| 短线模式 | 用户说"短线"时按上节执行 |

## Pitfalls

- **数据层依赖**：本技能本身不含数据脚本，依赖同仓库 `tradingagents-astock` 的 `fetch_data.py`；单独拷贝时务必两个技能目录一起拷贝。
- **历史日期**：实时估值、北向等无历史时点值的数据会快照告警，不得当作分析日事实；财报按"已公布"截断。
- **东财限流**：批量抓多只时设 `EM_MIN_INTERVAL=1.5~2` 降速。
- **目标价/止损是估算**：基于支撑压力与 ATR 的参考值，非操作指令；输出时标注不确定性。
- **数据块失败**：部分源在网络受限环境不可达，脚本会标记失败并继续；对失败块换等价数据或重试。
- **免责**：分析由 AI 基于公开数据生成，仅供研究，不构成投资建议。

## Verification

1. 数据可用：`terminal(command="python <astock技能目录>/scripts/fetch_data.py 600519 --sections quote,kline")` 产出非空数据。
2. 结构完整：对同一标的跑完五阶段，确认输出 JSON 含 `decision`/`direction`/`confidence`/`target_price`/`stop_loss_price`/`risk_items`/`key_metrics`/`final_trade_decision` 全部字段。
3. 口径一致：`decision` 与 `direction` 一致；每条理由与风险可追溯到具体数据块。
