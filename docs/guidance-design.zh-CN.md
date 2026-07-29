# 指导体系设计

本系统不使用一份巨型提示词，而是采用小而清晰的指令层级。可直接安装的全局成果是 [`plugins/rootloom/assets/system/AGENTS.md`](../plugins/rootloom/assets/system/AGENTS.md)，打磨后的项目示例见 [`examples/AGENTS.project.md`](../examples/AGENTS.project.md)。

## 来自 OpenAI 当前官方建议的原则

OpenAI 的 [GPT-5.6 模型指南](https://developers.openai.com/api/docs/guides/latest-model)建议精简提示词、每条规则只写一次、明确自主权与审批边界，并显式提供领域上下文、硬约束和成功标准。Codex 的 [`AGENTS.md` 文档](https://developers.openai.com/codex/agent-configuration/agents-md)进一步给出了自然层级：一个全局文件，再叠加从仓库根目录到当前目录的项目指导，越近的文件优先级越高。

因此本系统采用四条原则：

1. 稳定的个人工作协议放在全局 `AGENTS.md`。
2. 仓库事实和命令放在项目 `AGENTS.md`。
3. 可复用的多步流程放在 Skills，不在每个任务中重复。
4. 可执行的策略和证据交给 Rules、sandbox、脚本、测试和 CI。

默认 32 KiB 的项目指令预算是上限，不是目标。本项目的全局托管模板目标为 3–4 KiB、30–45 行，生成的项目 Context 更短。

## 从 GEB 保留什么

[GEB 系统](https://chunxiang.space/geb-system)有两个值得保留的思想：

GEB 是个人文章/课程站点，不是 OpenAI 规范或同行评审标准。它只提供设计启发；Rootloom 的 Codex 契约以官方平台文档和实际观察到的仓库行为为准。

- 文档应与其描述的代码和契约保持局部一致；
- 全局、模块和局部上下文应形成层级，而不是平铺成百科全书。

本项目将它们转换为 Codex 原生形式：

| GEB 思想 | Rootloom 的实现 |
| --- | --- |
| 项目宪法 | 根 `AGENTS.md` 只保留全仓库持久不变量 |
| 局部模块地图 | 只在真实模块边界创建嵌套 `AGENTS.md` |
| 代码/文档回环 | 命令、契约、所有权或架构改变时更新指导 |
| 冷启动 Context | 确定性的只读 `SessionStart` 扫描器 |

## 从 GEB 舍弃什么

本系统不会整段复制 GEB 提示词，明确舍弃：

- 身份扮演和强制称呼；
- 对隐藏推理语言或内部思考结构的要求；
- 与仓库证据无关的通用文件行数上限；
- 每个文件一行的完整清单；
- 所有源码都必须带 L3 文件头；
- 文档未扩张前阻塞全部工作；
- “文字与代码可以完全同构”的过度承诺。

这些模式会增加提示词负担、制造陈旧重复、扩大无意义 diff，并带来虚假的安全感。源码、Schema、测试、Manifest 和 CI 始终是可执行事实；`AGENTS.md` 只指向它们，并记录 Agent 容易遗漏的决策。

## 打磨后的全局成果

全局工作协议只保留六类稳定内容：

- 在所属边界修复根因；
- 保护无关修改；
- 三档比例化风险；
- 比例化证据与诚实完成声明；
- 深度审查保持显式例外；
- 本条命令、普通权限、所有权限的最小语义。

它不包含仓库命令、框架偏好、项目架构、人格文案或重复的工具手册。

## 打磨后的项目成果

在 Plan Session 之外，SessionStart Hook 最多向当前会话注入 4 KiB 可安全再生的增量事实，不写入仓库：

- 项目标识与主要 Manifest；
- 项目 Guidance 是否已经存在；
- 仅当项目 Guidance 缺失时，最多注入三条检测到的验证命令。

临时 Renderer 明确省略完整事实来源清单、顶级目录地图、Module Candidate 与通用验证契约。完整持久 Renderer 只在显式 Seed 时使用。

只有显式调用 `$project-guidance` 才会持久化托管区块。Active Guidance 可以自动
请求只读 Validate；单个文件可以用独立且精确的
`<!-- rootloom:refine-once version=1 -->` Marker 请求一次语义 Refine，并由成功写入
消费该 Marker。自然语言指导本身绝不授权持久化。用户区只保留持久且有路径证据的
不变量，例如所有权方向、生成代码边界、公开或持久化契约，以及权威架构或迁移文档。
单独安装的 `rootloom-memory` 插件可用可审查的风险和失败经验补充指导，但不能替代
`AGENTS.md` 权威或当前仓库证据。

Guidance 完成前会对照初始状态与授权路径检查最终工作树。验证应尽量使用 No-cache
选项，且不得留下 Cache、Coverage、Build 或其他生成输出；只允许清理由当前任务创建
的 Artifact。

嵌套指导按需创建。只有具备独立 Manifest、命令、所有权、契约或运维规则的目录才值得拥有自己的 `AGENTS.md`；普通目录和单个文件不创建。

## 维护判断标准

一条指导只有同时满足以下条件才应保留：它会改变未来的实现、审查、验证或安全决策；在普通代码变更后仍然有效；由真实路径支持；属于当前层级；且没有被更强的事实来源重复表达。

任一答案是否定的，就删除这句话，或把它留在本来就拥有它的权威文档中。
