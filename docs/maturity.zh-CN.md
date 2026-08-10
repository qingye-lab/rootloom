# 成熟度、保证与兼容性

Rootloom Core 是早期、单维护者产品。目标是在不把深度审查成本强加给安装与
普通工作的前提下，让 Codex 工程行为更审慎、更可检查。仓库目前还没有完成的
对比模型证据证明它能降低缺陷或审查时间，也没有第三方安全审计或 Fuzzing 报告。

`v2.0.0` 发布版已经通过 Linux Python 3.11–3.14、macOS、Windows 与固定 Codex CLI 契约矩阵。这只能证明这些环境中的已检查机制，不代表模型层面的工程质量保证。

## 可执行保证

- 确定性、无网络的项目 Context 扫描，SessionStart 上限为 4 KiB 且跳过 Plan Session，仓库写入只来自显式播种；
- 由精确整数 `version: 1` 托管本地策略控制的 fail-closed Hook；
- 个人 setup 目标的显式 install/upgrade/status/rollback，以及已安装 Hash 漂移拒绝；
- 普通本地锁串行、暂存恢复日志重放与逐文件原子替换；
- 拒绝漂移的备份恢复；
- 所有命令先完成解析，再以不使用 Shell 的方式执行；验证与 Git Capture 共享流式输出/时间上限及残留子进程清理；
- 仓库外、带 ownership marker 的 review bundle，以及有界 status、patch、指纹、命令数量与聚合日志；
- 显式按需、原子且不可替换发布的修改前 Baseline，以及 Draft → Seal 的严格 Tier 1/2 Contract；
- 两次一致的稳定 Repository Capture、Strict Evidence JSON、路径段感知 Scope Glob 与 HEAD/Ref/Index 不变绑定；
- 普通 Untracked 内容指纹、按任务分区的可应用有界文本 Patch 与风险信号，以及具有独立定向候选/分类结果上限、递归的 Metadata-observed 敏感捕获与敏感变化隔离；
- 证据诚实的 Revision 4 审查状态：操作方语义断言独立表达，发生遮蔽的审查不通过；
- 敏感删除路径精确确认；
- 综合任务、路径、Tracked/非敏感 Untracked Diff 与操作的可解释静态风险下限；
- 与已执行测试证据分离的风险专属验证建议；
- 单独安装、有界、过期感知的 Project Memory、加锁显式更新与 Core 不导入的严格 Reader Contract；
- 独立的 Agent Plugins 1.0.0 预览，具有封闭 Manifest、精确 Change/Review/Project
  Guidance Allowlist、路径包含关系、相对 Reference 检查、确定性来源一致性、可选只读
  Host Adapter 模板与一次性 Codex 安装冒烟；
- 仓库校验、单元测试与离线 Codex 兼容冒烟。

## 仍属于语义判断的部分

Rootloom 无法机械证明：

- 证据完整或真实；
- 根因判断正确；
- Change Contract 包含所有消费者；
- 选择的测试足够；
- 最终审查没有遗漏；
- 静态风险判断包含所有语义影响；
- 建议验证命令安全、充分或已经执行；
- 项目记忆仍然最新或正确。

Skills 负责指导这些判断，当前仓库与运行时证据必须再次验证它们。

## 个人安全边界

个人 Artifact Bundle 是可变的本地文件。验证命令属于可信的操作方输入，不是沙箱工作负载；命令参数与输出会原样保留，因此不能携带 Credential。Capture 不覆盖非敏感 Ignored 文件、Git 管理文件、外部状态、Detached Manager，也无法识别敏感源没有可观察变化时复制到普通路径的 Secret。Rootloom 的隐私分类器基于路径，不是内容感知型 Secret Scanner；更广泛的检测需要独立、可信的本地扫描器，并在发现进入 Rootloom Evidence 前完成脱敏。Setup 锁是普通协作锁。Setup 逐文件原子，但整个目标集不是一个原子事务。备份/回滚用于普通本地失误，不面向掉电恢复、敌对同用户竞态、签名审批、不可变审计、合规保留或多操作方环境。

这些 Assurance 机制作为未持续维护的 Archived Assurance Edition 保留在
`codex/enterprise-assurance`；Rootloom Core 不隐含它们，也不把它作为活跃产品线宣传。

## 兼容性

普通 CI 在 Linux 验证 Python 3.11–3.14，并在 macOS/Windows 验证可移植契约。固定
版本 Codex 兼容任务先证明原生 Marketplace/插件安装没有全局策略或审查门禁副作用，
再独立覆盖可选个人 Setup 往返与命令 Rules，并安装隔离的可移植包、验证其精确三
Skill Surface。live smoke 因需要登录 Codex 与真实模型回合而保持手动。

