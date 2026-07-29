# Case study: the command passed, but the review failed

[简体中文](passing-command-failed-review.zh-CN.md) · **English**

## Executive summary

A verification command returned exit code 0 after creating a newly ignored `.env` file and copying its synthetic value into an ordinary untracked file. A command-only gate could have treated that run as successful.

Rootloom's post-verification repository capture changed the decision. It detected the new sensitive path, activated quarantine before retaining changed content, marked the captured state as unpreserved, and returned failure. The synthetic value did not enter the emitted patch.

This is a real regression from Rootloom's own development. It demonstrates one narrow claim:

> A passing verification command is not sufficient evidence when the repository state being reviewed has changed.

It does not compare language models and does not claim that Rootloom proves code correctness or security.

## Context

Rootloom's strict review binds a change to:

- an intake repository and Git state;
- an explicit path scope;
- verification commands and behavior claims;
- a fresh repository capture after verification.

Sensitive material is path-classified and content-unread. When sensitive metadata changes relative to the reference capture, Rootloom must quarantine all changed endpoints before ordinary content capture.

The relevant invariant is:

```text
verification may execute repository code
→ repository state may change during verification
→ final capture must detect that change
→ sensitive drift must quarantine content before patch retention
→ command success cannot override failed capture preservation
```

## The strongest completion claim

The verification subprocess exited successfully. If completion were based only on the command exit code, the review could report success.

That claim was incomplete because the command itself created:

- an ignored `.env` path containing a synthetic token;
- an ordinary `leaked.txt` path containing the same synthetic value.

The final state therefore differed materially from the state that entered verification.

## The counterexample

The focused regression constructs a temporary Git repository, ignores `.env`, begins a governed change, and runs a verification command that writes both files before exiting 0.

The expected Rootloom result is:

| Observation | Required decision |
| --- | --- |
| Verification command exits 0 | Record the command result, but do not complete yet |
| A new ignored sensitive path appears | Activate sensitive-change quarantine |
| Changed content may contain the synthetic value | Keep changed endpoints metadata-only |
| Final capture differs from the reference capture | Set `capture_preserved: false` |
| Capture preservation fails | Return a nonzero strict result |

The regression also checks that the synthetic value is absent from `diff.patch`.

## What changed at the owning boundary

The fix did not add a caller-side exception for `.env`. It changed the repository-capture boundary:

1. discover the reference-aware union of known and current sensitive paths before ordinary content reads;
2. compare sensitive metadata with the reference capture;
3. quarantine every changed endpoint when sensitive drift is observed;
4. disable additional repository reads that could expose content;
5. surface the sensitive path as an explicit task change and scope decision;
6. refuse a successful completion claim when capture preservation fails.

This keeps the decision at the component that owns repository evidence rather than at an individual verification command.

## Reproduce the current regression

From the Rootloom repository root:

```bash
python3 -m unittest \
  tests.test_engineering_change.EngineeringChangeTests.test_new_ignored_sensitive_path_is_a_scoped_task_change \
  tests.test_engineering_change.EngineeringChangeTests.test_verification_new_ignored_sensitive_path_quarantines_before_recapture
```

Observed on 2026-07-16 with Python 3.13 on macOS:

```text
..
----------------------------------------------------------------------
Ran 2 tests in 1.228s

OK
```

The two tests prove adjacent parts of the invariant:

- a newly ignored sensitive file present before finalization becomes an explicit task change, triggers quarantine, stays out of the patch, and violates an insufficient path scope;
- a newly ignored sensitive file created by the verification command is detected by post-verification recapture, keeps copied content unread, and prevents capture preservation.

## What this case proves

- Rootloom can distinguish command success from final repository-state preservation.
- The sensitive-change decision is exercised by an automated regression test.
- The test verifies both content non-retention and a nonzero strict result.
- The owning-boundary fix covers a pre-verification addition and a during-verification addition.

## What this case does not prove

- It does not prove that Rootloom finds every sensitive file; classification is path-based.
- It does not prove that the model's diagnosis or semantic review is correct.
- It does not make verification commands safe to run; they remain trusted operator input.
- It does not compare Rootloom with Vanilla Codex, Spec Kit, OpenSpec, Superpowers, or another model.
- It does not establish an independent security audit.

## Evidence

- Accepted decision: [Personal engineering intelligence contract](../decisions/2026-07-14-personal-intelligence-contract.md)
- Regression tests: [`tests/test_engineering_change.py`](../../tests/test_engineering_change.py)
- Capture owner: [`runner/state.py`](../../plugins/rootloom/resources/evidence/runner/state.py)
- Final decision owner: [`finalize_change.py`](../../plugins/rootloom/resources/evidence/finalize_change.py)
- Release containing the regression: [Rootloom Personal Core 2.2.2](https://github.com/liyanqing90/rootloom/releases/tag/v2.2.2)
