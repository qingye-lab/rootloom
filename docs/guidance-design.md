# Guidance design

The system uses a small instruction hierarchy instead of one giant prompt. The exact installable global result is [`plugins/rootloom/assets/system/AGENTS.md`](../plugins/rootloom/assets/system/AGENTS.md); a polished project example is [`examples/AGENTS.project.md`](../examples/AGENTS.project.md).

## What comes from OpenAI's current guidance

OpenAI's [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model) recommends lean prompts, stating each rule once, defining autonomy and approval boundaries, and keeping domain context, hard constraints, and success criteria explicit. Codex's [AGENTS.md documentation](https://developers.openai.com/codex/agent-configuration/agents-md) adds a natural hierarchy: one global file, then root-to-current-directory project guidance, with closer files taking precedence.

That leads to four design rules:

1. Put stable personal operating policy in global `AGENTS.md`.
2. Put repository facts and commands in project `AGENTS.md`.
3. Put reusable multi-step procedures in Skills rather than repeating them in every task.
4. Keep executable policy and proof in Rules, sandboxing, scripts, tests, and CI.

The default 32 KiB project-instruction budget is a ceiling, not a target. This project's managed global template targets 3–4 KiB and 30–45 lines; generated project context is intentionally smaller.

## What we retain from GEB

The [GEB system](https://chunxiang.space/geb-system) contains two valuable ideas:

GEB is an individual article/course site, not an OpenAI specification or peer-reviewed standard. It is design inspiration only; official platform documentation and observed repository behavior govern Rootloom's Codex contracts.

- documentation should stay locally aligned with the code and contracts it describes;
- global, module, and local context should form a hierarchy rather than a flat encyclopedia.

This project translates those ideas into Codex-native layers:

| GEB idea | Rootloom form |
| --- | --- |
| Project constitution | Root `AGENTS.md` with only repository-wide durable invariants |
| Local module map | Nested `AGENTS.md` only at genuine module boundaries |
| Code/document feedback loop | Update guidance when commands, contracts, ownership, or architecture change |
| Cold-start context | Deterministic read-only `SessionStart` scanner |

## What we reject from GEB

The system does not copy the GEB prompt wholesale. It deliberately rejects:

- identity role-play and mandatory forms of address;
- instructions about hidden reasoning language or internal thought structure;
- universal file-length rules unrelated to repository evidence;
- one-line inventories of every file;
- mandatory L3 header comments in every source file;
- blocking all work until documentation has been expanded;
- claims that prose and code can be perfectly isomorphic.

Those patterns create prompt weight, stale duplication, noisy diffs, and false confidence. Source, schemas, tests, manifests, and CI remain the executable truth; `AGENTS.md` points to them and records only decisions an agent would otherwise miss.

## The refined global result

The global working agreement keeps only six compact concerns:

- root-cause repair at the owning boundary;
- preservation of unrelated work;
- three proportional risk tiers;
- proportional evidence and honest completion claims;
- deep review as an explicit exception, not the routine path;
- minimal Single action, Standard, and Full authorization semantics.

It intentionally contains no repository commands, framework preferences, project architecture, personality prose, or duplicated tool manuals.

## The refined project result

Outside Plan sessions, the SessionStart Hook may inject at most 4 KiB of regenerated incremental facts without writing the repository:

- project identity and primary manifest;
- whether project guidance already exists;
- up to three detected verification commands only when project guidance is absent.

The temporary renderer deliberately omits the full source-of-truth inventory, top-level map, module candidates, and generic verification contract. The complete persistent renderer remains available only through explicit seeding.

Only an explicit `$project-guidance` request persists a managed block. Active guidance
may request read-only validation automatically; one file may request one semantic
refinement with the exact standalone `<!-- rootloom:refine-once version=1 -->` marker,
which is consumed by the successful write. Natural-language guidance alone never
authorizes persistence. The user-owned section may contain only durable,
evidence-cited invariants such as ownership direction, generated-code boundaries,
public or persisted contracts, and canonical architecture or migration documents. The
separately installed `rootloom-memory` plugin may complement guidance with reviewable
risks and failure lessons; it never replaces `AGENTS.md` authority or current repository
evidence.

Guidance completion compares the final worktree with the starting state and authorized
paths. Verification uses no-cache options where practical and must not leave cache,
coverage, build, or other generated output; only artifacts created by the current task
may be removed.

Nested guidance is created lazily. A folder deserves its own `AGENTS.md` only when it has a distinct manifest, commands, ownership, contracts, or operational rules. Ordinary directories and individual files do not.

## Maintenance test

Keep a guidance sentence only if it changes a future implementation, review, verification, or safety decision; remains useful across ordinary code changes; is supported by a real path; belongs at that scope; and is not already stated by a stronger source of truth.

When any answer is no, delete the sentence or leave it in the source document that already owns it.
