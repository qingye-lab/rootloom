# Agent Plugins 可移植预览

Rootloom 提供两个彼此独立的安装根：

| 包 | 公共 Skills | 运行边界 |
| --- | --- | --- |
| `plugins/rootloom/` | Change、Review、Project Guidance、Setup | OpenAI Codex 原生插件，包含可选 Hook 与 Setup |
| `portable/rootloom/` | Change、Review、Project Guidance | Agent Plugins 1.0.0 可移植预览；仅包含 Skills |

可移植包在根目录提供 `plugin.json`，使用规范标识
`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`。兼容客户端会按照
Agent Plugins 与 Agent Skills 规范发现 `skills/` 的直接子目录。该包有意不包含
`.codex-plugin`、Hook、Host 配置、OpenAI 界面元数据、Setup、Rules、Memory 或 MCP
Server。Project Guidance 是自包含的：确定性 Helper 与锁实现从原生来源生成，Codex
`agents/` 元数据则被排除。

Agent Plugins 1.0.0 当前仍是 Working Draft。规范定义包加载与组件发现，但安装、分发、
权限、更新和客户端交互仍由各客户端负责。请使用目标客户端自己的安装流程，并把
`portable/rootloom/` 选作插件根目录。同一个客户端不要同时安装 Rootloom 原生包和
可移植包；规范没有定义同名 Skill 的优先级。

## 一份通用包，不同加载入口

Rootloom 不为 Cursor、VS Code、Copilot 或 Kiro 复制 Skills，也不增加 Cursor Manifest、
VS Code Extension、Copilot Manifest 或旧版 Kiro `POWER.md`。这四个平台都已记录对根
`plugin.json` Agent Plugins 的支持。三项 Skills 在各 Host 保持一致；只有 Agent
Plugins v1 尚未标准化的生命周期 Envelope 才由 `adapters/rootloom/` 下的可选消费者
仓库模板提供。

| 客户端 | 使用的包 | 当前入口 | 运行证据 |
| --- | --- | --- | --- |
| Cursor IDE | 原样使用 `portable/rootloom/` | 本地插件目录 | 官方 Loader 已记录；Rootloom 运行冒烟待完成 |
| VS Code | 原样使用 `portable/rootloom/` | `chat.pluginLocations` | 官方 Loader 已记录；Rootloom 运行冒烟待完成 |
| GitHub Copilot CLI | 原样使用 `portable/rootloom/` | `--plugin-dir` 或 `plugin install` | 官方 Loader 已记录；Rootloom 运行冒烟待完成 |
| GitHub Copilot Coding Agent | 相同标准格式 | 需要可解析的 Copilot Marketplace 入口 | Rootloom 当前没有 Cloud 安装渠道 |
| Kiro IDE | 原样使用 `portable/rootloom/` | 从本地文件夹导入 Power | 官方 Loader 已记录；Rootloom 运行冒烟待完成 |
| Codex | `plugins/rootloom/` 原生包 | 既有 Rootloom Marketplace | 已有原生兼容冒烟；完整四 Skill Surface |

通用包没有平台分叉。未来只有在 Agent Plugins 规范确实无法表达某项 Host 能力时，才使用
Client Extension 或独立 Adapter；不得为了一个平台改变其他所有客户端共享的 Skills。

### 可选只读 SessionStart Adapter

`adapters/rootloom/` 提供 Cursor、VS Code/GitHub Copilot 共享配置和 Kiro 的非安装式
模板。每个模板都调用同一份 Project Guidance Renderer，只读检查所选仓库，把完整
Advisory Context 限制在 4 KiB，并且绝不创建或更新 `AGENTS.md`。模板不增加工具门禁、
权限、Rules、MCP Server 或自动 Setup。
共享 `.github/hooks/rootloom.json` 带有必需的精确整数 `"version": 1`；畸形输入与
Host 不兼容诊断只进入 stderr，绝不会进入 Agent Context。

复制前先检查消费者仓库已有的 `.cursor/`、`.github/hooks/`、`.kiro/hooks/` 与
`.rootloom/rootloom-adapter/`；若已有 Owner 或命令冲突，先人工合并，不能盲目覆盖。
只把一个适用的 `template/` 目录内容复制到仓库根。移除时，只删除精确的 Rootloom Hook
JSON 和 `.rootloom/rootloom-adapter/` 下两个文件；删除前确认它们仍与模板一致且未被
其他集成共享，随后新建 Agent Session。

