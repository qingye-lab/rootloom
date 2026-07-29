# Troubleshooting

## The project-guidance Hook does nothing

Check that the personal or guidance preset is installed and that `~/.codex/.rootloom/components.json` contains exact integer `version: 1` plus managed boolean `project-guidance-hook: true`. Missing, malformed, wrong-type, unsupported-version, or symlinked policy disables the Hook. The Hook only injects temporary context and never writes `AGENTS.md`; use `$project-guidance` explicitly when persistence is intended. Start a new Codex task after plugin or setup changes and review `/hooks` again.

The scanner also skips untrusted repositories unless the platform marks them trusted. `ROOTLOOM_ALLOW_UNTRUSTED=1` is intended only for controlled tests.

## Setup reports a conflict

Run `plan` and inspect every affected path. Unmarked content is user-owned. Use `--replace-conflicts` only after exact authorization; Rootloom will create a backup first.

Symlinked targets are always refused. Move or resolve the symlink explicitly rather than asking setup to follow it.

## Setup stopped partway through

Rootloom Core has per-file atomic writes and pre-mutation backups, not a recovery journal. Run:

```bash
python3 <setup-skill>/scripts/setup_rootloom.py status
```

Inspect the newest `~/.codex/.rootloom/backups/*/manifest.json`, compare target hashes, and restore only the affected paths. Do not re-run with conflict replacement until the partial state is understood.

## Rollback refuses a changed file

Rollback protects post-setup edits. Preserve or merge the current file manually, restore it to the recorded managed version, then run rollback again. Do not delete the state or backup merely to bypass the check.

## Commands still prompt unexpectedly

Use `codex execpolicy check` against every active Rules file. The most restrictive matching decision wins, so a broader `git` prompt may override Rootloom's local `git commit` allow. Rules inspect argv prefixes; nested shell commands need their own policy and approval boundary.

## Verification helper rejects a command

`finalize_change.py` parses commands with platform-aware `shlex` rules and does not run a shell. Windows parsing preserves backslash paths and removes matching outer quotes from arguments; quote an executable path when it contains spaces. Pipelines, redirects, `&&`, environment assignment, or command substitution are not interpreted. Put complex verification in a reviewed repository-owned script or Make target and invoke that executable directly.

Exit 124 is timeout. Exit 125 means the bounded output budget was exceeded. Exit 126 means the executable could not start. Increase budgets only when the larger evidence is necessary and safe to retain.

The output directory must be outside the captured repository. A tracked patch larger than the default 16 MiB ceiling is refused; raise `--max-patch-bytes` only after checking why the review bundle is that large. The verification log budget is aggregate across at most 20 commands.

## The risk scanner looks too strict or too lenient

Inspect `signals`, `changed_paths`, and `confidence` in `analyze_change.py` output.
Pass anticipated `--path` values before editing so documentation/tests can be
distinguished from product code. The reported Tier is a minimum advisory floor: current
semantic evidence may raise it, but neither `--declared-risk` nor finalizer `--risk`
can lower it. If a false positive is repeatable, add a focused analyzer regression
rather than hiding the signal.

## The verification plan says suggested-not-executed

That is intentional. `required_behaviors` describes what should be proven and `suggested_commands` contains detected repository commands, but only commands explicitly supplied with `--verify` appear under `tests` and affect `passed`. Review suggestions before execution.

## Sensitive deletion returns exit 10

The helper detected an exact `.env`, secret, migration, or database path deletion. Obtain confirmation for that exact path and repeat it with `--confirm-dangerous-delete`. This is a lightweight guard, not an approval ledger.

## Project memory is stale or malformed

Install `rootloom-memory` separately; Core does not read `.project-memory/`. Repository
evidence wins. Its `context` command excludes expired, resolved, and superseded matches
by default and lists them under `stale`; use `--include-stale` only for historical
investigation. Use explicit `set-status` lifecycle changes instead of deleting lessons.
The helper refuses unknown formats, oversized collections, unsafe paths, symlinks, or
invalid entries and never silently migrates ambiguous content.

## I need the old Human Review or strict Runner

Those features are not hidden flags in Rootloom Core. Use `codex/enterprise-assurance`,
which preserves Rootloom 1.2.19. Roll back one product's setup with its own version
before installing the other.
