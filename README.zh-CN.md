<p align="center">
  <img src="plugins/rootloom/assets/icon.svg" width="112" alt="Rootloom 标志">
</p>

<h1 align="center">Rootloom</h1>

<p align="center">
  <strong>把 Codex 的代码修改，变成可检查的工程过程。</strong>
</p>

<p align="center">
  一个 OpenAI Codex 原生插件：找到真正该改的位置；<br>
  另提供可移植 Change、Review 与 Project Guidance 的 Agent Plugins 预览。
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

Rootloom 是一个本地工程工作流，包含完整的 OpenAI Codex 原生插件，以及独立的
Agent Plugins 可移植预览。原生插件暴露四个 Skills：修改、审查、项目指导和设置；
可移植预览暴露 Change、Review 与 Project Guidance，不包含 Codex-only Hook 或 Setup。它不是另一个
Coding Agent，也不会取代编辑器、测试或 CI。高风险治理与机器证据仍然是 Change 的
内部模式，不是额外公共入口。

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

## Agent Plugins 可移植预览

`portable/rootloom/` 是一个独立的 Agent Plugins 1.0.0 包，只包含
`operating-coding-change`、`operating-code-review` 与 `project-guidance`。兼容客户端会从包根目录的
`plugin.json` 和固定 `skills/` 目录发现这三个 Skills。Agent Plugins Working Draft
把安装、更新、权限和客户端交互交给各个客户端，因此请使用目标客户端自己的流程，并
把 `portable/rootloom/` 选作插件根目录。

Cursor、VS Code、GitHub Copilot CLI 与 Kiro 原样使用同一份包，不增加平台 Manifest，
也不复制 Skills；区别只在加载配置。Copilot Cloud 仍需要已经发布且可解析的 Marketplace
入口，Rootloom 当前尚未提供。Codex 保留原生包，是因为它的托管 Hook、Setup 与界面
Surface 有意大于 Agent Plugins v1。

预览包含 Review、Project Guidance，以及 Direct、Scoped、Governed Change；持久 Guidance
仍要求精确用户意图。它有意不包含 Setup、Hook、Rules、Memory、MCP、OpenAI UI 元数据和插件级
Evidence Helper。明确请求 Evidence 时会失败关闭，不会伪造 Evidence Bundle。同一
客户端不要同时安装原生包与可移植包，因为规范没有定义同名 Skill 的优先级。

仓库检查能够证明包结构、路径包含关系、Agent Skills 元数据、相对 References 以及与
原生来源同步；一次性的 Codex CLI 冒烟还会证明 Codex 能够安装这个独立包，且安装产物
精确包含三个 Skill 目录与自包含 Helper。静态与合成测试还覆盖可选 Host Adapter Envelope，
但这些检查不能证明运行时发现、激活，也不能证明 Cursor、VS Code、
GitHub Copilot、Kiro 或所有兼容客户端中的运行行为完全一致。精确能力矩阵、迁移和
回滚边界参见
[Agent Plugins 可移植预览](docs/agent-plugins.zh-CN.md)，其中包含 Cursor、VS Code、
Copilot 与 Kiro 的精确加载步骤、运行冒烟门槛、迁移和回滚边界。

## 按任务选择工作流

| 你希望 Codex…… | 使用 | 适用场景 |
| --- | --- | --- |
| 实现、修复、重构、迁移、部署或生成严格证据 | `$operating-coding-change` | 唯一修改入口；自动路由 Direct、Scoped、Governed、Evidence 与 External Action |
| 只审查 Diff、PR、Migration 或设计，不修改文件 | `$operating-code-review` | 你需要结论与证据，而不是补丁 |
| 创建、刷新、精炼或检查仓库 `AGENTS.md` | `$project-guidance` | 项目命令或持久不变量需要长期保留 |
| 安装、升级、检查或回滚可选全局设置 | `$setup-rootloom` | 你需要跨项目指导或 Autonomy Rules |

Rootloom Core 始终只展示这四个入口。Change 只有在风险和证据模式需要时，
才按需加载治理、外部动作、验证或 Evidence Reference。
版本号与序列化产物本身不会触发兼容：可再生内部记录保持 Scoped 且只接受当前版本；
回滚恢复完整旧版本，历史回放使用匹配的旧运行时。只有存在真实的切换后消费者证据时，
才启用运行时兼容。
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
只在相应模式成立时、首次编辑前加载详细合同，必需 Reference 无法加载时停止。
使用 `make core-reset-release-eval CORE_RESET_RESULTS=/absolute/path/results-v2.json`
执行该正式门禁。
耗时比率只比较两个版本都成功完成任务的配对；任务成功率回退仍由独立硬门禁禁止。
仓库保留的 [4.3.0 候选报告](evals/core-reset/reports/4.3.0.md)记录了全部 135 个 Cell，
复用 99 个未受影响的 Cell，并替换会激活 Change 或 Setup 的 36 个候选 Cell。结果、
精确路由、质量、Token、命令数与成功配对耗时门禁全部通过；版本 Tag Workflow 会运行
这份保留结果。

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

- **它是**包含完整 OpenAI Codex 原生插件的单代理工程工作流；
- **它是**面向 Change、Review 与 Project Guidance 的 Agent Plugins 1.0.0 可移植预览；
- **它是**本地、可检查的，运行时只依赖 Python 标准库；
- **它不是**需求规格框架、测试 Runner、Linter、Secret Scanner、CI 或人工审查的替代品；
- **它不是**用于执行不可信验证命令的沙箱；
- **它不承诺**不同 Coding Agent 客户端具有等价的 Hook、Setup、权限、Evidence 或模型行为。

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

公开的 GitHub Pages 网站只在全局 `index.html` 中加载一次 VibeLoft 官方浏览器运行时。Rootloom 不安装遥测包、不手动发送 Page View、不让浏览器直接访问 Supabase，也不配置其他 Collector。随机第一方设备 ID、粗粒度环境摘要、GPC/DNT、导航覆盖、重试和失败隔离都由官方运行时负责。由于发布运行时已经混淆，发布门禁固定一次“请求全部拦截”的浏览器审核所确认构建的精确 SHA-256；任何上游变化都会失败关闭。具体边界、复审方式与回滚见已接受的[网站遥测决策](docs/decisions/2026-07-17-vibeloft-web-telemetry.md)。

## 开发

```bash
make check-changed BASE=origin/main
make validate
make test
make check
make compatibility-smoke
make telemetry-check

# 在 http://localhost:8000 预览网站
python3 -m http.server 8000
```

`check-changed` 是默认开发路径：它覆盖已提交、已暂存及未暂存的受跟踪变更，并默认排除
无关未跟踪文件；只有它们都属于当前任务时才使用 `INCLUDE_UNTRACKED=1`。未知可执行路径
或共享测试选择基础设施变化时，回退到全量套件。`test` 与 `check` 是显式全量 Target。
CI 只在 `main` 保留一次规范性全量运行；宽版本矩阵由定时或手动触发。

## 许可证

[MIT](LICENSE)
