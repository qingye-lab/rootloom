# Default to impact-scoped verification

- Status: accepted
- Date: 2026-08-10
- Owners: Rootloom maintainers
- Scope: installable verification guidance and Rootloom repository CI
- Supersedes: none
- Superseded by: none

## Context

Rootloom said that checks should be proportional, but it did not define when broader
regression was justified. The repository then repeated the complete unit suite across
four Linux Python versions and again on macOS and Windows. Models could also interpret
rollback, broad risk awareness, or the existence of a test command as a reason to run
every check, even when a change had a bounded owner and consumers.

The correction must reduce repeated work without allowing an unknown executable change
to pass silently. It must remain understandable from repository source and must not add
a dependency graph service, historical test database, or another persisted format.

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| The prior CI definition ran complete unit discovery in four Linux jobs and again on macOS and Windows | repository fact | Rootloom `main` before this decision | 2026-08-10 | Git revision `958d6fa2`, `.github/workflows/ci.yml` | Repository history; no private data |
| Rootloom tests already align with seven bounded component owners | repository fact | current test modules and Make targets | 2026-08-10 | `tests/test_*.py`; `Makefile` | Current source |
| Existing global guidance required proportional evidence but did not define a full-suite stop condition | repository fact | released Rootloom 4.2.2 | 2026-08-10 | `plugins/rootloom/assets/system/AGENTS.md`; Change verification Reference | Released source |

## Decision

Impact-scoped verification is the default in both Rootloom governance and this
repository:

1. Select checks from the changed owner, known consumers, and one adjacent behavior
   path. Each platform or runtime lane must prove a distinct risk.
2. `scripts/impact_tests.py` owns a static, reviewable path-to-component map. Known
   documentation-only changes run structural validation without unit tests. Unknown
   executable paths and changes to the selector, validator, Makefile, or CI workflow
   fail closed to the full suite.
3. Pull requests run selected tests. `main` runs one canonical full suite on Python
   3.11. Python 3.14 and macOS/Windows select named compatibility cases from
   `COMPATIBILITY_TESTS`, filtered by component; each entry states its runtime or OS risk.
   Primary retains all affected assertions. Unknown/shared changes select the full primary
   suite and all named compatibility cases. Repository validation rejects missing groups,
   stale names, duplicates, and incorrect case ownership. A scheduled or
   manually requested run covers the full supported-Python matrix and complete portable
   contract subset.
4. Pinned Codex installation smokes run only when installation or package-loading paths
   change. The weekly latest-Codex probe validates structure and then tests the CLI
   compatibility boundary; it does not repeat unrelated unit tests.
5. A full suite or matrix remains valid when impact cannot be bounded or an explicit
   repository or release contract requires it. Its existence, rollback value, or
   convenience alone is not a trigger.

## Alternatives considered

- Keep the six routine full-suite executions — rejected because five executions repeat
  unaffected behavior without proving a distinct platform or version risk.
- Build a dynamic dependency graph from coverage or test history — rejected because its
  maintenance and failure modes exceed this repository's size and needs.
- Run only focused tests with no fallback — rejected because new executable paths could
  be omitted before their mapping is added.

## Consequences

- Positive: ordinary changes receive faster evidence tied to their actual owner and
  consumers.
- Positive: unknown or shared selection changes remain conservative through an explicit
  full-suite fallback.
- Negative: the static map must be updated when a new executable component or test owner
  is added.
- Tradeoff: routine extra environments sample integration boundaries rather than repeat
  every policy/schema permutation. The scheduled full matrix remains the wider backstop.
- Operational: local branch comparison includes tracked worktree changes and excludes
  unrelated untracked files by default; untracked inclusion is explicit.
- Operational: existing installations adopt the governance wording on normal Rootloom
  upgrade; rollback restores the complete previous release. No wire format, stored data,
  or runtime compatibility path changes.

## Verification

- `tests/test_impact_tests.py` proves documentation-only selection, component mapping,
  platform/Codex flags, and fail-closed fallback.
- `tests/test_core_reset_eval.py` proves the same default and stop conditions remain in
  global guidance, the Change Skill, and its verification Reference.
- `scripts/validate_repo.py` binds the selector, CI topology, Make targets, governance
  wording, bilingual documentation, and this decision into repository validation.

## Revisit when

- Component boundaries grow enough that the static map becomes hard to audit.
- Measured CI failures show that an omitted platform/runtime lane would have caught a
  relevant defect, or that a selected lane repeatedly proves no distinct risk.
- The repository adopts an authoritative dependency graph that is simpler and at least
  as fail-closed as the static mapping.
