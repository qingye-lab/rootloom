# 从 Rootloom 3.x 迁移到 4.0

Rootloom 4 会有意收缩公共 Skill API。已有 Baseline v2–v4、Summary revision 5、
Change Contract、Manifest 与 Seal Artifact 仍然可读。

## Skill 映射

| Rootloom 3.x | Rootloom 4.0 |
| --- | --- |
| `$operating-coding-change` | `$operating-coding-change` |
| `$operating-high-risk-change` | `$operating-coding-change` 的 Governed 模式 |
| `$engineering-change` | `$operating-coding-change` 的显式 Evidence Mode |
| `$seed-project-guidance` | `$project-guidance` 的 Seed 或 Refresh 模式 |
| `$refine-project-guidance` | `$project-guidance` 的 Refine 模式 |
| `$record-engineering-decision` | Governed Change 的持久决策步骤 |
| Core 内的 `$project-memory` | 独立安装 `rootloom-memory` 后的 `$project-memory` |
| `$setup-rootloom` | `$setup-rootloom` |

旧 Skill 目录不会保留 Alias，因为 Alias 仍会被发现，会破坏“四入口”合同。
升级前请修改已保存 Prompt、团队文档和自动化中的旧名称。

## Evidence CLI 路径

Evidence Helper 在不修改冻结 Wire Format 的前提下迁移：

```text
plugins/rootloom/skills/engineering-change/scripts/
→
plugins/rootloom/resources/evidence/
```

请更新自动化中的绝对或仓库相对路径。4.0 Analyzer/Finalizer 不再接受
`--include-project-memory`。需要历史线索时先单独查询可选 Memory Skill，
再用当前证据验证，只把相关结论带入任务或 Change Contract。

## Project Memory

需要时单独安装：

```bash
codex plugin add rootloom-memory@rootloom
```

仓库现有 `.project-memory/` 继续使用 `rootloom-project-memory-v1`，无需迁移。
移除 Rootloom Memory 插件不会删除这些文件。

## 升级

```bash
codex plugin marketplace upgrade rootloom
codex plugin add rootloom@rootloom
```

新建 Codex 任务以重新发现 Skill Catalog。如果安装了 Rootloom 的可选全局设置，
随后用 `$setup-rootloom` 执行 Upgrade；Setup State 和 Rollback 与公共 Skill
收缩相互独立。

## 回滚

安装 4.0 Release 前，请先把 Prompt 或自动化路径修改纳入版本控制。要退回 3.4，
安装不可变 `v3.4.0` Marketplace Snapshot，并恢复旧 Skill/CLI 名称。Evidence
Artifact 无需转换。

正式发布 4.0 前必须通过 `evals/core-reset/` 的对比矩阵；仅有结构性上下文缩减
不能证明行为质量。
