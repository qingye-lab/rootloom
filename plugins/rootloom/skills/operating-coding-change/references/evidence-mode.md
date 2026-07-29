# Evidence Mode

Evidence Mode is an explicit recording layer for a scoped or governed change. It is not
an everyday prerequisite and does not authorize commands or prove semantic correctness.

The deterministic helpers live under `plugins/rootloom/resources/evidence/`. Existing
low-level CLIs and frozen evidence formats remain compatible.

For advisory analysis:

```bash
python3 <plugin-root>/resources/evidence/analyze_change.py \
  --repo /absolute/path/to/repository \
  --task 'Describe the requested behavior' \
  --path src/anticipated-owner.py
```

For the usual strict code-change flow, prepare intake and the sealed contract in one
command before editing:

```bash
python3 <plugin-root>/resources/evidence/orchestrate_evidence.py prepare \
  --repo /absolute/path/to/repository \
  --task 'Describe the requested behavior' \
  --review-dir /absolute/path/outside-repository/run/intake \
  --path src/anticipated-owner.py \
  --path tests/test_owner.py \
  --verify 'python3 -m unittest tests.test_owner -v' \
  --target tests.test_owner \
  --primary-evidence 'What proves the caller-visible behavior' \
  --invariant-evidence 'What proves the owning rule' \
  --adjacent-evidence 'What proves a nearby negative or alternate path' \
  --root-cause-alignment PASS
```

After implementation, finalize the sealed commands in one step:

```bash
python3 <plugin-root>/resources/evidence/orchestrate_evidence.py finish \
  --repo /absolute/path/to/repository \
  --task 'Describe the requested behavior' \
  --review-dir /absolute/path/outside-repository/run/intake \
  --output /absolute/path/outside-repository/run/bundle \
  --semantic-review-confirmed
```

Use repeatable `--claim CLAIM-ID=EXPECTED-EVIDENCE` during `prepare` when the
same sealed verification command covers an additional governed behavior. The target
must occur literally in that command; this prevents an unbound passing command from
being recorded as claim evidence. For distinct specialized verification commands, use
the compatible low-level lifecycle below.

For custom intake, sensitive-path policy, or dangerous-deletion handling, use the
compatible low-level lifecycle:

```bash
begin_review.py → complete change-contract.draft.json → seal_contract.py → finalize_change.py
```

The orchestrator passes `--strict`, the intake baseline, sealed change contract, and
`--semantic-coverage reviewed`; the assertion still requires actual semantic review.
Analyzer suggestions are plans, not executed proof. Evidence/output paths must remain
outside both the worktree and resolved Git common directory.

Read [evidence-contract.md](evidence-contract.md) before strict capture or finalization.
