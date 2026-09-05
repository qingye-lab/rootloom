# 参与贡献

感谢你帮助改进 Rootloom。本项目偏好范围清晰、基于证据的修改，不鼓励宽泛自动化和推测式抽象。

English: [CONTRIBUTING.md](CONTRIBUTING.md)

## 创建 Issue 前

- 搜索已有 Issue 和 Discussion。
- 可复现缺陷请使用 Bug 模板。
- 提供 Codex 版本、操作系统、Python 版本、probe 输出，以及能够展示问题的最小安全仓库样例。
- 移除 Token、私有路径、专有源码和其他敏感数据。

安全漏洞请按照 [SECURITY.md](SECURITY.md) 私下报告，不要使用公开 Issue。

## 开发环境

需要 Git、Python 3.11+ 和 `make`：

```bash
git clone https://github.com/liyanqing90/rootloom.git
cd rootloom
make validate
```

运行时和测试都不依赖 Python 标准库之外的包。

## 目录结构

```text
.agents/plugins/marketplace.json       Git Marketplace 目录
plugins/rootloom/                      可安装的四入口 Core 插件
  .codex-plugin/plugin.json            Codex 原生插件元数据
  assets/system/                       可安装的全局指导与命令 Rules
  hooks/                               可选的只读 SessionStart 项目 Context
  skills/                              Change、Review、Project Guidance 与 Setup
  resources/evidence/                  显式 Analyzer/Baseline/Seal/Finalizer Helper
portable/rootloom/                     生成的三 Skill Agent Plugins 预览
adapters/rootloom/                     生成的可选消费者仓库 Host 模板
experiments/rootloom-memory/           单独安装的实验性 Memory 插件
evals/core-reset/                      3.4 与 4.0 的结构/行为 Ablation
tests/                                 单元与真实集成检查
scripts/validate_repo.py               仓库契约校验
scripts/sync_portable_plugin.py        确定性可移植包同步
scripts/sync_host_adapters.py          确定性 Host Adapter 同步
docs/                                  设计和排障文档
assets/                                README 配图
```

## 设计规则

修改必须保持以下不变量：

1. 自动启动行为保持确定性和本地执行。
2. 不安全或模糊状态应跳过，不能覆盖。
3. 无托管标记的指导始终归用户所有。
4. 扫描器陈述必须由可检查的仓库证据支持。
5. 扫描期间绝不执行仓库代码。
6. 遍历范围、文件数量、文件大小和嵌套深度保持有界。
7. 除非有经过评审的强需求，运行时只使用 Python 标准库。
8. 语义判断保留在 Skills 中，不进入确定性自动核心。
9. 全局 setup 必须先计划、加锁串行、备份、逐文件原子写入并拒绝冲突。
10. Hooks 不得宣称超过当前事件 API 的执行强度。
11. 本地 `git commit` 必须与远程发布和破坏性 Git 操作分开治理。

## 修改流程

1. 创建范围清晰的分支。
2. 行为变化应新增或更新回归测试。
3. 安装方式、公共行为或用户配置变化时同步更新中英文 README。
4. 架构或排障契约变化时更新相应文档。
5. Change、Review 或 Project Guidance 变化后重新生成可移植包；Project Guidance Helper
   或锁变化后重新生成 Host Adapter。
6. 运行 `make check-changed BASE=origin/main`；只有在影响无法界定、共享测试选择
   基础设施发生变化，或明确发布门禁要求全量套件时，才运行 `make check`。
7. 检查最终 Diff 中是否包含秘密、临时文件、生成噪声或无关修改。

提交信息应简短并使用祈使语气，例如：

```text
Handle Cargo workspace module boundaries
```

发布验收采用实际变更所需检查与既有 CI。历史 135 个 Cell 的 Core Reset 矩阵保留为
可选研究工具，不再是固定发布门禁。工作流变更采用明确选定的有界行为对比，如实报告
失败与限制；不以最低篇幅、删减比例或固定流程措辞替代可执行行为测试。

## 测试原则

优先使用真实临时 Git 仓库和行为断言。避免网络请求、任意 sleep、依赖偶然空白的快照，以及能够用小型文件系统样例替代的 Mock。

默认使用影响范围内的精准验证。`make check-changed BASE=<ref>` 始终执行仓库校验，并把
已提交、已暂存及未暂存的受跟踪变更映射到对应组件测试；默认排除无关未跟踪文件。只有
全部未跟踪文件都属于当前任务时才使用 `INCLUDE_UNTRACKED=1`，新增文件也可直接选择明确
的组件 Target。未知可执行路径，或测试选择器、校验器、Makefile、CI Workflow 自身变化
时，失败关闭到全量套件。组件 Target 包括 `make test-setup`、`test-guidance`、
`test-packaging`、`test-change`、`test-evidence`、`test-memory`、`test-web`。

CI 对 Pull Request 运行精准测试，在 `main` 保留一次规范性全量套件，在最新支持的
Python 上只重跑受影响模块，并仅在 macOS/Windows 运行相关可移植契约。完整 Python
版本矩阵每周定时运行，也可手动触发。除非新增平台或运行时能证明一种独立风险，
否则不要重复运行相同测试。

手动真实冒烟测试要求本机 Codex 已登录。它会把当前 checkout 安装进可丢弃的 `CODEX_HOME`，不会修改用户主配置：

```bash
make smoke
```

该测试依赖已登录的 Codex，并会执行一次真实模型回合，因此不能进入普通 CI。Hook 信任只在可丢弃测试目录中绕过。

## 公共契约版本规则

Rootloom 对可观察 JSON、CLI、持久证据、Setup 与插件行为执行 Semantic Versioning，而不只针对 Python API：

- Patch：修复实现缺陷，但不改变既有字段、枚举、Flag、退出码或持久格式的公开语义。
- Minor：新增旧 Consumer 可以忽略的可选字段、Flag 或兼容格式/行为，并允许新旧 Producer/Consumer 共存。只有枚举被明确声明为开放集合、且未知值可被安全忽略时，新增枚举值才属于 Minor。
- Major：删除或重命名字段/Flag、替换枚举值、向封闭/穷尽枚举新增值、改变退出语义、对既有值作不兼容重解释，或在没有兼容 Reader 时强制新的持久格式。

即使顶层 `format` 不变，Schema Revision 变化也不自动等于 Minor；必须评估真实 Producer/Consumer 契约与混合版本行为。自动化优先读取 `evidence_complete` 等稳定能力字段，把详细状态枚举视为诊断展示；不得为了兼容而保留具有误导性的权威状态别名。

已经发布的 Tag 与 Release 保持不可变。发布后的普通修复使用新版本，不能移动或删除原 Tag。

兼容的边界修复先积累在 `Unreleased`，再批量正式发布。发布事实由 GitHub PR、Actions、Tag 与 Release 管理；仓库不再加入一次性 `.codex/plans/`、Publication Record、Final Record、Release ID、Tag Object ID 或 CI Run ID。`CHANGELOG.md` 只记录用户可观察变化。

## Pull Request

PR 应说明：

- 可观察问题或改进；
- 所属边界和设计选择；
- 用户可见或兼容性影响；
- 实际执行的验证；
- 剩余风险或明确不支持的情况。

提交贡献即表示你同意按照本项目 MIT 许可证授权该贡献。
