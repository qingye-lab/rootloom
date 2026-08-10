# Verification contract

Use this Reference for scoped and governed implementation.

## Behavior map

Before choosing commands, map the change to:

1. **Primary path** — the original trigger or requested user-visible behavior.
2. **Owning invariant** — the rule enforced where the behavior or state is owned.
3. **Adjacent path** — one negative, edge, cancellation, cleanup, retry, or alternate
   path that must remain unchanged.

Prefer fail-before/pass-after regression evidence for defects. When that is impractical,
record an equivalent trace, contract proof, or runtime observation and the remaining
gap. Assertions should prove behavior rather than mocks, snapshots, incidental
structure, arbitrary sleeps, or the new conditional alone.

## Proportional checks

Run the smallest relevant evidence first:

1. original reproduction or focused regression;
2. affected unit and integration tests;
3. applicable typecheck and lint;
4. build, package, or generated-artifact checks;
5. browser or runtime inspection for user-facing behavior;
6. a broader suite only when a shared contract or common owner makes the impact
   materially unbounded.

Impact-scoped verification is the default. Select checks from the changed owner, its
known consumers, and the adjacent path in the behavior map. Do not repeat unaffected
tests across operating systems, runtimes, or versions unless each lane proves a distinct
risk. Use a full suite or matrix only when impact cannot be bounded, shared test-selection
or build infrastructure changed, or an explicit repository or release contract requires
it. An unclassified executable path must fail closed to that broader check. A
documentation-only change may stop after applicable structural or documentation validation.

Classify every failure as introduced, pre-existing, environmental, or unverified. If a
required check cannot run, name the exact missing evidence, blocker, and residual risk.

## Challenge pass

After the reported checks pass:

- inspect an analogous producer, consumer, or sibling for the same defect class;
- attempt the strongest counterexample to the completion claim;
- audit for lost user changes, scope growth, compatibility drift, data/retry/cleanup
  regressions, manifest or generated noise, secrets, logs, and temporary artifacts;
- delete a guard, flag, wrapper, record, or abstraction when it does not change a
  concrete decision.

For a defect, `ROOT_CAUSE_ALIGNMENT: PASS` requires that the diff repairs the violated
invariant at its owning boundary rather than masking a downstream symptom.
