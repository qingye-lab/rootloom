# 从 Rootloom 4.0 迁移到 4.1

Rootloom 4.1 保持四个公共 Skill 和所有冻结的 Evidence Wire Format。已有 Baseline
v2–v4、Summary revision 5、Change Contract、Review Manifest 与 Seal 都继续可读，
无需迁移 Artifact。

## Direct Change 路由

机械、局部、可逆的工作现在走明确的 Direct 快速路径：不读取 Change Reference，只应
检查目标、完成修改、运行最小相关检查并检查目标 Diff。脏工作树本身不会使任务切换为
Governed 或 Evidence Mode；它仍是必须精确保留的已有工作。
文件数量或局部 Callable/Signature 形态同样不能证明公共契约存在；Governed 路由必须
有共享/外部消费者、兼容义务或其他 Governed 风险信号。

初始根因未知时保持 Scoped，并通过有限诊断确定所属边界。只有诊断后仍存在材料级根因
不确定性，或出现其他 Governed 信号时才升级；公开/持久契约与显式证据请求仍分别进入
Governed 或 Evidence 路由。

## Strict Evidence 快捷路径

原有 `begin_review.py`、`seal_contract.py` 与 `finalize_change.py` 仍受支持。常见的
Strict 生命周期可以使用新增的编排器：

```bash
python3 <plugin-root>/resources/evidence/orchestrate_evidence.py prepare \
  --repo /absolute/path/to/repository \
  --task '描述这项变更' \
  --review-dir /absolute/path/outside-repository/run/intake \
  --path src/owner.py \
  --verify 'python3 -m unittest tests.test_owner -v' \
  --target tests.test_owner \
  --primary-evidence '覆盖调用方可见行为' \
  --invariant-evidence '覆盖所属规则' \
  --adjacent-evidence '覆盖相邻替代路径'

# 完成并审查范围内的改动。

python3 <plugin-root>/resources/evidence/orchestrate_evidence.py finish \
  --repo /absolute/path/to/repository \
  --task '描述这项变更' \
  --review-dir /absolute/path/outside-repository/run/intake \
  --output /absolute/path/outside-repository/run/bundle \
  --semantic-review-confirmed
```

缺陷修复时，在 `prepare` 增加 `--root-cause-alignment PASS`。同一条已密封验证命令能够
覆盖额外要求时，增加明确的 `--claim CLAIM-ID=EXPECTED-EVIDENCE`；如果需要彼此不同的专用
验证命令，请使用底层生命周期。Orchestrator 是单验证命令的便捷路径，不是多 Target/
Command、迁移、Mixed-version、安全边界或 Build + Runtime 证明的默认入口。`finish`
只读取已密封的命令，并要求确认语义审查；它不会让未审查的 Bundle 变为通过。

## 评测与发布证据

历史 v1 矩阵和 4.0 结果仍是历史证据。新候选使用 v2 套件，包含 Guidance 与 Setup
场景、实际完成回合 Token 字段、精确路由评分、确定性随机化和每次运行独立的 Codex
Home。
当前 `rootloom-core-reset-mechanical-v3` Scorer 能识别合法的托管 Marker 属性、
绝对或 Codex-home 相对的缓存 Skill 路径，以及有界的等价质量表述；正式门禁会拒绝
缺少或使用旧 Scoring Identifier 的结果。若命令把一个有界 Shell Loop 中的相对
Reference 列表连接到已观察到的缓存 Skill 目录，Scorer 也会解析这些路径。

使用 `make core-reset-eval` 执行当前结构门禁；它有意不声称行为验收。正式候选需要一份
至少三轮的已评分 v2 结果：

```bash
make core-reset-release-eval CORE_RESET_RESULTS=/absolute/path/results-v2.json
```

原始模型 Transcript 保留在仓库外，并把净化后的结果绑定到最终
`plugins/rootloom/` Tree Digest。

仓库保留的 [`results-4.1.0.json`](../evals/core-reset/results-4.1.0.json) 与
[候选报告](../evals/core-reset/reports/4.1.0.md)包含全部 126 个 Cell。报告记录正式
门禁未通过：路由和质量证据通过，两项效率阈值未通过。版本 Tag 会运行该结果并失败关闭。

## Project Guidance Hook

SessionStart Renderer 现在会忽略带有 Shell 风格或指令风格字符的 package-script 名称。
`test:unit` 等正常名称仍会出现。若仓库使用不再出现在临时 Context 中的非常规 Script
名称，请从 package manifest 显式运行它，不要把它复制到 Guidance 中。

Hook 仍然只读。Repository Guidance 可以自动请求 Validate；持久 Seed/Refresh/Refine
需要用户明确意图。唯一例外是独立且精确的
`<!-- rootloom:refine-once version=1 -->` Marker，它只授权对标记文件进行一次 Refine，
并由成功写入消费。
