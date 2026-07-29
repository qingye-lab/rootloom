<p align="center">
  <img src="plugins/rootloom/assets/icon.svg" width="112" alt="Rootloom 标志">
</p>

<h1 align="center">Rootloom</h1>

<p align="center">
  <strong>把 Codex 的代码修改，变成可检查的工程过程。</strong>
</p>

<p align="center">
  一个本地 OpenAI Codex 插件：找到真正该改的位置、<br>
  控制修改范围，并说清楚到底验证了什么。
</p>

<p align="center">
  <a href="https://liyanqing90.github.io/rootloom/">项目网站</a> · <strong>简体中文</strong> · <a href="README.md">English</a>
</p>

<p align="center">
  <a href="https://github.com/liyanqing90/rootloom/actions/workflows/ci.yml"><img src="https://github.com/liyanqing90/rootloom/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/liyanqing90/rootloom?color=6D5EF7" alt="MIT 许可证"></a>
  <a href="https://github.com/liyanqing90/rootloom/releases"><img src="https://img.shields.io/github/v/release/liyanqing90/rootloom?display_name=tag&amp;sort=semver" alt="最新版本"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-39B98F" alt="Python 3.11+">
</p>

<p align="center">
  <img src="assets/rootloom-xiaohei-loom-zh.png" width="1000" alt="Rootloom 用证据、范围和测试，把风险、缺陷与项目上下文织成经过验证的修改">
</p>

## Rootloom 是什么？

Rootloom 是一个运行在本地的 OpenAI Codex 插件。它不是另一个 Coding Agent，也不会取代编辑器、测试或 CI。它只暴露四个 Skills：修改、审查、项目指导和设置。高风险治理与机器证据是 Change 的内部模式，不再是额外公共入口。

你仍然用自然语言描述任务。Rootloom 改变的是 Codex 处理任务的顺序：

1. 动手前先读仓库和项目规则；
2. 判断风险，划定合理范围；
3. 遇到缺陷时，从现象追到真正拥有这段行为的边界；
4. 只做解决问题所需的完整修改；
5. 验证主路径、核心不变量，以及一条相邻路径；
6. 说明实际执行了哪些命令、结果如何，还有什么没有被证明。

多数任务只需要这样调用：

```text
$operating-coding-change
修复重连竞态，并验证重连、正常断开和取消路径。
```

## 为什么需要它？

Coding Agent 很擅长生成“看上去合理”的补丁。但看上去合理，不等于改对了、方便审查，也不等于任务真的完成了。

| 常见问题 | Rootloom 要求 Codex 换一种做法 |
| --- | --- |
| 在离报错最近的地方补一个分支 | 找到真正拥有这段行为的组件 |
| 一直修改，直到某个测试通过 | 先说清范围，并保护无关的现有工作 |
| 只测最顺利的一条路径 | 同时检查主路径、核心不变量和相邻的异常或替代路径 |
| 笼统地说“测试通过了” | 列出真正执行过的命令和每条命令的结果 |
| 把退出码 0 当作完成证明 | 命令结束后再检查范围、仓库状态和证据是否发生变化 |
| 每个任务都套上重流程 | 日常修改保持轻量，只在确实影响决策时启用深度证据 |

它带来的价值很具体：更少在错误层级打补丁，Diff 更小，审查更清楚，完成声明也能被复核。

> Rootloom 让工作过程更容易检查。它不会让模型永远正确，也不会把“测试通过”变成正确性的证明。

## 快速开始

你需要支持插件的 Codex CLI 或桌面端、Git，以及 Python 3.11+。

### 1. 安装插件

```bash
codex plugin marketplace add liyanqing90/rootloom
codex plugin add rootloom@rootloom
```

两条命令完成后插件即安装完毕。

### 2. 新建一个 Codex 任务

Codex 会在任务开始时发现插件 Skills。无需项目配置、后台进程，也不用单独运行 Rootloom CLI。

### 3. 直接提出任务

```text
$operating-coding-change
Worker 在取消后仍能重连，最终会出现两个活跃 Session。
请找到原因，在不修改公开 API 的前提下修复，并运行相关测试。
```

一份有用的完成报告，应当明确回答四个问题：

```text
原因    行为从哪里产生？破坏了什么不变量？
修改    哪些文件和行为发生了变化？
验证    真正运行了哪些命令？每条命令证明了什么？
风险    还有哪些内容没有验证，或仍然存在不确定性？
```

这就是 Rootloom 的日常用法。你不需要先生成证据包，不需要安装全局配置，也不必把插件里的每个 Skill 都跑一遍。

## 按任务选择工作流

| 你希望 Codex…… | 使用 | 适用场景 |
| --- | --- | --- |
| 实现、修复、重构、迁移、部署或生成严格证据 | `$operating-coding-change` | 唯一修改入口；自动路由 Direct、Scoped、Governed、Evidence 与 External Action |
| 只审查 Diff、PR、Migration 或设计，不修改文件 | `$operating-code-review` | 你需要结论与证据，而不是补丁 |
| 创建、刷新、精炼或检查仓库 `AGENTS.md` | `$project-guidance` | 项目命令或持久不变量需要长期保留 |
| 安装、升级、检查或回滚可选全局设置 | `$setup-rootloom` | 你需要跨项目指导或 Autonomy Rules |

