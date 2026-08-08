# Setup、更新与回滚

安装插件只会暴露四个 Core Skills 和经过审查的 `SessionStart` Hook 定义；
不会安装全局策略、启用 Hook、运行 Evidence Resource 或安装 Rootloom Memory。
应用全局 Core 资产是独立且可选的操作。

本文只适用于 `plugins/rootloom/` 的 Codex 原生包。位于 `portable/rootloom/` 的独立
Agent Plugins 预览包含 Change、Review 与 Project Guidance，没有 Setup 或 Hook 配置；参见
[Agent Plugins 可移植预览](agent-plugins.zh-CN.md)。可选消费者仓库 SessionStart 模板
单独位于 `adapters/rootloom/`，不会安装或管理 Host 权限。该包的安装与移除使用目标客户端
自己的生命周期，绝不管理 `~/.codex`。

## 安装

```bash
codex plugin marketplace add liyanqing90/rootloom
codex plugin add rootloom@rootloom
```

新建任务并检查 `/hooks`。唯一 Hook 只检测仓库事实并注入临时只读项目 Context；只有精确的托管组件策略版本 1 启用后才会执行，并且绝不写入 `AGENTS.md`。

此时插件已经可以完整使用，不需要 Setup 命令、Analyzer、Baseline、Contract、
Finalizer 或 Memory 插件。

明确用自然语言请求规划、安装、检查、更新或回滚 Rootloom 时可以自动路由到 Setup；
`$setup-rootloom` 是确定性的显式形式。Skill 激活本身不授权覆盖用户拥有的冲突文件。

只有需要实验性 Memory 时才单独安装：

```bash
codex plugin add rootloom-memory@rootloom
```

## Preset

| Preset | 能力 |
| --- | --- |
| `skills-only` | 仅 Skills；关闭 Hook |
| `guidance` | `global-policy`、`project-context` |
| `personal` | Guidance + `autonomy`；默认 |

`skills-only` 使用的空 capability 集合会作为明确的已安装状态保存。后续没有显式新选择的 `status`、`plan` 与兼容命令 `apply` 都会保持它。

只有用户明确需要跨项目全局层时，才检查并安装：

```bash
python3 <setup-skill>/scripts/setup_rootloom.py list-components
python3 <setup-skill>/scripts/setup_rootloom.py plan --preset personal
python3 <setup-skill>/scripts/setup_rootloom.py install --preset personal
python3 <setup-skill>/scripts/setup_rootloom.py status
```

`install` 会拒绝已经安装的 setup。`apply` 继续作为兼容/专家命令保留；显式使用 `install` 与 `upgrade` 能让生命周期和回滚意图清晰可见。

也可以精确选择能力：

```bash
python3 <setup-skill>/scripts/setup_rootloom.py plan \
  --capabilities global-policy,project-context,autonomy
```

选择 `autonomy` 时会自动包含 `global-policy`；负责避免重复弹窗的命令规则不能脱离管理普通权限、本条命令和所有权限的全局指导单独安装。旧 `engineering` 与 `command-safety` 输入只作为兼容别名继续接受。

## 托管目标

| 路径 | 用途 |
| --- | --- |
| `~/.codex/AGENTS.md` | 个人工程工作协议 |
| `~/.codex/rules/rootloom.rules` | 可选低确认授权策略 |
| `~/.codex/.rootloom/components.json` | Hook 开关 |
| `~/.codex/.rootloom/state.json` | 已安装选择与目标哈希 |
| `~/.codex/.rootloom/transaction.json` | 待恢复的已暂存 setup 事务，恢复后删除 |
| `~/.codex/.rootloom/backups/` | 修改前文件副本与清单 |

Rootloom 不会修改普通模型、推理、沙箱、审批、Provider、MCP、插件或 App 配置。

## 安全契约

Setup：

