# Migrate from Rootloom 3.x to 4.0

Rootloom 4 intentionally contracts the public Skill API. Existing Baseline v2–v4,
Summary revision 5, change-contract, manifest, and seal artifacts remain readable.

## Skill mapping

| Rootloom 3.x | Rootloom 4.0 |
| --- | --- |
| `$operating-coding-change` | `$operating-coding-change` |
| `$operating-high-risk-change` | `$operating-coding-change` in Governed mode |
| `$engineering-change` | `$operating-coding-change` with explicit Evidence Mode |
| `$seed-project-guidance` | `$project-guidance` in Seed or Refresh mode |
| `$refine-project-guidance` | `$project-guidance` in Refine mode |
| `$record-engineering-decision` | Governed Change durable-decision step |
| `$project-memory` from Core | `$project-memory` from separately installed `rootloom-memory` |
| `$setup-rootloom` | `$setup-rootloom` |

Removed Skill directories are not retained as aliases because alias Skills would remain
discoverable and defeat the four-entry contract. Update saved prompts, team docs, and
automation to the new names before upgrading.

## Evidence CLI paths

Evidence helpers moved without changing their frozen wire formats:

```text
plugins/rootloom/skills/engineering-change/scripts/
→
plugins/rootloom/resources/evidence/
```

Update absolute or repository-relative automation paths. The 4.0 analyzer/finalizer no
longer accept `--include-project-memory`. Query the optional Memory Skill separately,
verify its leads against current evidence, and pass only relevant conclusions through
the task or change contract.

## Project Memory

Install Memory separately when needed:

```bash
codex plugin add rootloom-memory@rootloom
```

Existing repository `.project-memory/` files keep the
`rootloom-project-memory-v1` format and do not require migration. Removing Rootloom
Memory does not delete those files.

## Upgrade

```bash
codex plugin marketplace upgrade rootloom
codex plugin add rootloom@rootloom
```

Start a new Codex task so the new Skill catalog is discovered. If Rootloom's optional
global setup is installed, run `$setup-rootloom` in upgrade mode afterward; setup state
and rollback remain independent from the public Skill contraction.

## Rollback

Before the 4.0 release is installed, preserve any updated prompt or automation path
changes in version control. To return to 3.4, install the immutable `v3.4.0` marketplace
snapshot and restore old Skill/CLI names. Evidence artifacts do not need conversion.

Formal 4.0 publication remains gated on the comparative matrix in
`evals/core-reset/`; structural context reduction alone is not behavioral proof.
