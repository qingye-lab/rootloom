# 只有存在消费者证据时才启用运行时兼容

- 状态：accepted
- 日期：2026-08-10
- 负责人：Rootloom 维护者
- 范围：Change 路由、Governed 兼容、审查指导与 Core Reset 评测
- 取代：无
- 被取代：无

## 背景

Rootloom 4.2 已经把 Adapter、Dual Path、Versioning 与 Migration 定义为条件性风险控制，
但 Change 路由在区分权威数据与可再生内部记录之前，就把 Schema 和持久化合同列为
Governed 信号。因此模型可能把带版本号的临时产物误判为生产兼容合同，并把回滚或历史
回放混同为“新运行时必须读取旧格式”。

## 证据

| 声明 | 类型 | 来源与环境 | 观察时间 | 引用 | 新鲜度 / 脱敏 |
| --- | --- | --- | --- | --- | --- |
| 4.2 Change 路由把 Schema 与持久化合同列为 Governed 信号，但没有先判断是否可再生 | 事实 | 不可变 `v4.2.0` Skill | 2026-08-10 | `plugins/rootloom/skills/operating-coding-change/SKILL.md` | 公共 Tag；无敏感数据 |
| 4.2 Governed 兼容章节在盘点消费者后直接讨论增量扩展与共存 | 事实 | 不可变 `v4.2.0` Reference | 2026-08-10 | `plugins/rootloom/skills/operating-coding-change/references/governed-change.md` | 公共 Tag；无敏感数据 |
| Core Reset 没有“版本化产物可再生且当前运行时必须拒绝旧格式”的场景 | 事实 | 已发布的 14 场景套件 | 2026-08-10 | `evals/core-reset/scenarios.json`；`evals/core-reset/reports/4.2.0.md` | 仓库源码 |

## 决策

版本号或序列化产物本身不会形成 Governed 兼容合同。路由 Schema 或格式工作前，Rootloom
必须先确认产物是否权威或不可替代，以及新运行时在切换后是否必须遇到旧实例。

可再生内部产物默认保持 Scoped，除非存在其他 Governed 风险。当前运行时只接受当前
合同；回滚恢复完整旧版本，历史回放使用匹配的旧运行时。只有仓库证据明确指出切换后
仍存在真实旧消费者或存量实例时，Rootloom 才能建议旧格式 Reader、Adapter、Dual Path、
Flag 或 Migration。

该规则由 Change 路由、Governed Compatibility Reference、全局工作协议与数据/迁移
审查 Reference 共同拥有；不新增 Evidence 格式、状态或强制产物。

## 备选方案

- 继续依靠“只有确实降低现实风险时才使用”——拒绝，因为缺少的是发生在该判断之前的
  产物权威性分类，版本化临时记录仍会被可预测地过度路由。
- 所有版本化产物仍走 Governed，只在报告中写兼容不适用——拒绝，因为加载兼容工作流
  本身已经增加不必要的 Prompt 与决策成本。
- 删除兼容指导——拒绝，因为既有外部消费者与不可替代存量状态仍然需要共存和迁移控制。

## 后果

- 正面：回滚、历史回放与生产兼容成为彼此独立的决策。
- 正面：可再生版本化记录保持在自包含 Scoped 路径，不再默认获得 Legacy Reader 或 Migration。
- 负面：语义路由必须判断产物权威性，不能只依赖 Schema 或版本号是否存在。
- 运维：现有 Public API 与 Data Migration 场景继续覆盖 Governed；新增当前版本专用的
  可再生产物场景防止回归。

## 验证

- 聚焦测试断言新的路由文案、兼容门槛与 Current-only Scorer。
- Core Reset 要求可再生版本化产物以 Scoped 且零 Reference 路由，只接受 v2，并拒绝 v1
  与未来版本。
- 仓库验证把扩展后的 15 场景发布结果绑定到最终 Core Tree。

## 重新评估条件

- 真实项目证明：没有切换后消费者时，可再生产物仍因其他运维原因需要混版本运行时支持。
- 路由无法在可接受的干预或任务成本内区分权威状态与生成产物。
