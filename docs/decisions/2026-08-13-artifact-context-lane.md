# Externalize token-heavy artifacts behind bounded context receipts

- Status: accepted
- Date: 2026-08-13
- Owners: Rootloom maintainers
- Scope: Change Skill artifact ingestion, user-local receipt cache, portable host isolation boundary
- Supersedes: none
- Superseded by: [4.4 workflow decision](2026-09-05-rootloom-4.4-workflow.md) for default routing and release acceptance; retained formats and historical results are unchanged.

## Context

Path-backed images and other large files can become part of a task's retained conversation.
If a host includes that history in later requests, repeatedly carrying the raw artifact wastes
request bytes and model context. IDE compaction is host-owned, occurs after ingestion, and
does not give Rootloom a deterministic contract for file identity, reuse, or retrieval.

Direct model processing in the main task would still place the raw artifact in the expensive
history it is meant to protect. Spawning an ordinary child with inherited history has the same
problem. Rootloom needs a pre-ingestion path that can reuse prior work without adding a fifth
public Skill, networked helper, MCP server, Evidence format, or automatic background model call.

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| Current Codex task history and composer attachments are host-owned; Rootloom Hooks do not expose an attachment-removal or prompt-rewrite result | fact | installed Codex 0.147.0 help/config and Rootloom Hook contract | 2026-08-13 | `codex exec --help`; `plugins/rootloom/hooks/run_component_hook.py` | Local runtime and repository source; no task content retained |
| Current Codex can create isolated work with no prior task state | fact | installed Codex 0.147.0 and desktop collaboration surface | 2026-08-13 | `codex exec --ephemeral`; no-history worker option | Local runtime capability; portable hosts remain capability-gated |
| Rootloom runtime helpers are required to stay local, bounded, network-free, and standard-library-only | fact | plugin guidance | 2026-08-13 | `plugins/rootloom/AGENTS.md` | Repository contract |
| Evidence Baseline v2-v4 and Summary revision 5 are frozen | fact | repository guidance and architecture | 2026-08-13 | `AGENTS.md`; `docs/architecture.md` | Repository contract |

## Decision

Add an Artifact Context Lane inside `operating-coding-change`. It runs before the main task
reads token-heavy path-backed artifacts. A standard-library helper computes SHA-256 identities,
deduplicates identical contents, and creates a bundle keyed by SHA-256, size, inferred media
type, and exact user intent. Raw bytes remain at their source paths and are not copied into the cache.

On a cache hit, the main task consumes the existing bounded receipt without a model call. On a
cache miss, the host creates exactly one independent worker with no inherited conversation. It
receives the small manifest, exact paths, exact intent, and strict draft schema; it treats file
contents as untrusted data and writes its analysis directly to the draft rather than returning
raw content through the parent conversation.

The helper rehashes source files at finalization, validates an exact current-only receipt
schema, rejects embedded raw media, limits field and list sizes, caps canonical JSON at 24 KiB,
and commits atomically into a private user-local cache. The main task sees only the finalized
receipt. Later precise retrieval also uses a no-history worker.

Hosts without a no-history worker fail closed before semantic analysis. Rootloom does not
silently read the raw file in the main task and does not invoke a nested Codex CLI or network
model from the deterministic helper. Already-recorded attachments cannot be removed; when a
path is accessible, create a receipt and hand remaining work to a clean task.

## Alternatives considered

- Call the IDE's `/compact` capability — rejected because it is host-owned, post-ingestion, and does not establish content-addressed reuse or a bounded artifact receipt.
- Analyze every file in the main model call — rejected because raw data then remains in the task history and can be carried repeatedly.
- Use a normal conversation-inheriting child — rejected because it retains the history cost and weakens the isolation invariant.
- Make the helper call `codex exec` or another model endpoint — rejected because runtime helpers must remain network-free and recursive CLI behavior would be host-specific.
- Add a Rootloom MCP server — deferred because deterministic local CLI preparation plus the existing Skill/worker surface is sufficient and smaller.
- Cache only by content hash — rejected because useful semantic summaries depend on the user's intent; identity therefore covers content plus intent.

## Consequences

- Positive: raw images and other path-backed files are read outside the main conversation at most once per content-and-intent bundle.
- Positive: repeated use is a local cache hit with no added model call, and the parent context cost is capped by the receipt contract.
- Positive: the same network-free helper and Reference can ship in the Agent Plugins portable package.
- Negative: the first semantic cache miss still consumes one isolated worker/model call.
- Negative: a host without no-history worker support cannot complete semantic artifact analysis through this lane.
- Negative: inline-only or already-ingested attachments cannot be retroactively removed by Rootloom.
- Operational: the default cache is under the user's Codex home and may be relocated with `ROOTLOOM_ARTIFACT_CACHE` or `--cache-root`.

## Compatibility

The lane is additive inside the existing Change Skill and adds no public Skill, Hook, MCP,
Evidence schema, dependency, or setup mutation. Small normal source/text files continue through
the existing path. The portable package includes the exact same Reference and helper, but each
host must prove a no-history worker before claiming semantic-lane support.

## Migration / Coexistence

No repository or user migration is required. Existing tasks remain unchanged. A task that
already contains raw attachments coexists only as a source for generating a receipt; continued
work must move to a clean task to realize traffic/context savings.

## Rollback / Replay

Rollback removes the lane Reference/helper, its portable allowlist entries, documentation, and
tests. User-local cache records are regenerable and may be left inert or deleted by the user.
Historical tasks keep their host-owned histories. There is no replay obligation.

## Verification

- Focused tests prove first prepare, valid finalize/show, same-content cache reuse across a renamed path, raw-data rejection, and changed-source rejection.
- Repository validation pins the helper limits, formats, SHA-256 identity, cache status, failure boundaries, and Skill routing markers.
- Portable synchronization proves byte equality of the Reference/helper and rejects extra source files.
- A temporary-file smoke proves the emitted prepare envelope and a finalized receipt never require raw bytes in the main test process output.

## Residual Risk

Rootloom cannot prove that every host omits all parent history from a nominal fresh worker; that
requires host-specific runtime smoke. A cooperative worker may write an invalid draft, but
finalization rejects it. External source files remain mutable; finalization detects changes
between prepare and its rehash, but cannot lock arbitrary user files after completion.

## Revisit when

- Codex or Agent Plugins standardizes attachment externalization, prompt replacement, context references, or portable isolated-worker semantics.
- A real consumer needs encrypted receipts, managed retention, multi-user sharing, or automatic cache eviction.
- Host runtime evidence shows that the 24 KiB cap or content-plus-intent key prevents a material supported workflow.