Rootloom Core 始终只展示这四个入口。Change 只有在风险和证据模式需要时，
才按需加载治理、外部动作、验证或 Evidence Reference。
当仓库指导要求检查时，Project Guidance 可以自动执行只读 Validate；持久化 Seed、
Refresh 或 Refine 则需要用户明确意图。仓库只能通过独立且精确的
`<!-- rootloom:refine-once version=1 -->` Marker 授权对该文件进行一次 Refine；
自然语言说明本身绝不授权写入。

## 一次日常修改会怎样进行

```text
你的请求
   ↓
仓库证据与项目规则
   ↓
风险 + 范围
   ↓
缺陷的根因 / 功能的预期行为
   ↓
聚焦的修改
   ↓
基于行为的验证
   ↓
有证据支撑的完成报告
```

处理缺陷时，Rootloom 会推动 Codex 建立一条明确的因果链：

```text
现象 → 触发条件 → 行为归属边界 → 被破坏的不变量 → 根因
```

处理新功能时，它不会硬编一个“根因”，而是明确预期行为和归属边界。验证也从实际改变的行为出发，而不是随手选择一条最容易运行的测试命令。

## 为什么“命令通过”仍然不够

Rootloom 在开发自身时遇到过一个很典型的例子：一条验证命令成功退出，却在运行过程中创建了新的、被 Git 忽略的 `.env`，还把其中的合成值复制进普通文件。命令通过了，但被审查的仓库状态已经不再相同。

验证后的再次采集发现了变化：敏感路径被隔离，变化内容没有进入补丁包，Strict Review 返回失败，而不是给出一份“已经完成”的通过声明。

完整过程和可执行回归记录在[命令通过了，审查仍然失败](docs/case-studies/passing-command-failed-review.zh-CN.md)中。

## 需要更强证据时

多数任务应该留在普通的“编辑—测试”路径上。需要可复现的本地记录时，
明确要求 `$operating-coding-change` 使用 Evidence Mode。

这条可选证据路径可以绑定：

- 修改前的 Git 与仓库状态；
- 允许和禁止修改的路径；
- 行为声明与真正执行过的命令；
- 验证完成后的第二次仓库采集；
- 机器观察结果与人工语义判断。

最终会生成包含补丁、测试日志和机器可读摘要的本地 Bundle。它是一份可检查的审查记录，不是安全证明，也不是不可篡改的审计系统。精确合同参见[架构](docs/architecture.zh-CN.md)与[成熟度和保证](docs/maturity.zh-CN.md)。

对于常见的严格 Intake → 编辑 → Finalize 流程，`resources/evidence/orchestrate_evidence.py`
提供 `prepare` 与 `finish`。它组合现有 Intake、Sealed Contract 和 Finalizer，不改变
它们的 Wire Format；`finish` 仍要求显式确认已完成语义审查。这是单验证命令的便捷路径；
多 Target 或专用命令、迁移、Mixed-version、安全边界以及 Build + Runtime 证据使用底层生命周期。

<details>
<summary><strong>技术合同速查</strong></summary>

Rootloom 4 Core 仍是**面向 Codex 的可检查个人工程工作流。** 公共入口固定为
Change、Review、Project Guidance 和 Setup。Optional Autonomy 通过 Setup 安装；
确定性 Evidence 是显式 Change 模式。Experimental Project Memory 已拆为独立插件，
当前仓库证据始终优先。

显式 Evidence 路径使用 `resources/evidence/analyze_change.py` 做建议式分析。
`analyze_change.py --write-baseline` 可写 Analyzer-only 证据；治理 Intake 则通过
`seal_contract.py` 发布精确合同。Strict Review 使用 `--strict`；机器消费方应读取
`quality_status` 与稳定能力字段 `evidence_complete`。`REVIEW_EVIDENCE_COMPLETE`
表示证据链完整，`REVIEW_REQUIRED_WITH_REDACTIONS` 表示材料脱敏阻止了这一声明。

Core Reset v2 会记录实际 Codex 完成回合的 Token 用量、精确 Mode/Reference 路由以及
隔离的重复运行。结构性缩减可用于开发期间，但正式 4.1 候选需要至少三轮的已评分 v2
矩阵；详见[4.1 效率决策](docs/decisions/2026-07-29-rootloom-4.1-efficiency-loop.md)。
Direct 与 Scoped 是自包含的 Routine 路由，不加载 Reference；Governed 与 Evidence
只在相应模式成立时加载详细合同。
使用 `make core-reset-release-eval CORE_RESET_RESULTS=/absolute/path/results-v2.json`
执行该正式门禁。
仓库保留的 [4.1.0 候选报告](evals/core-reset/reports/4.1.0.md)记录了全部 126 个 Cell：
此前两项效率失败均已修复，但一次 Governed 路由漏读与两项轻微质量评分回退使完整门禁
继续失败关闭。版本 Tag Workflow 会运行这份保留结果。

