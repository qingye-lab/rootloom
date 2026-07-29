# 案例：命令通过了，审查仍然失败

**简体中文** · [English](passing-command-failed-review.md)

## 摘要

一个验证命令以退出码 0 结束，却在执行期间创建了被忽略的 `.env`，并把其中的合成值复制到普通 Untracked 文件。如果只检查命令退出码，这次运行可能被判断为成功。

Rootloom 的验证后 Repository Capture 改变了最终决定：它发现了新增敏感路径，在保留变更内容前触发隔离，把最终 Capture 标记为未保持，并返回失败。合成值没有进入输出 Patch。

这是 Rootloom 开发自身时产生的真实回归，它只证明一个明确结论：

> 当被审查的仓库状态已经变化时，验证命令通过并不足以证明任务可以完成。

本案例不比较语言模型，也不宣称 Rootloom 可以证明代码正确或安全。

## 背景

Rootloom 的 Strict Review 会绑定：

- Intake 时的 Repository 与 Git 状态；
- 显式路径范围；
- Verification Command 与行为 Claim；
- 验证结束后的全新 Repository Capture。

敏感材料按路径分类，内容始终不读取。当敏感元数据相对 Reference Capture 发生变化时，Rootloom 必须在普通内容捕获前隔离全部变更端点。

对应不变量是：

```text
验证可能执行仓库代码
→ 验证期间仓库状态可能变化
→ Final Capture 必须发现变化
→ 敏感漂移必须在保留 Patch 前隔离内容
→ 命令成功不能覆盖 Capture Preservation 失败
```

## 最强完成声明

验证子进程成功退出。如果完成判断只依赖命令退出码，审查就可能报告成功。

但该声明并不完整，因为命令本身创建了：

- 包含合成 Token 的被忽略 `.env`；
- 包含相同合成值的普通 `leaked.txt`。

最终状态已经明显不同于进入验证时的状态。

## 反例

该回归会创建临时 Git 仓库、忽略 `.env`、开始 Governed Change，并执行一条在退出 0 前写入两个文件的验证命令。

Rootloom 必须得到以下决策：

| 观察 | 必需决策 |
| --- | --- |
| Verification Command 退出 0 | 记录命令结果，但暂不完成 |
| 新增被忽略敏感路径 | 启用 Sensitive-change Quarantine |
| 变更内容可能包含合成值 | 全部变更端点只保留元数据 |
| Final Capture 与 Reference Capture 不同 | 设置 `capture_preserved: false` |
| Capture Preservation 失败 | Strict Result 返回非零 |

回归还会检查合成值没有进入 `diff.patch`。

## Owning Boundary 的修复

修复没有在某个调用方为 `.env` 添加特殊判断，而是修改 Repository Capture 边界：

1. 在普通内容读取前发现已知与当前敏感路径的 Reference-aware 并集；
2. 把敏感元数据与 Reference Capture 比较；
3. 观察到敏感漂移时隔离全部变更端点；
4. 停止可能暴露内容的额外仓库读取；
5. 把敏感路径作为显式 Task Change 与范围决策；
6. Capture Preservation 失败时拒绝成功完成声明。

这样，最终决定仍由拥有 Repository Evidence 的组件负责，而不是交给单条验证命令。

## 复现当前回归

在 Rootloom 仓库根目录执行：

```bash
python3 -m unittest \
  tests.test_engineering_change.EngineeringChangeTests.test_new_ignored_sensitive_path_is_a_scoped_task_change \
  tests.test_engineering_change.EngineeringChangeTests.test_verification_new_ignored_sensitive_path_quarantines_before_recapture
```

2026-07-16 在 macOS、Python 3.13 上的实际结果：

```text
..
----------------------------------------------------------------------
Ran 2 tests in 1.228s

OK
```

两个测试分别覆盖相邻不变量：

- Finalization 前新增的被忽略敏感文件会成为显式 Task Change、触发隔离、不进入 Patch，并暴露不足的路径范围；
- Verification Command 创建的被忽略敏感文件会被验证后重新采集发现，复制内容保持未读取，并让 Capture Preservation 失败。

## 本案例证明什么

- Rootloom 可以区分命令成功与最终仓库状态保持。
- Sensitive-change 决策具有自动化回归。
- 测试同时验证内容不保留与 Strict Result 非零。
- Owning-boundary 修复同时覆盖验证前新增与验证期间新增。

## 本案例不证明什么

- 不证明 Rootloom 能发现所有敏感文件；当前分类是 Path-based。
- 不证明模型的诊断或语义审查一定正确。
- 不会让 Verification Command 变得安全；它们仍属于可信操作方输入。
- 不比较 Rootloom 与 Vanilla Codex、Spec Kit、OpenSpec、Superpowers 或其他模型。
- 不构成独立安全审计。

## 证据

- 已接受决策：[Personal Engineering Intelligence Contract](../decisions/2026-07-14-personal-intelligence-contract.md)
- 回归测试：[`tests/test_engineering_change.py`](../../tests/test_engineering_change.py)
- Capture Owner：[`runner/state.py`](../../plugins/rootloom/resources/evidence/runner/state.py)
- Final Decision Owner：[`finalize_change.py`](../../plugins/rootloom/resources/evidence/finalize_change.py)
- 包含该回归的发布：[Rootloom Personal Core 2.2.2](https://github.com/liyanqing90/rootloom/releases/tag/v2.2.2)
