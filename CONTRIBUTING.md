# Contributing

Thank you for helping improve Rootloom. The project favors small, evidence-backed changes over broad automation or speculative abstraction.

中文说明见 [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md).

## Before opening an issue

- Search existing issues and discussions.
- Use the bug template for reproducible failures.
- Include the Codex version, operating system, Python version, probe output, and the smallest safe repository fixture that demonstrates the problem.
- Remove tokens, private paths, proprietary source, and other sensitive data.

Security vulnerabilities must follow [SECURITY.md](SECURITY.md), not the public issue tracker.

## Development setup

Requirements: Git, Python 3.11+, and `make`.

```bash
git clone https://github.com/liyanqing90/rootloom.git
cd rootloom
make validate
```

There are no runtime or test dependencies outside the Python standard library.

## Repository layout

```text
.agents/plugins/marketplace.json       Git marketplace catalog
plugins/rootloom/                      Installable four-entry Core plugin
  .codex-plugin/plugin.json            Codex-native plugin metadata
  assets/system/                       Installable global guidance and command Rules
  hooks/                               Optional read-only SessionStart project context
  skills/                              Change, Review, Project Guidance, and Setup
  resources/evidence/                  Explicit Analyzer/Baseline/Seal/Finalizer helpers
portable/rootloom/                     Generated three-Skill Agent Plugins preview
adapters/rootloom/                     Generated opt-in consumer-repository host templates
experiments/rootloom-memory/           Separately installable experimental Memory plugin
evals/core-reset/                      3.4 versus 4.0 structural and behavioral ablation
tests/                                 Unit and live integration checks
scripts/validate_repo.py               Repository contract validation
scripts/sync_portable_plugin.py        Deterministic portable-package synchronization
scripts/sync_host_adapters.py          Deterministic host-adapter synchronization
docs/                                  Design and troubleshooting docs
assets/                                README visuals
```

## Design rules

Changes should preserve these invariants:

1. Automatic startup behavior remains deterministic and local.
2. Unsafe or ambiguous state results in a skip, not an overwrite.
3. Unmarked guidance remains user-owned.
4. Scanner claims are supported by inspectable repository evidence.
5. Repository code is never executed during scanning.
6. Traversal, file count, file size, and nested depth stay bounded.
7. The runtime remains Python-standard-library only unless a strong, reviewed need proves otherwise.
8. Semantic judgment stays in Skills, outside the deterministic automatic core.
9. Global setup remains plan-first, lock-serialized, backed up, atomic per file, and conflict refusing.
10. Hooks never claim stronger enforcement than the current event API provides.
11. Local `git commit` remains distinct from remote publication and destructive Git operations.

## Making a change

1. Create a focused branch.
2. Add or update a regression test for behavior changes.
3. Update both READMEs when installation, public behavior, or user-facing configuration changes.
4. Update architecture or troubleshooting docs when their contracts change.
5. Regenerate the portable package when Change, Review, or Project Guidance changes;
   regenerate host adapters when the Project Guidance helper or lock changes.
6. Run `make check-changed BASE=origin/main`; use `make check` only when impact cannot
   be bounded, shared test-selection infrastructure changed, or an explicit release
   gate requires the full suite.
7. Review the final diff for secrets, temporary files, generated noise, and unrelated edits.

Commit messages should be short and imperative, for example:

```text
Handle Cargo workspace module boundaries
```

Release acceptance uses the checks justified by the change plus existing CI. The historical
135-cell Core Reset matrix remains an optional research tool, not a standing release gate.
Workflow changes should use a bounded, explicitly selected behavioral comparison and report
failures and limitations honestly. Do not enforce minimum prose size, a shrink percentage,
or exact procedural wording as a substitute for executable behavior tests.

## Testing guidance

Prefer real temporary Git repositories and behavioral assertions. Avoid network calls, arbitrary sleeps, fixture snapshots tied to incidental whitespace, and mocks when a small filesystem fixture can prove behavior directly.

Impact-scoped verification is the default. `make check-changed BASE=<ref>` always runs
repository validation and maps committed, staged, and unstaged tracked changes to their
component tests. It excludes unrelated untracked files by default; use
`INCLUDE_UNTRACKED=1` only when every untracked file belongs to the task, or select an
explicit component target for new files. Unknown executable paths and changes to the
selector, validator, Makefile, or CI workflow fail closed to the full suite. Component
targets are `make test-setup`, `test-guidance`, `test-packaging`, `test-change`,
`test-evidence`, `test-memory`, and `test-web`.

CI runs focused pull-request checks, one canonical full suite on `main`, affected tests
on the newest supported Python, and only relevant portable contracts on macOS/Windows.
The full supported-Python matrix is scheduled weekly and available through manual
workflow dispatch. Do not add another platform or runtime lane unless it proves a
distinct risk.

The manual live smoke test requires a logged-in local Codex session. It installs the current checkout into a disposable `CODEX_HOME` and does not mutate the user's main Codex configuration:

```bash
make smoke
```

Do not make the live smoke test part of normal CI because it depends on a logged-in Codex installation and performs a real model turn. Hook trust is bypassed only inside the disposable test home.

## Versioning public contracts

Rootloom applies Semantic Versioning to observable JSON, CLI, persisted evidence, setup, and plugin behavior—not only to Python APIs:

- Patch: correct an implementation defect without changing the documented meaning of an existing field, enum, flag, exit code, or persisted format.
- Minor: add an optional field, flag, or compatible format/behavior that old consumers can ignore and existing producers/consumers can coexist with. Adding an enum value is Minor only when the enum is explicitly documented as open and unknown values are safely ignored.
- Major: remove or rename a field/flag, replace an enum value, add a value to a closed/exhaustive enum, change exit semantics, reinterpret an existing value incompatibly, or make a new persisted format mandatory without a compatibility reader.

A schema revision inside the same top-level `format` does not automatically make a change Minor. Review the real producer/consumer contract and mixed-version behavior. Prefer stable capability fields such as `evidence_complete` for automation; treat detailed status enums as diagnostic presentation. Never preserve a misleading status as an authoritative compatibility alias.

Published tags and Releases are immutable. A post-release correction receives a new version; it never moves or deletes the existing tag during ordinary release maintenance.

Accumulate compatible boundary fixes under `Unreleased` and batch formal releases. GitHub PRs, Actions, tags, and Releases own publication facts; do not add one-time `.codex/plans/`, Publication Records, Final Records, Release IDs, tag-object IDs, or CI run IDs to the repository. `CHANGELOG.md` records only user-observable changes.

## Pull requests

Pull requests should explain:

- the observable problem or improvement;
- the owning boundary and design choice;
- user-visible or compatibility impact;
- exact verification performed;
- remaining risks or intentionally unsupported cases.

By contributing, you agree that your contribution is licensed under the project's MIT License.
