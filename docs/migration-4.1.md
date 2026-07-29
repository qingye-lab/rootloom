# Migrate from Rootloom 4.0 to 4.1

Rootloom 4.1 keeps the four public Skills and all frozen Evidence wire formats. Existing
Baseline v2–v4, Summary revision 5, change-contract, review-manifest, and seal files
remain readable; no artifact migration is required.

## Direct Change routing

Mechanical, local, reversible work now takes an explicit Direct fast path. It reads no
Change Reference and should inspect only the target, make the change, run the smallest
relevant check, and inspect the target diff. A dirty worktree alone is not a reason to
switch to Governed or Evidence mode; it remains work that must be preserved exactly.
File count or a local callable/signature shape also does not prove a public contract.
Governed routing needs shared/external consumers, compatibility obligations, or another
governed risk signal.

Behavioral changes, public/persisted contracts, uncertain causes, and explicit evidence
requests retain their existing Scoped, Governed, or Evidence routing.

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
specialized verification commands. `finish` reads only the sealed commands and requires
the semantic-review confirmation; it does not make an unreviewed bundle pass.

## Evaluation and release evidence

The historical v1 matrix and its 4.0 result remain historical. New candidates use the
v2 suite, including Guidance and Setup scenarios, actual completion-token fields,
exact route scoring, deterministic randomization, and per-run Codex-home isolation.
Its current `rootloom-core-reset-mechanical-v3` scorer recognizes legal managed marker
attributes, absolute or Codex-home-relative cached Skill paths, and bounded equivalent
quality wording; the formal gate rejects an older or missing scoring identifier.

Use `make core-reset-eval` for the current structural gate. It intentionally does not
claim behavioral acceptance. A formal candidate requires a scored v2 result with at
least three repetitions:

```bash
make core-reset-release-eval CORE_RESET_RESULTS=/absolute/path/results-v2.json
```

Keep raw model transcripts outside the repository and bind the sanitized result to the
final `plugins/rootloom/` tree digest.

## Project guidance Hook

The SessionStart renderer now ignores package-script names containing shell-like or
instruction-like characters. Normal names such as `test:unit` continue to appear. If a
repository uses an unusual script name that no longer appears in temporary context,
run it explicitly from the package manifest rather than copying it into guidance.
