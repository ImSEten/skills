# Hermes Skills

本仓库存放可直接装入 Hermes（或兼容 Agent Skills 规范的环境）使用的技能包。
技能完全自包含：拷贝技能目录到任意环境的技能目录即可运行，不依赖本仓库之外的其他工程。

## 技能列表

| 技能 | 说明 |
|------|------|
| [tradingagents-Astock-analysis](tradingagents-Astock-analysis/SKILL.md) | A 股 21 分析师六阶段投研：免费直连数据（新浪/腾讯/东财/同花顺/百度，15 数据块零 key）+ 七维权重研判 + 博弈裁判 + 多空辩论 + 交易执行 + 风险管控 + 交叉验证综合决策，输出结构化 JSON（零 API key、零托管服务）。 |

> 合并自原 `tradingagents-astock`（数据脚本 + 七维权重）、`tradingagents-analysis`（15 分析师五阶段）、
> `tradingagents-ensemble`（双源交叉验证综合）三个技能，专家数量增至 21 名、六阶段流水线。

## 目录结构

技能使用统一结构：

```
<skill-name>/
├── SKILL.md          # 技能入口：触发条件（When to Use）、工作流程、快速参考、Pitfalls、Verification
├── references/       # 参考文档：分析方法、专家角色、综合决策、数据工具说明、领域规则
└── scripts/          # 可执行脚本（自包含，只依赖标准库 + requests）
```

## 安装使用

将技能目录拷贝到目标环境的技能目录，例如：

```bash
# Hermes 用户技能目录
cp -r tradingagents-Astock-analysis ~/.hermes/skills/

# 或拷贝到工程的 skills/ 目录
cp -r tradingagents-Astock-analysis /path/to/project/skills/
```

技能目录内通过 `SKILL.md` 的 frontmatter（`name` / `description`）被自动识别与索引。

## 开发约定

- `SKILL.md` 遵循 Hermes 技能规范：frontmatter 含 `name`、`description`（≤60 字符）、`version`、`author`、`license`、`platforms`、`metadata.hermes.tags`。
- `scripts/` 下的脚本必须自包含：除 `requests` 等常用库外不依赖任何工程代码，便于跨环境直接运行。
- 提交前清理 `__pycache__/`、`*.pyc` 等 Python 工件（见 `.gitignore`）。

## 许可证

Apache-2.0
