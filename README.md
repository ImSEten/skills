# Hermes Skills

本仓库存放可直接装入 Hermes（或兼容 Agent Skills 规范的环境）使用的技能包。
每个技能完全自包含：拷贝对应技能目录到任意环境的技能目录即可运行，不依赖本仓库之外的其他工程。

## 技能列表

| 技能 | 说明 |
|------|------|
| [tradingagents-astock](tradingagents-astock/SKILL.md) | A 股多智能体投研分析：免费直连数据（新浪/腾讯/东财/同花顺/百度）+ 七维度研判 + 多空辩论 + 风险评级。仅依赖 Python3 + `requests`，零 API key。 |
| [tradingagents-analysis](tradingagents-analysis/SKILL.md) | A 股 15 分析师五阶段投研：Hermes 扮演 15 名分析师（分析团队→博弈→多空辩论→交易→风控），免费直连数据，输出结构化决策（零 API key、零托管服务）。 |
| [tradingagents-ensemble](tradingagents-ensemble/SKILL.md) | 编排技能：股票/金融分析时并行运行两个免费直连投研技能（七维研判 + 15 分析师框架），对齐口径、对比一致与分歧，综合给出结论。 |

## 目录结构

每个技能一个独立目录，遵循统一结构：

```
<skill-name>/
├── SKILL.md          # 技能入口：触发条件（When to Use）、工作流程、快速参考、Pitfalls、Verification
├── references/       # 参考文档：分析方法、数据工具说明、领域规则
└── scripts/          # 可执行脚本（自包含，只依赖标准库 + requests）
```

## 安装使用

将技能目录拷贝到目标环境的技能目录，例如：

```bash
# Hermes 用户技能目录
cp -r tradingagents-astock ~/.hermes/skills/

# 或拷贝到工程的 skills/ 目录
cp -r tradingagents-astock /path/to/project/skills/
```

技能目录内通过 `SKILL.md` 的 frontmatter（`name` / `description`）被自动识别与索引。

## 开发约定

- `SKILL.md` 遵循 Hermes 技能规范：frontmatter 含 `name`、`description`（≤60 字符）、`version`、`author`、`license`、`platforms`、`metadata.hermes.tags`。
- `scripts/` 下的脚本必须自包含：除 `requests` 等常用库外不依赖任何工程代码，便于跨环境直接运行。
- 提交前清理 `__pycache__/`、`*.pyc` 等 Python 工件（见 `.gitignore`）。

## 许可证

Apache-2.0
