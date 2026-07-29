# Migrate from Rootloom 4.0 to 4.1

Rootloom 4.1 keeps the four public Skills and all frozen Evidence wire formats. Existing
Baseline v2–v4, Summary revision 5, change-contract, review-manifest, and seal files
remain readable; no artifact migration is required.

## Routine Change routing

Mechanical, local, reversible work now takes an explicit Direct fast path. It reads no
Change Reference and should inspect only the target, make the change, run the smallest
relevant check, and inspect the target diff. A dirty worktree alone is not a reason to
switch to Governed or Evidence mode; it remains work that must be preserved exactly.
File count or a local callable/signature shape also does not prove a public contract.
Governed routing needs shared/external consumers, compatibility obligations, or another
governed risk signal.

Initial cause uncertainty stays in Scoped while bounded diagnosis establishes the
owning boundary. Governed routing applies only when material root-cause uncertainty
remains after that diagnosis, or another governed signal is present. Public/persisted
contracts and explicit evidence requests retain their Governed or Evidence routing.
Scoped is now self-contained in the Change Skill and, like Direct, reads no Reference.
It still maps verification to the primary path, owning invariant, and an adjacent path,
then performs one post-check challenge. Routine work batches independent reads and final
state inspection to avoid model/tool rounds that cannot change the next decision.

## Strict Evidence shortcut

The existing `begin_review.py`, `seal_contract.py`, and `finalize_change.py` commands
remain supported. For the common strict lifecycle, use the additive orchestrator:

```bash
python3 <plugin-root>/resources/evidence/orchestrate_evidence.py prepare \
  --repo /absolute/path/to/repository \
  --task 'Describe the change' \
  --review-dir /absolute/path/outside-repository/run/intake \
  --path src/owner.py \
  --verify 'python3 -m unittest tests.test_owner -v' \
  --target tests.test_owner \
  --primary-evidence 'Caller-visible behavior is covered' \
  --invariant-evidence 'Owning rule is covered' \
  --adjacent-evidence 'Nearby alternate path is covered'

# Make and review the scoped change.

python3 <plugin-root>/resources/evidence/orchestrate_evidence.py finish \
  --repo /absolute/path/to/repository \
  --task 'Describe the change' \
  --review-dir /absolute/path/outside-repository/run/intake \
  --output /absolute/path/outside-repository/run/bundle \
  --semantic-review-confirmed
```

For defect repair, add `--root-cause-alignment PASS` to `prepare`. Add explicit
`--claim CLAIM-ID=EXPECTED-EVIDENCE` entries when the same sealed verification command
covers additional required behaviors. Use the low-level lifecycle for distinct
specialized verification commands. The orchestrator is a single-command verification
convenience path, not the default for multiple targets or commands, migrations,
mixed-version checks, security boundaries, or build-plus-runtime proof. `finish` reads
only the sealed commands and requires the semantic-review confirmation; it does not make
an unreviewed bundle pass.

## Evaluation and release evidence

The historical v1 matrix and its 4.0 result remain historical. New candidates use the
v2 suite, including Guidance and Setup scenarios, actual completion-token fields,
exact route scoring, deterministic randomization, and per-run Codex-home isolation.
Its current `rootloom-core-reset-mechanical-v3` scorer recognizes legal managed marker
attributes, absolute or Codex-home-relative cached Skill paths, and bounded equivalent
quality wording. It also resolves a bounded shell-loop Reference list when the command
joins those relative paths to one observed cached Skill directory. The formal gate
rejects an older or missing scoring identifier.

Use `make core-reset-eval` for the current structural gate. It intentionally does not
claim behavioral acceptance. A formal candidate requires a scored v2 result with at
least three repetitions:

```bash
make core-reset-release-eval CORE_RESET_RESULTS=/absolute/path/results-v2.json
```

Keep raw model transcripts outside the repository and bind the sanitized result to the
final `plugins/rootloom/` tree digest.

The retained [`results-4.1.0.json`](../evals/core-reset/results-4.1.0.json) and
[candidate report](../evals/core-reset/reports/4.1.0.md) contain all 126 cells. The
report records that both previous efficiency failures are corrected. One Governed
Reference-route miss and two small quality-score regressions keep the complete formal
gate and version-tag workflow fail-closed.

## Project guidance Hook

The SessionStart renderer now ignores package-script names containing shell-like or
instruction-like characters. Normal names such as `test:unit` continue to appear. If a
repository uses an unusual script name that no longer appears in temporary context,
run it explicitly from the package manifest rather than copying it into guidance.

The Hook remains read-only. Repository guidance may request automatic validation, but
persistent seed/refresh/refinement needs explicit user intent. The only exception is
one refinement of the marked file through the exact standalone
`<!-- rootloom:refine-once version=1 -->` marker, consumed by the successful write.