仓库状态只有在**连续两次有界采集**一致后才会被接受；每个采集生命周期受 `--max-capture-seconds` 约束。任何**材料元数据变化**——包括**新发现的 Ignored 新增**——都会在普通内容采集前启用仅元数据隔离。分类使用 `is_sensitive_material_path`；Rootloom 不是内容感知型 Secret Scanner。

`--reviewable-path` 是 Intake-only 的精确文件声明。它会拒绝 Ignored 文件、Symlink、Hardlink、歧义重复项、强秘密材料，以及标记为 `assume-unchanged` 或 `skip-worktree` 的 Git 条目。Summary 中的 `reviewability_policy` 会记录精确路径与 `policy_provenance`；历史声明不再符合当前策略时，会在读取内容前返回 `reintake-required`。

Evidence 与 Bundle 路径必须同时位于仓库 Worktree 和解析后的 Git Common Directory 之外。可选授权模式为本条命令、普通权限与所有权限：普通权限**跨任务持久**，但每个任务仍需要明确目标与范围；**所有权限绝不会被自动推断**。Archived Assurance Edition 继续保存在 `codex/enterprise-assurance`，但不承诺活跃维护。

</details>

## 可选的个人设置

安装 Rootloom 只会暴露四个 Skills。它**不会**写入 `~/.codex/AGENTS.md`、
安装命令 Rules、启用 Hook、运行 Evidence Helper，或安装/读取 Project Memory。

如果希望在不同项目间使用 Rootloom 的工作协议，再明确提出设置请求：

```text
$setup-rootloom
先展示 personal preset 的安装计划；如果没有冲突，再执行安装。
```

Setup 会先展示计划、拒绝冲突、建立备份，并在文档化边界内支持回滚。它不会修改模型、推理强度、沙箱、审批策略、Provider、MCP Server、插件或 App。参见[安装、升级与回滚](docs/setup.zh-CN.md)。

## Rootloom 是什么，也不是什么

Rootloom 有意保持克制：

- **它是**面向 OpenAI Codex 的单代理工程工作流；
- **它是**本地、可检查的，运行时只依赖 Python 标准库；
- **它不是**需求规格框架、测试 Runner、Linter、Secret Scanner、CI 或人工审查的替代品；
- **它不是**用于执行不可信验证命令的沙箱；
- **它目前不提供** Claude Code、Cursor 或其他 Coding Agent 的集成。

[GitHub Spec Kit](https://github.com/github/spec-kit)、[OpenSpec](https://github.com/Fission-AI/OpenSpec) 一类工具帮助你在实现前定义工作；测试、Lint、安全扫描和 CI 各自执行检查。Rootloom 关注的是执行与审查的交界处：为什么这样改、为什么改这里、实际运行了什么，以及完成声明有哪些证据。

## 产品组成

```text
Rootloom Core
├── Change：Direct / Scoped / Governed / Evidence
├── Review
├── Project Guidance
├── Setup
├── Optional Autonomy：授权模式 / Command Rules
└── Optional Evidence Resources：Analyzer / Baseline / Contract / Seal / Finalizer

Rootloom Memory
└── 独立实验插件
```

不再维护的 1.2.19 实现保存在 [Archived Assurance Edition](https://github.com/liyanqing90/rootloom/tree/codex/enterprise-assurance)。Human Review 状态机、不可篡改 Audit Chain、多代理审计 Runner 和 Recovery Journal 不属于 `main`。

## 可选 Rootloom Memory

Core 不再发现 Project Memory。只有明确需要仓库内历史经验时才单独安装：

```bash
codex plugin add rootloom-memory@rootloom
```

它的 `$project-memory` Skill 继续兼容 `rootloom-project-memory-v1`，始终只提供
线索，不能覆盖当前 Source、Test、Schema 或 Runtime Evidence。

## 文档

- [架构](docs/architecture.zh-CN.md)
- [安装、升级与回滚](docs/setup.zh-CN.md)
- [成熟度与保证](docs/maturity.zh-CN.md)
- [项目指导设计](docs/guidance-design.zh-CN.md)
- [排障](docs/troubleshooting.zh-CN.md)
- [从 Rootloom 3.x 迁移到 4.0](docs/migration-4.0.zh-CN.md)
- [从 Rootloom 4.0 迁移到 4.1](docs/migration-4.1.zh-CN.md)
- [参与贡献](CONTRIBUTING.zh-CN.md)

## 网站遥测

公开的 GitHub Pages 网站只在全局 `index.html` 中加载一次 VibeLoft 官方浏览器运行时。Rootloom 不安装遥测包、不手动发送 Page View、不让浏览器直接访问 Supabase，也不配置其他 Collector。随机第一方设备 ID、粗粒度环境摘要、GPC/DNT、导航覆盖、重试和失败隔离都由官方运行时负责。具体边界与回滚方式见已接受的[网站遥测决策](docs/decisions/2026-07-17-vibeloft-web-telemetry.md)。

## 开发

```bash
make validate
make test
make check
make compatibility-smoke
make telemetry-check

# 在 http://localhost:8000 预览网站
python3 -m http.server 8000
```

## 许可证

[MIT](LICENSE)