本仓库已通过静态 Schema、来源相等、含空格路径、畸形输入与合成 Envelope 检查。
Cursor、VS Code、Copilot 与 Kiro 的真实运行冒烟仍待完成；模板不代表运行时等价。

### Cursor IDE

Clone 本仓库，然后把完整通用包根放入或链接到 Cursor 本地插件目录：

```bash
mkdir -p ~/.cursor/plugins/local
ln -s "/absolute/path/to/rootloom/portable/rootloom" \
  ~/.cursor/plugins/local/rootloom
```

重启 Cursor 或执行 **Developer: Reload Window**。链接安装在更新 Checkout 后重新加载
即可更新；Skill 调用方式可在 **Customize → Skills** 管理。移除这个精确链接可运行
`unlink ~/.cursor/plugins/local/rootloom`，重新加载并新建 Chat。当前不能宣称已上架
Cursor Marketplace：Rootloom Manifest 位于 `portable/rootloom/`，而公开提交流程能否
解析该 Monorepo 子路径尚未实际验证。参见 [Cursor 插件文档](https://cursor.com/docs/plugins)。

### VS Code

在用户 Settings 中启用 Agent Plugins，并注册同一个包根：

```json
{
  "chat.plugins.enabled": true,
  "chat.pluginLocations": {
    "/absolute/path/to/rootloom/portable/rootloom": true
  }
}
```

Workspace Settings 也可以使用相对路径 `portable/rootloom`。把 Mapping 改为 `false` 可禁用，
删除 Mapping 可取消注册，随后执行 **Developer: Reload Window**。**Chat: Install Plugin
From Source** 只记录了 Repository URL，没有记录 Monorepo 子目录选择器，因此 Rootloom
仓库根 URL 不是已验证的直接安装入口。参见 [VS Code Agent Plugins](https://code.visualstudio.com/docs/agent-customization/agent-plugins)
与 [AI Settings](https://code.visualstudio.com/docs/agents/reference/ai-settings)。

### GitHub Copilot CLI 与 Coding Agent

Copilot CLI 可以临时加载同一目录，也可以精确安装远端子目录：

```bash
copilot --plugin-dir "$PWD/portable/rootloom" \
  -p "Use operating-code-review to review this repository without editing files."
copilot plugin install "$PWD/portable/rootloom"
copilot plugin install liyanqing90/rootloom:portable/rootloom
```

持久安装使用 `copilot plugin list`、`copilot plugin update rootloom`、
`copilot plugin disable rootloom`、`copilot plugin enable rootloom` 和
`copilot plugin uninstall rootloom` 管理。VS Code 也能发现 Copilot 的已安装插件目录。
参见 [Copilot CLI 插件参考](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)。

GitHub Copilot Coding Agent 被列为 Agent Plugins 兼容客户端，但仓库的 `enabledPlugins`
设置需要通过已知 Marketplace 解析 Plugin Spec。Rootloom 尚未通过这种 Marketplace 发布
可移植包。不要把 `OWNER/REPO:portable/rootloom` 写入 `enabledPlugins` 后就声称安装成功；
Cloud 支持仍需先完成发布渠道与真实冒烟。

### Kiro IDE

在 **Powers → Add Custom Power → Import power from a folder** 中选择
`portable/rootloom/` 并安装。Kiro 当前 Power 格式就是 Agent Plugins，因此不需要
`POWER.md` 或 `dev.kiro/` Adapter。GitHub 导入要求 `plugin.json` 位于 Repository Root，
所以不能直接使用当前 Rootloom 仓库 URL；在有以可移植包为根的发布源之前，请使用本地
文件夹。Kiro 记录了更新控制，但没有稳定公开移除或存储合同；不要删除猜测的 Cache
路径。Rootloom 在声明支持回滚前，必须用当时 Powers UI 禁用或移除 Power、新建 Chat，
并确认三个 Rootloom Skills 都不再出现。参见 [Kiro Powers](https://kiro.dev/docs/powers/)与
[Power 安装](https://kiro.dev/docs/powers/installation/)。

### 运行冒烟门槛

Cursor、VS Code、Copilot CLI 与 Kiro 的版本化发布冒烟必须证明：只出现
`operating-code-review`、`operating-coding-change` 与 `project-guidance`；Review 不修改
Fixture Worktree；小型 Change 完成并报告真实验证；所选可选 Adapter 注入相同的有界只读
Session Context；明确 Evidence 请求会失败关闭。要声明支持 Artifact Context，还必须让缓存未命中 Fixture 在无历史 Worker 中运行、Finalize 成有界回执，并在不重新读取原文件时再次
命中缓存。同时还要确认没有产生 Rules、Setup、
权限策略或 MCP 配置。仓库尚未保存这些 Host 的当前版本通过
证据，因此这些运行检查仍是待完成项，不会被报告为已通过。

## 能力边界

| 能力 | 可移植状态 |
| --- | --- |
| Review 工作流及四个相对 References | 已包含 |
| Direct 与 Scoped Change | 已包含 |
| Governed 推理与验证合同 | 已包含 |
| 持久决策模板 | 原生模板不存在时，使用 Governed Reference 内置的同名章节 |
| Evidence Mode | 不可用；可移植包缺少插件级 Evidence Helper，因此会失败关闭 |
| Project Guidance probe/seed/validate | 已包含；持久写入需要用户精确意图 |
| 只读 4 KiB SessionStart Context | 同一 Renderer；Codex 原生 Hook 或可选 Host Adapter |
| Artifact Context 身份/缓存/24 KiB 回执 | 可选优化需要 Host 提供无历史 Worker；普通有界读取不需要 |
| Setup、`~/.codex`、命令 Rules、Hook 启用 | 仅 Codex 原生包 |
| MCP Server | 未提供 |

符合包格式不等于所有客户端中的模型行为和工具能力完全一致。仓库 CI 会校验 Manifest
合同、Agent Skills Frontmatter、包路径包含关系、相对 References、精确的三 Skill
Allowlist，以及与原生来源逐字节同步。Codex 另有兼容性冒烟；在 Rootloom 宣称功能
等价前，Cursor、VS Code、GitHub Copilot、Kiro 等客户端仍需要面向具体版本的真实
运行冒烟。

Artifact Context Helper 可移植、不联网且只依赖标准库。可选语义回执创建使用无历史
Worker；继承历史的子任务不能提供该隔离。Host 没有此能力时继续普通有界读取，除非用户
明确隔离要求不允许该回退。通道不使用 MCP Server，也不能修改已记录的任务历史。

## 维护流程

原生 Skill 目录是唯一编辑来源。修改 Change、Review 或 Project Guidance 后重新生成
可移植镜像；修改 Project Guidance Helper 或锁后还要重新生成 Host 模板：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_portable_plugin.py --write
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_portable_plugin.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_host_adapters.py --write
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_host_adapters.py
make portable-compatibility-smoke
```

仓库内 Rootloom Skills 有意只使用 Agent Skills Frontmatter 的规范单行子集，且只包含
`name` 与 `description`：值以 ASCII 字母开头、仅使用可打印 ASCII，并排除 YAML 的
`:` 与 `#` 分隔符。这样可以在只依赖标准库的前提下拒绝歧义或结构化 YAML 值。除非
同步扩展 Parser、测试与可移植合同，否则不要加入可选字段或放宽该标量子集。

如果可移植包或 Adapter 发生漂移、出现额外文件或 Symlink、暴露 Setup、Manifest 非法，
或不再匹配原生来源和共享身份字段，`scripts/validate_repo.py` 会失败。可移植同步还使用
逐 Skill 的显式文件 Allowlist；本地、隐藏或临时来源文件会被拒绝，不会被静默发布。
可选冒烟会把隔离的可移植包安装到一次性的 Codex Home；它不能证明其他客户端中的行为。

## 迁移与回滚

现有 Codex 用户不会自动迁移，仍然安装 `rootloom@rootloom`。可移植包是额外的预览
渠道，不是原生插件的升级。当前预览没有发布面向用户的 Codex 可移植 Marketplace
入口，因此 Codex 用户应继续使用原生包。Codex 中的原生包与其他 Host 中的可移植包
属于不同客户端，可以同时存在；不要在同一个客户端里加载两个包根。

如果因为其他原因要卸载 Codex 原生包，先用 `$setup-rootloom` 检查并回滚所有可选
Setup，再运行 `codex plugin remove rootloom@rootloom` 并结束当前任务。只删除插件不会
清理复制到 `~/.codex` 的 Guidance、Rules、Hook Policy 或 Setup State。

移除或禁用可移植包由客户端管理，不会撤销此前任务已经写入仓库的修改；操作后应新建
任务，让客户端刷新 Skill 发现。维护者撤回这项打包能力时，只移除可移植包、同步/校验
和可移植文档；原生 Codex 包与 Marketplace 保持不变。

参见 [Agent Plugins 规范](https://agent-plugins.org/specification)、
[Agent Skills 规范](https://agentskills.io/specification)与当前的
[兼容客户端目录](https://agent-plugins.org/compatible-clients)。
