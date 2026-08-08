# Unify the Rootloom capability baseline across agent hosts

- Status: accepted
- Date: 2026-08-08
- Owners: Rootloom maintainers
- Scope: portable Skills, read-only session context, and consumer-repository host adapters
- Supersedes: [Agent Plugins portable preview isolation](2026-08-08-agent-plugins-portable-preview.md)
- Superseded by: none

## Context

The isolated Agent Plugins preview originally exposed only Change and Review. That
preserved Codex-native lifecycle behavior but left Project Guidance outside the common
capability baseline. Agent Plugins 1.0.0 standardizes Skills and MCP, not host lifecycle
events. Cursor, VS Code/GitHub Copilot, Kiro, and Codex provide different SessionStart
events and output envelopes, so copying the workflow into host forks would create
semantic drift.

## Evidence

- The native `project-guidance` Skill already owns a deterministic, network-free,
  read-only 4 KiB session renderer and persistent seeding that requires explicit intent.
- Cursor uses `sessionStart` and `additional_context`; VS Code accepts Copilot lowerCamel
  hook configuration and returns nested `hookSpecificOutput`; Copilot uses camel input
  and `additionalContext`; Kiro `SessionStart` adds plain stdout to context.
- Agent Plugins client extensions are host-defined. No documented common Hook namespace
  spans these hosts, so placing invented host directories inside `portable/rootloom/`
  would not be a standards contract.

## Decision

Expose exactly three standard Skills in `portable/rootloom/`: Change, Review, and
Project Guidance. Native Skill directories remain authoritative. Deterministic
synchronization excludes `agents/` metadata and caches, and vendors
`rootloom_lock.py` beside the Project Guidance helper so the portable Skill is
self-contained.

Keep `portable/rootloom/` Agent Plugins v1 standard-only. Put opt-in, non-installing
consumer-repository templates under `adapters/rootloom/`. Cursor, the shared VS
Code/Copilot configuration, and Kiro each vendor byte-identical canonical runtime
files and vary only by event/config/output envelope. A machine-readable capability
contract records the shared three-Skill baseline, read-only 4 KiB context, host mapping,
pending non-Codex runtime status, and non-unified surfaces.

Adapters always invoke the read-only hook path with an explicit per-invocation trust
override. Persistent seed/refresh still requires an exact user request: the Skill runs
without override first and may retry with `--allow-untrusted` only after the exact
`untrusted_project` result for that repository. Both
`.rootloom/disable-project-guidance` and the legacy Codex sentinel disable context and
seeding.

Setup remains Codex-native. Portable Evidence runtime remains unavailable and fails
closed. Host permission enforcement remains host-owned. No adapter adds PreToolUse, Stop,
Rules, permissions, MCP, automatic installation, or repository writes.

## Alternatives considered

- Duplicate Project Guidance per IDE — rejected because behavior and safety fixes would drift.
- Put Hook directories in the Agent Plugins root — rejected because v1 does not define a cross-host Hook component.
- Use only host instructions or Steering — rejected because they do not provide the same deterministic bounded session renderer.
- Add permission gates now — rejected because permission semantics are host-owned and outside the common baseline.

## Compatibility, migration, and rollback

The Codex-native manifest, four-Skill discovery, Setup, Rules, Hook enablement, Evidence
formats, marketplace path, and Memory remain unchanged. The portable package expands
additively from two to three Skills before formal release; no version is bumped in this
unreleased change. Existing portable users refresh the same package root. Adapters are
copied only by explicit consumer action after conflict inspection.

Rollback removes the exact adapter files and regenerates the portable package without
Project Guidance; it does not alter native Codex state or earlier repository guidance.
There is no irreversible operation.

## Verification

Repository checks enforce exact manifests, events, timeouts, commands, source-byte
equality, path containment, no symlinks or unexpected files, bounded/malformed stdin,
Plan and disable skips, trust behavior, path-with-spaces execution, missing-interpreter
non-destruction, the shared Hook configuration's required integer version 1, stderr-only
non-Codex diagnostics, and identical synthetic context across envelopes. The isolated Codex
package smoke expects exactly three Skills and the self-contained helper.

These are static and synthetic checks. Live runtime smokes for Cursor, VS Code, GitHub
Copilot, and Kiro remain pending; this decision does not claim live runtime parity.

## Revisit when

- Agent Plugins standardizes portable lifecycle events or a common Hook namespace.
- A host changes its event, input, output, timeout, or repository Hook contract.
- Versioned live-host smoke evidence supports promoting a runtime claim.
