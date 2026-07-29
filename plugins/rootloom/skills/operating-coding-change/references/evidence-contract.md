# Evidence contract

Baseline v2–v4, Summary revision 5, change-contract, manifest, and seal wire formats are
frozen compatibility contracts. Do not add a format, state, or schema merely to express
new policy.

## Intake and scope

- Strict Tier 1/2 evidence requires an intake created before implementation and at
  least one `--path`, unless `--allow-all-paths` is explicit.
- Default intake requires a clean HEAD/index; `--allow-dirty-baseline` records existing
  work. Never recreate a missing pre-change baseline after editing.
- A sealed `rootloom-change-contract-v1` binds allowed/forbidden paths, compatibility,
  rollback, and structured primary/invariant/adjacent claims to exact verification
  commands.
- The contract never authorizes a command. Every mapped command must still be passed
  with `--verify`.

## Capture and privacy

- Two consecutive bounded captures must agree. Each Git child and the aggregate
  capture have finite time budgets.
- Evidence and output paths must be outside the repository worktree and resolved Git
  common directory, with symlink redirection rejected lexically.
- Sensitive material is metadata-only. A material metadata change or newly discovered
  ignored addition quarantines changed endpoints before ordinary content capture.
- `--reviewable-path` is intake-only, exact-file, bounded, and unable to override strong
  or declared secrets. Ignored, index-suppressed, symlinked, hardlinked, ambiguous, or
  incorrectly cased targets fail closed.
- Verification argv and output are retained verbatim; never put credentials in a
  command or print them.

## Execution and quality

Verification commands run without a shell in a controlled process group/tree. This is
not a sandbox and cannot govern detached managers, containers, privileged background
processes, Git administration, or external state.

Strict mode revalidates evidence bytes, seals, Git base, output ownership, repository
capture, and sensitive-material state after commands run. Classify failures honestly.

`semantic_coverage: reviewed` is an operator assertion, not machine proof. Only a
workflow-sealed mechanical chain plus that assertion yields
`REVIEW_EVIDENCE_COMPLETE`; use `evidence_complete` for stable automation. Redaction
caps the result at `REVIEW_REQUIRED_WITH_REDACTIONS`. Advisory mode may exit zero for a
generated bundle while retaining `quality_status: UNVERIFIED` and `passed: false`.

Protected deletion still requires each exact path through
`--confirm-dangerous-delete`. Pure verification requires `--allow-no-change`. After the
bundle is written, inspect `diff.patch`, `test.log`, and `summary.json`; generation
alone is not acceptance.
