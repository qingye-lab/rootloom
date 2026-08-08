# 统一 Rootloom 跨 Host 能力基线

- Status: accepted
- Date: 2026-08-08
- Owners: Rootloom maintainers
- Scope: 可移植 Skills、只读 Session Context 与消费者仓库 Host Adapter
- Supersedes: [Agent Plugins 可移植预览隔离](2026-08-08-agent-plugins-portable-preview.zh-CN.md)
- Superseded by: none

## Context

隔离的 Agent Plugins 预览原来只暴露 Change 与 Review；它保住了 Codex 原生生命周期，
却让 Project Guidance 不在通用能力基线内。Agent Plugins 1.0.0 标准化 Skills 与 MCP，
但不标准化 Host 生命周期事件。Cursor、VS Code/GitHub Copilot、Kiro 与 Codex 使用不同
SessionStart 事件与输出 Envelope；如果复制工作流形成 Host 分叉，语义必然漂移。

## Evidence

- 原生 `project-guidance` 已拥有确定性、无网络、只读且完整输出不超过 4 KiB 的 Session Renderer；持久 Seed 仍要求显式意图。
- Cursor 使用 `sessionStart` 与 `additional_context`；VS Code 接受 Copilot lowerCamel Hook 配置并返回嵌套 `hookSpecificOutput`；Copilot 使用 Camel 输入与 `additionalContext`；Kiro `SessionStart` 把纯 stdout 加入 Context。
- Agent Plugins Client Extension 由 Host 定义，目前没有覆盖这些 Host 的通用 Hook Namespace；把自创 Host 目录放进 `portable/rootloom/` 不构成标准合同。

## Decision

`portable/rootloom/` 精确暴露三个标准 Skills：Change、Review 与 Project Guidance。
原生 Skill 目录保持权威；确定性同步排除 `agents/` 元数据和 Cache，并把
`rootloom_lock.py` 放在 Project Guidance Helper 旁，使可移植 Skill 自包含。

`portable/rootloom/` 继续只使用 Agent Plugins v1 标准结构。可选、非安装式消费者仓库
模板放在 `adapters/rootloom/`。Cursor、VS Code/Copilot 共享配置与 Kiro 都逐字节复制
同一规范运行文件，只在 Event、Config 和输出 Envelope 上不同。机器可读能力合同记录
三 Skill 基线、只读 4 KiB Context、Host Mapping、非 Codex 运行状态 Pending，以及
无法统一的 Surface。

Adapter 只在只读 Hook 路径上使用单次显式 Trust Override。持久 Seed/Refresh 仍需精确
用户请求：Skill 必须先不带 Override 运行；只有该仓库返回精确 `untrusted_project` 时，
才可以因同一显式请求用 `--allow-untrusted` 重试。`.rootloom/disable-project-guidance`
与旧 Codex Sentinel 都会关闭 Context 与 Seed。

Setup 仍为 Codex 原生能力；可移植 Evidence Runtime 仍不可用并失败关闭；Host
权限执行仍由 Host 拥有。Adapter 不增加 PreToolUse、Stop、Rules、权限、MCP、自动安装或仓库写入。

## Alternatives considered

- 每个 IDE 复制 Project Guidance——拒绝，因为行为和安全修复会漂移。
- 把 Hook 目录放入 Agent Plugins Root——拒绝，因为 v1 没有跨 Host Hook 组件。
- 只使用 Host Instructions 或 Steering——拒绝，因为无法提供同一确定性有界 Renderer。
- 现在加入权限门禁——拒绝，因为权限语义属于 Host，不在通用基线内。

## Compatibility, migration, and rollback

Codex 原生 Manifest、四 Skill 发现、Setup、Rules、Hook 开关、Evidence Format、Marketplace
路径与 Memory 均不变。正式发布前，可移植包从两个 Skills 兼容扩展到三个，本次未发布
修改不提升版本。现有可移植用户刷新同一包根即可。Adapter 只有在用户检查冲突并明确
复制后才进入消费者仓库。

回滚只删除精确 Adapter 文件，并重新生成不含 Project Guidance 的可移植包；不改变
Codex 原生状态或既有仓库 Guidance。没有不可逆操作。

## Verification

仓库检查约束精确 Manifest、Event、Timeout、Command、来源逐字节相等、路径包含、无
Symlink/额外文件、有界与畸形 stdin、Plan/Disable Skip、Trust 行为、含空格路径执行、
缺少解释器时不破坏、共享 Hook 配置必需的整数版本 1、非 Codex 诊断只进入 stderr，
以及各 Envelope 的合成 Context 完全一致。隔离 Codex 包冒烟要求
精确三个 Skills 和自包含 Helper。

这些只是静态与合成检查。Cursor、VS Code、GitHub Copilot 与 Kiro 的真实运行冒烟仍为
Pending；本决策不宣称已达到真实运行时等价。

## Revisit when

- Agent Plugins 标准化可移植生命周期事件或通用 Hook Namespace。
- 任一 Host 改变 Event、Input、Output、Timeout 或仓库 Hook 合同。
- 绑定版本的真实 Host 冒烟证据足以提升运行时声明。
