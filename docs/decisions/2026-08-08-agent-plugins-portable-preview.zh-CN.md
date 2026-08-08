# 将 Agent Plugins 可移植预览与 Codex 原生包隔离

- Status: accepted
- Date: 2026-08-08
- Owners: Rootloom maintainers
- Scope: 插件打包、可移植 Skill Surface、Codex 共存与兼容性声明
- Supersedes: none
- Superseded by: [统一 Rootloom 跨 Host 能力基线](2026-08-08-unified-host-capability-baseline.zh-CN.md)

## Context

Rootloom 四入口 Core 通过 `plugins/rootloom/` 中的 `.codex-plugin/plugin.json`、界面
元数据、受门禁控制的 SessionStart Hook、Project Guidance 与可选 Codex-home Setup
服务 Codex。Agent Plugins 1.0.0 则定义根 `plugin.json`、固定 `skills/` 以及可选
`mcp.json`。如果直接在现有 Codex 包加入根 Manifest，当前 Codex 实现会改变格式选择，
并停止加载原生 Hook。格式兼容不能以静默丢失既有能力为代价。

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| Agent Plugins 1.0.0 要求根 Manifest 与固定 Skill 发现 | fact | Agent Plugins Working Draft 与规范 Schema | 2026-08-08 | [规范](https://agent-plugins.org/specification) | 公开规范 |
| 当前 Codex 优先选择 Agent Plugins 格式，并且该模式不加载插件 Hook | fact | 当前 OpenAI Codex 源码 | 2026-08-08 | `codex-rs/core-plugins` Manifest 与 Loader 路径 | 公开源码；无敏感数据 |
| Cursor、VS Code、GitHub Copilot 与 Kiro 都记录了根 `plugin.json` Agent Plugins 加载 | fact | 当前 Host 文档与 Agent Plugins 兼容客户端目录 | 2026-08-08 | 各 Host 插件或 Power 文档 | 公开文档 |
| Review 自包含，Change 的 Direct/Scoped/Governed 使用 Skill 内 References | fact | 当前 Rootloom Skill Tree | 2026-08-08 | `plugins/rootloom/skills/{operating-code-review,operating-coding-change}` | 仓库源码 |
| 完整 Evidence、Project Guidance 写入、Setup 与 SessionStart 依赖插件级或 Codex 专用资源 | fact | 当前 Rootloom 源码 | 2026-08-08 | Evidence、Guidance、Setup 与 Hook | 仓库源码 |

## Decision

保持 `plugins/rootloom/` 为 Codex 原生四 Skill 包，Marketplace 继续只指向该路径。新增
独立的 `portable/rootloom/` Agent Plugins 1.0.0 预览，只包含 Change 与 Review。

Cursor、VS Code、GitHub Copilot、Kiro 与其他 Conformant Host 原样使用这一份包。Host
安装设置留在包外。除非必需能力确实超出 Agent Plugins，并且另有已接受的兼容、迁移、
回滚与验证合同，否则不增加平台 Manifest、生成的 Skill 镜像或 Extension Directory。
Codex 继续作为有意保留的原生 Adapter，因为既有 Hook、Setup、Guidance 与界面行为
超出了 Portable v1 Core。

原生 Skill 目录继续作为唯一编辑来源。确定性的标准库同步器只复制 `SKILL.md` 与非客户
端专用的配套资源。显式 Evidence Mode 会在缺少插件级 Helper 时失败关闭。仓库校验
负责约束可移植 Manifest Schema、路径包含关系、精确 Allowlist、共享身份/版本一致性，
以及与原生来源逐字节相同。

Portable Change 包含 Direct、Scoped、Governed 推理与成比例验证。明确请求 Evidence
Mode 时，由于包中没有插件级 Evidence Helper，它会失败关闭。Review 保持完整自包含。
Project Guidance、Setup、Hook、Rules、OpenAI UI 元数据、Memory 与 MCP 不进入预览。

## Alternatives considered

- 在 `.codex-plugin/plugin.json` 旁增加 `plugin.json`——拒绝，因为当前 Codex 的格式优先级会静默关闭既有 Hook。
- 用 Agent Plugins 格式替换 Codex 包——拒绝，因为 Hook 与 Setup 不是 v1 可移植组件，现有用户会失去原生行为。
- 把四个 Skills 全部复制到预览——拒绝，因为 Project Guidance 写入与 Setup 依赖 Codex 专用信任、路径、协议和配置。
- 人工复制共享 Skills——拒绝，因为安全和工作流修复可能漂移；确定性同步让原生来源保持权威。
- 生成 Cursor、VS Code、Copilot 或 Kiro 包分叉——拒绝，因为四个平台都消费 Agent Plugins 根格式，差异只在 Loader 配置。
- 包含完整 Evidence 子系统——暂缓，因为 Agent Plugins 只标准化打包，不统一实现等价 Evidence 所需的 Shell、进程与运行时能力。

## Consequences

- Positive: Agent Plugins 客户端能够发现符合标准形态的 Rootloom Change/Review 包，而不改变 Codex 原生行为。
- Positive: 现有 Marketplace 安装、Hook 启用、可选 Setup 与回滚保持不变。
- Positive: 所有 Conformant 非 Codex Host 共享一个 Manifest 与一份生成的 Skill 镜像，不累积平台分叉。
- Negative: 可移植预览的能力少于原生包，且仍需要客户端级运行测试。
- Negative: 仓库保留一份生成的 Skill 镜像，并用精确同步检查约束。
- Operational: 每个客户端只能选择一种 Rootloom 包；安装与移除仍由客户端负责。
- Operational: 有文档的 Loader 不等于运行已通过；Cursor、VS Code、Copilot 与 Kiro 仍需绑定版本的 Host 冒烟证据。
- Operational: 回滚只移除 `portable/rootloom/`、同步/校验和可移植文档；Codex 包不受影响。

## Verification

- 仓库校验拒绝非法 Schema、额外文件、Codex-only Skill、Symlink、路径逃逸、身份漂移和过期镜像。
- 聚焦单元测试对 Manifest Schema、Shape、类型与共享身份字段做变异测试，并生成隔离包。
- `make check` 验证仓库合同与完整单元测试。
- `make compatibility-smoke` 验证原生 Codex Marketplace、Setup、Rules 与回滚仍然通过。
- `make portable-compatibility-smoke` 验证 Codex 能够安装隔离包，且已安装 Skill 目录
  Surface 只包含 Change 与 Review；它不证明运行时激活。
- 在把 Preview 提升为跨客户端功能等价声明之前，仍需至少一个非 OpenAI 兼容客户端的真实运行冒烟。

## Revisit when

- Codex 发布并验证能够保留当前原生生命周期合同的可移植 Hook 或扩展语义。
- Agent Plugins 离开 Working Draft，或调整 Manifest/组件合同。
- 客户端运行证据足以支持加入 Project Guidance、Evidence Helper 或其他可移植 Skill。
- 同名 Skill 优先级形成足够稳定的标准，允许同一客户端安全共存原生包与可移植包。