- Skill 应用前先展示 plan；
- 使用普通 create-exclusive 本地锁；
- 拒绝符号链接目标和无标记的用户文件冲突；
- 使用 `--replace-conflicts` 前需要精确授权；
- 第一个托管目标写入前复制所有被替换文件；
- 在发布事务日志前暂存完整目标集合和最终 setup 状态；
- 逐目标原子写入；
- 下一个会写入的 setup 或 rollback 操作会在 setup 锁下恢复待处理事务；
- 记录 apply 后哈希以检测漂移；
- 托管目标不再匹配已安装哈希时拒绝升级，即使传入 `--replace-conflicts` 也不会覆盖；
- 回滚时恢复原内容和 POSIX mode。

如果进程在多个文件替换之间停止，`status` 会只读报告待处理事务；下一个会写入的 setup 或 rollback 操作会恢复精确的暂存目标集合和最终状态。若目标在中断后被修改，恢复会拒绝覆盖并保留事务日志，等待显式协调。它仍不防御敌对同用户进程并发替换锁或目标路径。

## 检查可选 Autonomy Rules

```bash
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- git commit -m test
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- git push origin main
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- gh pr merge 123 --merge
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- gh release create v1.0.0
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- npm publish
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- kubectl apply -f deployment.yaml
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- git push --force-with-lease origin main
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- gh release delete v1.0.0
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- terraform destroy
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- git reset --hard
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- rm -rf /
```

预期依次是十个 `allow`，最后一个 `forbidden`。授权状态由安装后的全局指导管理，而不是由参数规则管理：本条命令只生效一次；普通权限跨任务持久，覆盖每个明确目标的全部非高危步骤；所有权限只在当前任务与范围内覆盖高危步骤。命令规则负责避免语义授权后再次弹窗，只保留灾难性递归删除的硬拒绝。其他更严格的有效规则或平台策略仍可能要求审批。
如果宿主仍把精确授权的动作归类为需要审批，而当前任务或组织 Profile 又禁止发起审批
（例如 `AskForApproval=Never`），应把该控制 Profile 视为阻断层；重复同一用户确认
无法覆盖它。

## 修改 preset 或回滚

修改能力选择前必须先回滚：

```bash
python3 <setup-skill>/scripts/setup_rootloom.py rollback
python3 <setup-skill>/scripts/setup_rootloom.py plan --preset guidance
python3 <setup-skill>/scripts/setup_rootloom.py install --preset guidance
```

回滚会预检每个托管文件。目标在 setup 后被修改时会停止，不覆盖该修改。普通 rollback 返回上一个简单备份；`rollback --all` 沿备份链回到安装前状态。

完成全局回滚后移除插件 Skills：

```bash
codex plugin remove rootloom@rootloom
```

## 更新

```bash
codex plugin marketplace upgrade rootloom
codex plugin add rootloom@rootloom
```

Codex 负责刷新 marketplace snapshot 与插件包。新建任务以加载更新后的 Skills；普通升级至此完成，不会触发任何 Rootloom 审查门禁。

如果之前安装过可选全局 preset，并且希望同时刷新其复制资产，只需显式运行一个命令：

```bash
python3 <setup-skill>/scripts/setup_rootloom.py upgrade
```

可选 setup 的 `upgrade` 始终保持已安装 capability 选择。插件与资产已经一致时返回 `up_to_date`；只有插件版本变化时只更新 setup 状态，不创建多余资产备份；托管内容变化时仍会在写入前创建正常备份。新版目录已退役的托管目标只有在仍匹配安装 Hash 时才会被移除，并会先备份，使 rollback 能恢复；访问前还会重新规范并校验已安装状态路径。`status` 会报告 `installed_version`、`upgrade_available` 与 `drifted_paths`。升级不会覆盖漂移：请先恢复预期内容或回滚。`--replace-conflicts` 只用于新版本首次引入的用户文件冲突，并且需要精确授权。

## 从 Archived Assurance Edition 1.2.19 迁移

两个 setup 契约有意不兼容。安装 Personal Core 前，请使用 `codex/enterprise-assurance` 上已归档的 1.2.19 代码回滚旧 setup。不要让 Personal Core 猜测或删除自定义 Agents、高保障 profile、配置限制、Human Review 状态或恢复日志。
