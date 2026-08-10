# Setup, update, and rollback

Installing the plugin exposes the four Core Skills and the reviewed `SessionStart` Hook
definition. It does not install global policy, enable the Hook, run Evidence resources,
or install Rootloom Memory. Applying global Core assets is a separate optional operation.

This document covers the native Codex package at `plugins/rootloom/`. The separate Agent
Plugins package at `portable/rootloom/` contains Change, Review, and Project Guidance
and has no Setup or Hook configuration; see [Agent Plugins portable preview](agent-plugins.md).
Optional consumer-repository SessionStart templates live separately under
`adapters/rootloom/`; they do not install or manage host permissions. Installing or
removing that package uses the target client's own lifecycle and never manages
`~/.codex`.

## Install

```bash
codex plugin marketplace add liyanqing90/rootloom
codex plugin add rootloom@rootloom
```

Start a new task and inspect `/hooks`. The only Hook detects repository facts and injects temporary read-only project context. It does nothing until exact managed component policy version 1 enables it, and it never writes `AGENTS.md`.

The plugin is fully usable at this point. No setup command, analyzer, baseline,
contract, finalizer, or Memory plugin is required.

An explicit natural-language request to plan, install, inspect, update, or roll back
Rootloom may route to Setup; `$setup-rootloom` is the deterministic explicit form.
Activation does not authorize overwriting a user-owned conflict.

Install experimental Memory separately only when wanted:

```bash
codex plugin add rootloom-memory@rootloom
```

## Presets

| Preset | Capabilities |
| --- | --- |
| `skills-only` | Skills only; Hook disabled |
| `guidance` | `global-policy`, `project-context` |
| `personal` | Guidance plus `autonomy`; default |

The empty capability selection used by `skills-only` is persisted as an intentional installed state. `status`, `plan`, and compatibility `apply` without a new explicit selection preserve it.

Only when the user explicitly wants a cross-project global layer, inspect and install:

```bash
python3 <setup-skill>/scripts/setup_rootloom.py list-components
python3 <setup-skill>/scripts/setup_rootloom.py plan --preset personal
python3 <setup-skill>/scripts/setup_rootloom.py install --preset personal
python3 <setup-skill>/scripts/setup_rootloom.py status
```

`install` refuses an already installed setup. `apply` remains available for compatibility and expert use, but explicit `install`/`upgrade` makes lifecycle and rollback intent visible.

Exact capability selection is also available:

```bash
python3 <setup-skill>/scripts/setup_rootloom.py plan \
  --capabilities global-policy,project-context,autonomy
```

Selecting `autonomy` always includes `global-policy`; Rules that suppress duplicate prompts must not be installed without the guidance that owns Standard, Single action, and Full authorization. Legacy `engineering` and `command-safety` input remains accepted only for compatibility.

## Managed targets

| Path | Purpose |
| --- | --- |
| `~/.codex/AGENTS.md` | Rootloom-managed block in the personal engineering working agreement; content outside the markers stays user-owned |
| `~/.codex/rules/rootloom.rules` | Optional low-confirmation authorization policy |
| `~/.codex/.rootloom/components.json` | Hook enablement |
| `~/.codex/.rootloom/state.json` | Installed selection and target hashes |
| `~/.codex/.rootloom/transaction.json` | Pending staged setup transaction, removed after recovery |
| `~/.codex/.rootloom/backups/` | Pre-mutation file copies and manifest |

Rootloom does not modify ordinary model, reasoning, sandbox, approval, provider, MCP, plugin, or app configuration.

## Safety contract

Setup:

- shows a plan before the Skill applies it;
- uses an ordinary create-exclusive local lock;
- inserts or replaces only the `rootloom:managed-start` / `rootloom:managed-end` block in `AGENTS.md`, preserving existing content outside that block;
- refuses symlinked targets, malformed `AGENTS.md` managed markers, and unmarked user-owned conflicts on whole-file targets;
- requires exact authorization before `--replace-conflicts`;
- copies every replaced file before the first managed target write;
- stages the complete target set and final setup state before publishing a transaction journal;
- writes each target atomically;
- resumes a pending staged transaction under the setup lock before the next mutating setup or rollback operation;
- records the `AGENTS.md` managed-block hash and whole-file hashes for other targets so user-owned guidance does not become setup drift;
- refuses upgrade when a managed target no longer matches its installed hash, even when `--replace-conflicts` is present;
- restores original content and POSIX mode during rollback.

