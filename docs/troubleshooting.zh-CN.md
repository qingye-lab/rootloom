# 排障

## 项目指导 Hook 没有执行

确认已安装 personal 或 guidance preset，并且 `~/.codex/.rootloom/components.json` 同时包含精确整数 `version: 1` 与托管布尔值 `project-guidance-hook: true`。策略缺失、损坏、类型错误、版本不支持或为符号链接时 Hook 会关闭。Hook 只注入临时 Context，绝不写入 `AGENTS.md`；需要持久化时显式调用 `$project-guidance`。插件或 setup 变化后新建 Codex 任务，并重新检查 `/hooks`。

仓库未被平台信任时扫描器也会跳过。`ROOTLOOM_ALLOW_UNTRUSTED=1` 仅用于受控测试。

## Setup 报告 conflict

运行 `plan` 并检查所有路径。无标记内容属于用户。只有得到精确授权后才能使用 `--replace-conflicts`；Rootloom 会先创建备份。

符号链接目标始终被拒绝。请显式处理或移动链接，不要让 setup 跟随它。

## Setup 中途停止

Rootloom Core 提供逐文件原子写入与修改前备份，不提供恢复日志。运行：

```bash
python3 <setup-skill>/scripts/setup_rootloom.py status
```

检查最新 `~/.codex/.rootloom/backups/*/manifest.json`，比较目标哈希，只恢复受影响路径。理解部分状态前不要使用 conflict replacement 重跑。

## Rollback 拒绝已修改文件

Rollback 会保护 setup 后的修改。手动保留或合并当前文件，把它恢复到记录的托管版本后再次 rollback。不要通过删除 state 或 backup 绕过检查。

## 命令仍然意外询问

对每个生效 Rules 文件运行 `codex execpolicy check`。最严格匹配结果优先，所以更宽的 `git` prompt 可能覆盖 Rootloom 对本地 `git commit` 的 allow。Rules 检查 argv 前缀；嵌套 shell 命令需要自己的策略与授权边界。

## 验证辅助工具拒绝命令

`finalize_change.py` 使用平台感知的 `shlex` 规则解析，不运行 shell。Windows 解析会保留路径反斜杠，并移除参数成对的最外层引号；可执行路径包含空格时应加引号。管道、重定向、`&&`、环境变量赋值或命令替换不会被解释。把复杂验证放进经过审查的仓库脚本或 Make target，再直接调用该可执行入口。

退出 124 表示超时；125 表示超过有界输出预算；126 表示可执行文件无法启动。只有更大证据确实必要且适合保留时才提高预算。

输出目录必须位于被捕获仓库之外。tracked patch 超过默认 16 MiB 上限时会拒绝；只有先检查 review bundle 为什么如此大后，才提高 `--max-patch-bytes`。验证日志预算由最多 20 条命令共同使用。

## 风险扫描过严或过松

检查 `analyze_change.py` 输出中的 `signals`、`changed_paths` 与 `confidence`。
修改前传入预期 `--path`，让文档/测试和产品代码得到区分。输出 Tier 是建议式
最低下限：当前语义证据仍可继续提高，但 `--declared-risk` 与 Finalizer 的
`--risk` 都不能压低它。可重复误报应通过聚焦扫描器回归测试修正，而不是隐藏信号。

## 验证计划显示 suggested-not-executed

这是有意设计。`required_behaviors` 描述应该证明什么，`suggested_commands` 给出检测到的仓库命令；只有通过 `--verify` 显式提供的命令才会进入 `tests` 并影响 `passed`。执行前应先检查建议。

## 敏感删除返回 exit 10

辅助工具发现精确 `.env`、secret、migration 或 database 路径删除。请先获得该路径的确认，再通过 `--confirm-dangerous-delete` 重复传入。这是轻量 guard，不是审批账本。

## 项目记忆过期或损坏

请单独安装 `rootloom-memory`；Core 不读取 `.project-memory/`。仓库证据优先。
其 `context` 命令默认排除过期、已解决和已替代匹配，并把它们列在 `stale`；
只有调查历史时才使用 `--include-stale`。通过显式 `set-status` 调整生命周期，
不要删除经验。辅助工具拒绝未知格式、过大集合、不安全路径、符号链接或无效条目，
且不会静默迁移模糊内容。

## 我需要旧 Human Review 或严格 Runner

这些能力不是 Rootloom Core 的隐藏开关。请使用保留 Rootloom 1.2.19 的
`codex/enterprise-assurance`。安装另一个产品前，使用对应版本回滚当前 Setup。
