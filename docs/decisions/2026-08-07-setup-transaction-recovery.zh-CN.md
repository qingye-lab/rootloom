# 恢复中断的 Personal Setup 事务

- Status: accepted
- Date: 2026-08-07
- Owners: Rootloom 维护者
- Scope: `plugins/rootloom/skills/setup-rootloom/scripts/setup_rootloom.py`
- Supersedes: 无
- Superseded by: 无

## 背景

Personal setup 会更新多个 Codex-home 文件，并在最后发布 `state.json`。逐文件原子替换
和备份可以保护单个文件，但进程如果在多个目标替换之间停止，目标文件与 setup 状态仍
可能不一致。

## 证据

| 主张 | 类型 | 来源与环境 | 观察时间 | 参考 | 新鲜度 / 脱敏 |
| --- | --- | --- | --- | --- | --- |
| 目标替换与状态发布是顺序操作 | 事实 | Rootloom 源码 | 2026-08-07 | `setup_rootloom.py`，修复前实现 | 仅本地源码 |
| 在第一个目标替换后注入故障会留下已修改目标但没有状态 | 事实 | 定向单元测试 | 2026-08-07 | `test_interrupted_apply_is_completed_from_transaction_journal` | 临时 Codex home |
| 暂存恢复路径可在中断后收敛 | 事实 | 定向单元测试 | 2026-08-07 | 同一测试；`python3 -m unittest tests.test_setup_rootloom` | 18 个测试通过 |

## 决策

Setup 在第一个托管目标写入前创建普通备份，暂存所有替换、删除和最终 setup 状态，
并原子发布 `rootloom-setup-transaction-v1` 日志。会写入的 setup 与 rollback 操作会在
setup 锁下先恢复这笔精确的暂存事务，再开始新工作。恢复会幂等执行、预检全部目标、
拒绝中断后的用户修改、验证最终哈希，并且只在收敛后删除日志。`status` 只读报告日志。

该日志是内部新增的持久化格式。没有日志的既有安装仍可读取，不需要迁移。敌对同用户
进程替换锁或目标路径仍不在契约范围内。

## 备选方案

- 保留文档中的人工协调路径——拒绝，因为 setup 边界可以安全地暂存并重放自己的小型目标集合。
- 中断后自动回滚——暂缓，因为完成原计划事务可以保留用户选择的 setup 意图和现有备份链。
- 引入完整文件系统事务依赖——拒绝，因为本地标准库运行时契约不需要它。

## 后果

- 正面：目标没有被用户修改时，中断的 setup 可以无需逐文件人工修复而收敛。
- 正面：暂存字节保留精确的计划事务，即使恢复前插件源码已经变化。
- 负面：每份备份会额外占用暂存副本的本地空间。
- 运维：`status` 会暴露待处理日志；中断后被修改的目标必须先显式协调，恢复才会继续。

## 验证

- 运行 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_rootloom`。
- 运行 `make check` 与仓库校验器。
- 在第一个目标替换后注入故障，确认下一次会写入的 setup 能恢复，并且只有全部最终哈希收敛后才删除 `transaction.json`。

## 重新审视条件

- Setup 管理的目标数量使暂存备份空间或恢复时间需要明确上限。
- 敌对同用户文件系统替换成为明确的安全要求。
- 持久化 setup 状态格式或回滚语义需要不兼容变更。
