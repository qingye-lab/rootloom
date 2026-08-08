---
name: project-guidance
description: Seed, refresh, refine, or validate concise evidence-backed AGENTS.md guidance. Deterministic scripts own the managed block; model judgment may add only durable repository-specific invariants outside it.
---

# Project guidance

Use when the user explicitly asks to persist, refresh, refine, or validate project
guidance, or when active repository guidance requests validation. The SessionStart Hook
is read-only and never invokes a writer.

Persistent seed, refresh, or refinement requires explicit user intent. The only
repository-authored exception is this exact standalone one-time marker in active
guidance:

```text
<!-- rootloom:refine-once version=1 -->
```

It authorizes one refinement of that marked file only. Remove it in the same successful
write; validation does not consume it. Natural-language guidance alone never authorizes
persistent refinement or any other write.

## Route the mode

```text
explicit seed request                  → seed
explicit refresh request               → refresh
explicit refinement or exact marker    → refine
user/repository validation request     → validate
```

Resolve this Skill directory and probe first:

```bash
python3 <skill-dir>/scripts/seed_project_guidance.py probe --cwd "$PWD"
```

## Seed or refresh

Run the deterministic writer:

```bash
python3 <skill-dir>/scripts/seed_project_guidance.py seed --cwd "$PWD"
```

Run that command without a trust override first. If and only if it returns the exact
`untrusted_project` skip reason and the user explicitly requested persistence in this
exact repository, retry once with `--allow-untrusted`. The flag is scoped to that
invocation and does not change Codex or host trust settings. Never infer this override
from a general request to inspect, review, or change code.

It derives observable facts from manifests, lockfiles, package scripts, Make/Just
targets, canonical docs, CI, and bounded module discovery. It locks through the Git
common directory, checks concurrent edits, writes atomically, and owns only its marked
managed block.

Never overwrite an unmarked existing `AGENTS.md`, `AGENTS.override.md`, symlinked
guidance, untrusted or disabled projects, temporary paths, vendor/cache trees, or
evidence resolved outside the repository. Respect every script skip reason.

Either `.rootloom/disable-project-guidance` or the legacy
`.codex/disable-project-guidance-seeding` sentinel disables both temporary session
context and persistent seeding.

## Refine

Read [references/semantic-refinement.md](references/semantic-refinement.md). Keep model
judgment outside managed markers. Add only evidence-backed statements that change a
future implementation, review, verification, or safety decision.

## Nested guidance

Use `module_candidates` from the probe only when current work enters a genuine module
with its own manifest and materially different commands, ownership, contracts, or
invariants:

```bash
python3 <skill-dir>/scripts/seed_project_guidance.py seed \
  --cwd "$PWD" \
  --target path/to/module
```

Create at most three nested files per pass and do not go deeper than three directories
from the Git root. Never mirror the directory tree.

## Validate

Run this for every created, refreshed, or inspected managed file:

```bash
python3 <skill-dir>/scripts/seed_project_guidance.py validate \
  --file path/to/AGENTS.md
```

Inspect the effective root-to-current-directory chain for contradictions, duplication,
stale paths, broken commands, oversized context, placeholders, secrets, and rules that
cannot be verified. Continue the user's original task after guidance work.

Before completion, compare the final worktree with the starting state and authorized
paths. Verification must not leave caches, coverage, build output, or other generated
artifacts. Prefer no-cache options; otherwise remove only artifacts created by this
task, never pre-existing user work.
