---
name: setup-rootloom
description: Plan, install, inspect, update, or roll back Rootloom Personal Core in a user's Codex home. Supports Skills-only, guidance, and the recommended personal preset. Use when the user explicitly asks for a Rootloom setup plan, installation, configuration, bootstrap, repair, audit, status, update, reduction, rollback, or removal. Never overwrite user-owned files without showing the plan and obtaining exact replacement authorization.
---

# Set up Rootloom Personal Core

Resolve this Skill directory and use its deterministic setup script.

## Choose a preset

```bash
python3 <skill-dir>/scripts/setup_rootloom.py list-components
```

| Preset | Result |
| --- | --- |
| `skills-only` | Plugin Skills only; the project-guidance Hook is disabled |
| `guidance` | Global working agreement plus read-only project-context Hook |
| `personal` | Guidance plus optional Autonomy; recommended and default |

Exact capabilities are `global-policy`, `project-context`, and `autonomy`.
`autonomy` always includes `global-policy` because the Rules intentionally defer authorization mode and scope to that guidance. Legacy `engineering` and `command-safety` inputs remain compatibility aliases but are not recommended names.

## Optional global layer

`codex plugin add rootloom@rootloom` completes the plugin installation. It exposes Rootloom Skills without writing global guidance, command Rules, setup state, or review gates. Stop there for the lowest-cost experience.

Only when the user explicitly wants cross-project guidance, the project-guidance Hook, or command Rules, inspect and install an optional preset:

```bash
python3 <skill-dir>/scripts/setup_rootloom.py plan --preset personal
python3 <skill-dir>/scripts/setup_rootloom.py install --preset personal
python3 <skill-dir>/scripts/setup_rootloom.py status
```

`apply` remains a compatibility/expert command. Prefer `install` for the first setup and `upgrade` after the Codex plugin snapshot has been refreshed.

The personal preset manages only:

- `~/.codex/AGENTS.md`;
- `~/.codex/rules/rootloom.rules`;
- `~/.codex/.rootloom/components.json`;
- `~/.codex/.rootloom/state.json`, a pending transaction journal, and a simple backup manifest.

Setup is serialized by an ordinary local lock, refuses symlinked or user-owned targets, stages the complete target set before publishing a transaction journal, resumes interrupted staged work before the next mutating setup or rollback operation, writes each file atomically, and preserves original content and mode for rollback. Recovery refuses a target changed after interruption and does not claim hostile shared-filesystem locking.

`AGENTS.md` is a managed-block target: setup inserts or replaces only the content between
the Rootloom markers and preserves everything outside them. Existing unmarked guidance is
kept after the inserted block. Malformed or duplicated markers stop setup and are never
replaced through `--replace-conflicts`.

If another target's plan contains `conflict`, show the exact paths. Use
`--replace-conflicts` only after the user authorizes those replacements. A backup does not
replace authorization.

## Verify optional Autonomy

When `autonomy` is selected, run `codex execpolicy check` for at least:

- routine and high-risk commands represented in the Rules → allow, because static argv Rules cannot carry authorization-mode state;
- catastrophic recursive deletion of root, home, the current directory, or its parent → forbidden.

The global working agreement owns authorization. Standard covers non-high-risk steps of
explicit goals across tasks; Single action covers the exact displayed action once; Full
is limited to the current task and scope and is never inferred. Request only missing
specific approval after preparing the action. Rules avoid duplicating that semantic
decision and do not grant authority. Other active Rules and platform policy remain binding.

Start a new Codex task after setup or plugin update so assets and Hooks are rediscovered.

## Upgrade

Refresh and reinstall the plugin with Codex, then start a new task. That completes the normal plugin upgrade and does not run analyzers, contracts, finalizers, or setup validation:

```bash
codex plugin marketplace upgrade rootloom
codex plugin add rootloom@rootloom
```

If the user previously installed the optional global layer and wants its copied assets refreshed, run one explicit command:

```bash
python3 <skill-dir>/scripts/setup_rootloom.py upgrade
```

Upgrade preserves the installed capability selection. It reports `up_to_date` for the same version, records a version-only upgrade without a redundant asset backup, and backs up changed managed assets before replacement. A pristine target retired by the new catalog is backed up and removed, so rollback restores it; a drifted retired target is refused. All installed target paths are revalidated before access. `AGENTS.md` drift is scoped to its Rootloom-managed block; user-owned content outside the block is preserved and does not block upgrade. If any other managed target or the managed block drifted after setup, both `status` and `upgrade` expose/refuse it; restore the installed content or roll back instead of overwriting the edit. `--replace-conflicts` applies only to newly introduced user-owned whole-file targets after exact authorization, not post-install drift.

## Roll back or change preset

```bash
python3 <skill-dir>/scripts/setup_rootloom.py rollback
```

Rollback first validates that managed files still match the installed hashes. It refuses to overwrite post-setup edits, then restores the backed-up content and mode or removes files created by setup. A normal rollback returns to the previous simple backup; `rollback --all` follows the available backup chain to the pre-install state.

To change presets, roll back, plan the new selection, and apply it. Archived Assurance Edition 1.2.19 uses a different branch and installation contract; roll it back with that version before installing Personal Core.
