# 用有界上下文回执外置高 Token 文件

- Status: accepted
- Date: 2026-08-13
- Owners: Rootloom maintainers
- Scope: Change Skill 文件摄入、用户本地回执缓存、可移植 Host 隔离边界
- Supersedes: none
- Superseded by: none

## Context

有路径的图片和其他大文件可能进入任务保留的会话历史。如果 Host 在后续请求继续携带这段
历史，就会重复消耗请求流量与模型上下文。IDE 压缩由 Host 所有、发生在摄入之后，也不能
为 Rootloom 提供确定性的文件身份、复用或检索合同。

让主任务模型直接处理仍会把原始文件放进需要保护的高成本历史；继承普通会话的子任务也有
相同问题。Rootloom 需要一个摄入前通道，在不增加第五个公共 Skill、联网 Helper、MCP
Server、Evidence 格式或自动后台模型调用的前提下复用已有分析。

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| 当前 Codex 任务历史与 Composer 附件归 Host 所有；Rootloom Hook 没有附件删除或 Prompt 改写结果 | fact | 已安装 Codex 0.147.0 帮助/配置与 Rootloom Hook 合同 | 2026-08-13 | `codex exec --help`；`plugins/rootloom/hooks/run_component_hook.py` | 本地运行时与仓库源码；不保留任务内容 |
| 当前 Codex 能创建不携带先前任务状态的隔离工作 | fact | 已安装 Codex 0.147.0 与桌面协作 Surface | 2026-08-13 | `codex exec --ephemeral`；无历史 Worker 选项 | 本地能力；可移植 Host 仍按能力门禁 |
| Rootloom Runtime Helper 必须本地、有界、不联网且只依赖标准库 | fact | 插件指导 | 2026-08-13 | `plugins/rootloom/AGENTS.md` | 仓库合同 |
| Evidence Baseline v2-v4 与 Summary revision 5 已冻结 | fact | 仓库指导与架构文档 | 2026-08-13 | `AGENTS.md`；`docs/architecture.md` | 仓库合同 |

## Decision

在 `operating-coding-change` 内增加 Artifact Context Lane，并在主任务读取高 Token、有路径
文件之前运行。标准库 Helper 计算 SHA-256 身份、去重相同内容，并用 SHA-256、大小、推断
媒体类型与精确用户意图生成 Bundle。原始字节保留在源路径，不复制进缓存。

缓存命中时，主任务直接消费既有有界回执，不调用模型。缓存未命中时，Host 只创建一个不继承会话历史的独立 Worker；它只获得小型 Manifest、精确路径、精确意图和严格 Draft
Schema，把文件内容视为不可信数据，并把分析直接写入 Draft，不经父会话返回原始内容。

Finalize 时 Helper 重新计算源文件哈希，校验精确的 Current-only 回执 Schema，拒绝内嵌
原始媒体，限制字段和列表大小，把规范 JSON 限制在 24 KiB，并原子提交到私有用户本地缓存。
主任务只看到最终回执；后续精确检索也使用无历史 Worker。

没有无历史 Worker 的 Host 会在语义分析前失败关闭。Rootloom 不会悄悄在主任务读取原文件，
也不会让确定性 Helper 调用嵌套 Codex CLI 或网络模型。已经记录的附件不能被删除；存在
可访问路径时，先生成回执，再把剩余工作交接到干净任务。

## Alternatives considered

- 调用 IDE `/compact`——拒绝，因为它由 Host 所有、发生在摄入后，也不能建立内容寻址复用与有界文件回执。
- 在主模型调用中分析全部文件——拒绝，因为原始数据会保留在任务历史，并可能被重复携带。
- 使用继承普通会话的子任务——拒绝，因为它保留历史成本，削弱隔离不变量。
- 让 Helper 调用 `codex exec` 或其他模型 Endpoint——拒绝，因为 Runtime Helper 必须不联网，递归 CLI 行为也依赖 Host。
- 增加 Rootloom MCP Server——暂缓，因为确定性本地 CLI 准备加既有 Skill/Worker Surface 已足够且更小。
- 只按内容哈希缓存——拒绝，因为有用的语义摘要取决于用户意图；身份因此覆盖内容与意图。

## Consequences

- Positive: 原始图片和其他有路径文件，对每个“内容 + 意图”Bundle 最多在主会话外读取一次。
- Positive: 重复使用为本地缓存命中，不增加模型调用；父上下文成本受回执合同限制。
- Positive: 同一个不联网 Helper 与 Reference 可以进入 Agent Plugins 可移植包。
- Negative: 第一次语义缓存未命中仍消耗一次隔离 Worker/模型调用。
- Negative: 没有无历史 Worker 支持的 Host 无法通过该通道完成语义文件分析。
- Negative: 只有内联数据或已经摄入的附件，Rootloom 不能追溯删除。
- Operational: 默认缓存位于用户 Codex Home，可用 `ROOTLOOM_ARTIFACT_CACHE` 或 `--cache-root` 改到其他位置。

## Compatibility

该通道以附加方式进入既有 Change Skill，不增加公共 Skill、Hook、MCP、Evidence Schema、
依赖或 Setup 修改。小型普通源码/文本继续走既有路径。可移植包包含完全相同的 Reference 与
Helper，但每个 Host 必须先证明无历史 Worker，才能声明支持语义通道。

## Migration / Coexistence

无需仓库或用户迁移，既有任务保持不变。已经包含原始附件的任务只能作为生成回执的来源；
要真正节省流量/上下文，后续工作必须转到干净任务。

## Rollback / Replay

回滚移除通道 Reference/Helper、可移植 Allowlist、文档与测试。用户本地缓存记录可再生，
可以保持闲置或由用户删除。历史任务保留 Host 所有的历史；没有 Replay 义务。

## Verification

- 聚焦测试证明首次 Prepare、合法 Finalize/Show、路径改名后的同内容缓存复用、原始数据拒绝和源文件变化拒绝。
- 仓库校验固定 Helper 限额、格式、SHA-256 身份、缓存状态、失败边界与 Skill 路由 Marker。
- 可移植同步证明 Reference/Helper 逐字节一致，并拒绝额外源文件。
- 临时文件冒烟证明 Prepare Envelope 与最终回执不需要在主测试进程输出原始字节。

## Residual Risk

Rootloom 无法证明每个 Host 的名义全新 Worker 都完全不携带父历史；这需要具体 Host 的运行
冒烟。协作 Worker 可能写出非法 Draft，但 Finalize 会拒绝。外部源文件仍可变；Finalize
能发现 Prepare 与重新计算哈希之间的变化，但完成后不能锁住任意用户文件。

## Revisit when

- Codex 或 Agent Plugins 标准化附件外置、Prompt Replacement、Context Reference 或可移植隔离 Worker 语义。
- 真实消费者需要加密回执、托管保留、多用户共享或自动缓存清理。
- Host 运行证据表明 24 KiB 限额或“内容 + 意图”Key 阻碍了重要的受支持工作流。