Agent Plugins 预览会按照仓库固定的 1.0.0 Working Draft 合同做机械校验：Manifest
Shape、精确 Skills、路径包含关系、相对资源和原生来源同步。可选的一次性 Codex 冒烟
还会证明已安装 Codex CLI 中的包安装、精确三 Skill 目录 Surface 与自包含 Helper。
静态与合成 Adapter 检查证明 Envelope 一致和失败不破坏。这不能证明运行时
发现、激活、工具可用性、模型行为、安装体验，也不能证明 Cursor、VS Code、GitHub
Copilot、Kiro 或其他客户端中的功能等价。Codex 仍是完整运行验证的原生环境；跨客户
端支持声明需要绑定客户端版本的真实冒烟证据。

Cursor、VS Code、GitHub Copilot CLI 与 Kiro 现在都有直接加载同一标准包的文档入口，
不需要平台 Manifest 或 Skill 分叉；可选模板只适配 Host 生命周期 Envelope。这只建立了有文档依据的结构路径，不等于 Rootloom
运行冒烟已通过。Copilot Coding Agent 也要等到兼容 Marketplace 入口发布并实际运行后，
才能形成安装声明。仓库尚未保存这些非 Codex Host 的当前版本通过证据，因此它们的
冒烟门槛仍明确处于 Pending 状态。

Personal Core 2.0 有意破坏 1.2.19 的 high-assurance Skill、严格 Runner CLI、自定义代理/profile setup、Human Review 格式、protected-deletion approval 与恢复日志契约。迁移前先使用 1.2.19 回滚。

Personal Core 2.1 保持 `rootloom-project-memory-v1` envelope 与旧条目可读；新增的 ID、证据、状态、路径和过期字段都是附加字段。原有 `rootloom-engineering-summary-v1` 字段继续保留，`risk_assessment` 与 `verification_plan` 为附加内容，旧的 `--risk low|medium|high` 调用仍然有效；但人工风险不能再压低静态检测下限。

Personal Core 2.2 保留 Summary Format 名称，并在 Revision 3 收紧显式治理证据。Advisory Finalization 默认仍不阻断。Strict 采用 Draft → Seal 生命周期、两次一致的稳定 Capture、Strict JSON、验证后 Evidence/Base 复检、Reference-aware 敏感变化隔离、Worktree 与 Git Common Directory 双边界包含检查、HEAD/Ref/Index 不变绑定及来自 Sealed Contract 的结构化 Claim，并默认使用 Quality Exit；`--strict-bundle-only` 保留显式非阻断 Strict Bundle。`semantic_coverage: reviewed` 是操作方断言，不是机器证明；语义未知最高只能得到 `MECHANICALLY_VERIFIED`，只有封存完整的机械证据加上该断言才能得到 `VERIFIED_CHANGE` 与 `passed: true`。纯验证必须使用 `--allow-no-change`，但非法证据和进程/Capture 错误优先于 `NO_CHANGE`。

Summary Revision 4 有意把最高状态的精确值从 `VERIFIED_CHANGE` 改为 `REVIEW_EVIDENCE_COMPLETE`，并独立暴露 `semantic_review: operator-asserted`。没有封存链的断言是 `SEMANTIC_REVIEW_ASSERTED`；发生敏感隔离时，原本完整的结果最高只能是 `REVIEW_REQUIRED_WITH_REDACTIONS` 与 `passed: false`。Strict Quality Exit 只有 `REVIEW_EVIDENCE_COMPLETE` 返回 0；Advisory Bundle Exit 继续保持非阻断。依赖 Revision 3 精确值的消费者必须按 `schema_revision` 分支。Git 现在与验证共用受控进程树所有者、关闭标准输入并使用显式时间预算；敏感发现使用共享定向 Pathspec 与独立的候选/分类结果上限；脏 Baseline 的风险与 Patch 输出复用同一任务分区；精确的 `seal_contract --recover` 只补全匹配的中断发布。