If the process stops between file replacements, `status` reports the pending transaction without writing; the next mutating setup or rollback operation resumes the exact staged target set and final state. Recovery refuses to overwrite a target changed after the interruption and leaves the journal for explicit reconciliation. The contract still does not defend against a hostile same-user process replacing lock or target paths concurrently.

## Optional Autonomy Rules check

```bash
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- git commit -m test
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- git push origin main
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- gh pr merge 123 --merge
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- gh release create v1.0.0
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- npm publish
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- kubectl apply -f deployment.yaml
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- git push --force-with-lease origin main
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- gh release delete v1.0.0
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- terraform destroy
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- git reset --hard
codex execpolicy check --pretty --rules ~/.codex/rules/rootloom.rules -- rm -rf /
```

Expected decisions are ten `allow`, followed by `forbidden`. The installed global guidance—not argv Rules—owns authorization state: Single action applies once, Standard persists across tasks for all non-high-risk steps of each explicit goal, and Full covers high-risk steps only in the current task and scope. The Rules avoid a second prompt after that semantic decision and retain only the catastrophic recursive-deletion hard deny. A more restrictive active Rule or platform policy can still prompt.
If the host still classifies an exact authorized action as approval-requiring while the
active task or organization profile forbids asking (for example
`AskForApproval=Never`), treat that controlling profile as the blocker; repeating the
same user confirmation cannot override it.

## Change preset or roll back

Changing capability selection requires rollback first:

```bash
python3 <setup-skill>/scripts/setup_rootloom.py rollback
python3 <setup-skill>/scripts/setup_rootloom.py plan --preset guidance
python3 <setup-skill>/scripts/setup_rootloom.py install --preset guidance
```

Rollback preflights every managed file. If a target changed after setup, it stops rather than overwriting the edit. A normal rollback returns to the previous simple backup; `rollback --all` follows that backup chain to the pre-install state.

To remove plugin Skills after global rollback:

```bash
codex plugin remove rootloom@rootloom
```

## Update

```bash
codex plugin marketplace upgrade rootloom
codex plugin add rootloom@rootloom
```

Codex owns the marketplace snapshot and plugin package update. Start a new task so the refreshed Skills are loaded. The normal upgrade is complete and does not trigger any Rootloom review gate.

If an optional global preset was previously installed and its copied assets should also be refreshed, run one explicit command:

```bash
python3 <setup-skill>/scripts/setup_rootloom.py upgrade
```

Optional setup `upgrade` always preserves the installed capability selection. It reports `up_to_date` when the current plugin and assets already match. If only the plugin version changed, it updates setup state without creating a redundant asset backup; if managed content changed, it creates the normal backup before writing. A managed target retired by the new catalog is removed only when it still matches its installed hash, and it is backed up so rollback restores it. Installed state paths are normalized and checked before access. `status` reports `installed_version`, `upgrade_available`, and `drifted_paths`. Drift is never overwritten by upgrade: restore the expected content or roll back first. `--replace-conflicts` is reserved for a newly introduced user-owned target after exact authorization.

For `AGENTS.md`, drift means a change inside Rootloom's marked block. Setup preserves
content before and after that block byte-for-byte during install and upgrade. On first
install into an unmarked file, it inserts the managed block before the existing content.
Malformed or duplicated markers stop the operation and must be repaired explicitly;
setup never falls back to replacing the whole file.

## Migrate from Archived Assurance Edition 1.2.19

The setup contracts are intentionally incompatible. Use the archived 1.2.19 code on `codex/enterprise-assurance` to roll back its setup before installing Personal Core. Do not ask the Personal Core setup to infer or remove custom agents, the high-assurance profile, configuration limits, Human Review state, or recovery journals.
