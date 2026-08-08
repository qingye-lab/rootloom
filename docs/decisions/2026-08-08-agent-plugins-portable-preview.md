# Isolate the Agent Plugins portable preview from the Codex-native package

- Status: accepted
- Date: 2026-08-08
- Owners: Rootloom maintainers
- Scope: plugin packaging, portable Skill surface, Codex coexistence, and compatibility claims
- Supersedes: none
- Superseded by: [Unified cross-host Rootloom capability baseline](2026-08-08-unified-host-capability-baseline.md)

## Context

Rootloom's four-entry Core is packaged for Codex under `plugins/rootloom/` with a
`.codex-plugin/plugin.json`, interface metadata, a gated SessionStart Hook, Project
Guidance, and optional Codex-home Setup. Agent Plugins 1.0.0 defines a vendor-neutral
root `plugin.json` plus fixed `skills/` and optional `mcp.json` locations. Adding that
root manifest to the existing Codex package would change format selection in current
Codex implementations and suppress native Hook loading. Packaging compatibility must
not silently remove an existing capability.

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| Agent Plugins 1.0.0 requires a root manifest and fixed Skill discovery | fact | Agent Plugins Working Draft and canonical schema | 2026-08-08 | [Specification](https://agent-plugins.org/specification) | Public specification |
| Current Codex gives the Agent Plugins format precedence and does not load plugin Hooks in that mode | fact | current OpenAI Codex source | 2026-08-08 | `codex-rs/core-plugins` manifest and loader paths | Public source; no sensitive data |
| Cursor, VS Code, GitHub Copilot, and Kiro document root `plugin.json` Agent Plugins loading | fact | current host documentation and Agent Plugins compatible-client directory | 2026-08-08 | Host plugin or Power documentation | Public documentation |
| Review is self-contained and Change Direct/Scoped/Governed uses in-Skill References | fact | current Rootloom Skill tree | 2026-08-08 | `plugins/rootloom/skills/{operating-code-review,operating-coding-change}` | Repository source |
| Full Evidence, Project Guidance writes, Setup, and SessionStart depend on plugin-wide or Codex-specific resources | fact | current Rootloom source | 2026-08-08 | Evidence resources, Guidance scripts, Setup, and Hook | Repository source |

## Decision

Keep `plugins/rootloom/` as the unchanged Codex-native four-Skill package and keep the
Codex marketplace pointed only at that path. Add a separate, checked-in
`portable/rootloom/` Agent Plugins 1.0.0 preview containing exactly Change and Review.

Use that one package unchanged across Cursor, VS Code, GitHub Copilot, Kiro, and other
conformant hosts. Host install settings stay outside the package. Do not add a
host-specific manifest, generated Skill mirror, or extension directory unless a
required capability is outside Agent Plugins and has its own accepted compatibility,
migration, rollback, and verification contract. Codex remains the intentional native
adapter because its existing Hook, Setup, Guidance, and interface behavior is outside
the portable-v1 core.

The native Skill directories remain the single editable source. A deterministic
standard-library synchronizer copies only `SKILL.md` and non-client-specific bundled
resources into the portable package. Repository validation enforces the portable
manifest schema, path containment, exact allowlist, shared identity/version parity, and
byte equality with the native source.

Portable Change includes Direct, Scoped, Governed reasoning, and proportional
verification. It fails closed when explicit Evidence Mode is requested because the
portable package does not ship plugin-wide Evidence helpers. Review remains fully
self-contained. Project Guidance, Setup, Hooks, Rules, OpenAI UI metadata, Memory, and
MCP are outside the preview.

## Alternatives considered

- Add `plugin.json` beside `.codex-plugin/plugin.json` — rejected because current Codex format precedence would silently suppress the existing Hook.
- Replace the Codex package with Agent Plugins format — rejected because Hooks and Setup are not portable-v1 components and existing users would lose native behavior.
- Copy all four Skills into the preview — rejected because Project Guidance writes and Setup depend on Codex-specific trust, paths, protocols, and configuration.
- Duplicate shared Skills manually — rejected because security and workflow fixes could drift between packages; deterministic synchronization makes the native source authoritative.
- Generate Cursor, VS Code, Copilot, or Kiro package forks — rejected because all four hosts consume the Agent Plugins root format; only their loader configuration differs.
- Include the complete Evidence subsystem — deferred because Agent Plugins standardizes packaging, not the shell/process/runtime capabilities needed to prove equivalent Evidence behavior in every client.

## Consequences

- Positive: Agent Plugins clients can discover a standards-shaped Rootloom Change/Review package without changing native Codex behavior.
- Positive: existing marketplace installs, Hook enablement, optional Setup, and rollback remain unchanged.
- Positive: all conformant non-Codex hosts share one manifest and one generated Skill mirror rather than accumulating platform forks.
- Negative: the portable preview has fewer capabilities than the native package and needs client-specific runtime testing.
- Negative: the repository retains a generated Skill mirror, guarded by exact synchronization checks.
- Operational: users must choose one Rootloom package per client; installation and removal remain client-owned.
- Operational: a documented loader is not a runtime-pass claim; Cursor, VS Code, Copilot, and Kiro still require versioned host smoke evidence.
- Operational: rollback removes only `portable/rootloom/`, synchronization/validation, and portability documentation; the Codex package is untouched.

## Verification

- Repository validation rejects invalid portable schemas, extra files, Codex-only Skills, symlinks, path escapes, identity drift, and stale mirrors.
- Focused unit tests mutate manifest schema, shape, types, and shared identity fields and build an isolated package.
- `make check` proves repository contracts and the full unit suite.
- `make compatibility-smoke` proves the native Codex marketplace, Setup, Rules, and rollback path still pass.
- `make portable-compatibility-smoke` proves Codex can install the isolated package and
  that its installed Skill directory surface contains exactly Change and Review; it
  does not prove runtime activation.
- Runtime smoke in at least one non-OpenAI compatible client remains required before changing the preview into a cross-client feature-parity claim.

## Revisit when

- Codex publishes and tests portable Hook or extension semantics that preserve the current native lifecycle contract.
- Agent Plugins leaves Working Draft or changes its manifest/component contract.
- Client runtime evidence justifies adding Project Guidance, Evidence helpers, or another portable Skill.
- Duplicate-Skill precedence becomes standardized strongly enough to support safe native/portable coexistence in one client.