Personal Core 3.0 把同一 Summary Format 升级到 Revision 5，并将暗示身份的 `operator-sealed` Provenance 枚举改为 `intake-sealed` / `workflow-sealed`。新 Intake 生成 `rootloom-change-baseline-v3`，Baseline v2 继续可读、可 Seal。`evidence_complete` 是稳定自动化能力字段，详细 Quality Status 保持诊断用途。秘密材料隐私与安全领域源码风险由两个分类器分别负责：安全源码保留 Patch，CamelCase 材料保持 Metadata-only。每次稳定两轮 Capture 还增加默认 90 秒的单一总 Monotonic Deadline，并继续保留默认 30 秒的逐 Git 上限。这些公共/持久契约变化使 3.0 成为 Major Release；历史 Revision 4 与 Baseline v2 Artifact 不会被重写。

Personal Core 3.1 在不改变 Summary Revision 5 的前提下收窄秘密材料命名。环境模板与公共证书格式保留可审查 Patch，并作为安全领域证据提高风险；无关 `.env*` 名称恢复为普通路径。默认 Intake 输出仍是 Baseline v3。新增的 Intake-only `--reviewable-path` 只有被使用时才生成 Baseline v4，把精确声明密封进 Policy Hash，既可固定默认已可审查的 Artifact，也可降级歧义材料，并拒绝强秘密或显式声明的 Sensitive Root。Baseline v2/v3/v4 Reader 与 Sealer 共存；未采用新参数的 Consumer 继续取得既有 v3 契约。

Personal Core 3.2 保持 v3/v4 Wire Format，但拒绝 Ignored 或被 Git Index 标志隐藏的 Reviewable Target、Hardlink、大小写歧义和常见私钥名称。DER 与 PEM 一样默认属于 Metadata-only 歧义材料，因为两种编码都可能包含私钥。Summary Revision 5 以附加字段披露密封的 Reviewability Policy 与捕获的文件身份元数据；按仓库 SemVer 规则，该可选字段使 3.2 成为 Minor Release。

Personal Core 3.3 批量交付 Core Reset，同时继续冻结这些 Wire Version。历史 Baseline Reader 只校验结构与 Hash，不再套用最新 Reviewability 分类器；Finalizer 独立执行当前策略，并在读取不兼容 Reviewable 内容前返回 `reintake-required`。Reviewable 声明使用固定 64 项上限，Provenance 区分已验证 Intake Policy 与最终 Capture Observation，SessionStart Context 改为只读，Project Memory 明确标为 Experimental。

Personal Core 3.4 在不改变 Baseline 或 Summary Format 的前提下，闭合动态 Context 与 Experimental Project Memory 的可执行边界。SessionStart 使用独立的增量 Renderer，把完整 Additional Context 限制在 4 KiB，并跳过 Plan Session。Analyzer 与 Finalizer 不再根据仓库中存在 `.project-memory/` 推断同意；调用方通过新增的 `--include-project-memory` Flag 显式选择，敏感变化隔离仍会阻止仓库读取。不依赖隐式 Memory 读取的现有自动化继续沿用原有 CLI 与 Evidence Contract。

Rootloom 4.0 把公共 Core 收缩为 Change、Review、Project Guidance 与 Setup。
高风险和 Evidence 行为变为按需 Change Mode Reference；确定性 Evidence Helper
迁移到 `plugins/rootloom/resources/evidence/`；Seeder 与 Refiner 合并到
`project-guidance`；持久决策记录成为 Governed 步骤。Project Memory 迁移到单独
安装的 `rootloom-memory` 插件，Core Analyzer/Finalizer 删除
`--include-project-memory`。Baseline v2–v4、Summary revision 5、Contract、
Manifest 与 Seal Wire Format 保持不变。参见 [3.x 迁移指南](migration-4.0.zh-CN.md)
与 [Core Reset Eval](../evals/core-reset/)。

Rootloom 4.1 保持这些冻结 Format 和四个公共 Skill 的边界。其 v2 评测 Harness 会
记录实际 Codex Token 字段、精确路由和隔离的重复运行；但正式行为验收仍需要一份经过
审阅、至少三轮并绑定最终 Core Tree 的候选结果。`prepare`/`finish` Evidence 编排只是
附加的易用性封装，不新增 Assurance State，也不构成机器证明；语义审查 Flag 仍是操作方
断言。SessionStart 会省略不安全的 package-script 名称，而不会渲染来自不可信元数据的
类命令文本。

Rootloom 4.2.1 保留一份绑定发布 Core Tree 的 135 Cell 结果。当前候选完成 45/45 个任务、
精确路由 45/45，且没有 Scope Escape 或虚假 Test-pass 声明；结构尺寸、Token、Direct
命令数与成功配对耗时的正式比较均通过。这是记录的 Codex/Model 合同下的 Fixture 证据，
不保证所有 IDE 或 Model 的行为完全相同。
