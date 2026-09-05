# Verification contract

Use this Reference when the governed or Evidence route requires detailed verification.

## Choose evidence by changed behavior

Identify the requested behavior, the invariant at its owner, and a failure or alternate path
when relevant. Prefer fail-before/pass-after evidence for defects; otherwise explain the
trace, contract check, or runtime observation that supports the repair and its limits.
Assertions should prove behavior, not simply repeat implementation details.

Run the smallest relevant reproduction, focused test, type/lint check, build, package check,
or runtime/UI inspection. Documentation may stop after applicable structural validation and
a misuse-scenario review. These are choices driven by the change, not a mandatory staircase.

Broaden only for new changes, failures, unresolved risk, unbounded impact, shared test
infrastructure, or an explicit applicable gate. Unknown executable impact must not silently
skip verification. A platform/runtime lane must prove a distinct risk; do not repeat unaffected
checks. Preserve actual deployment or release acceptance requirements.

## Challenge the completion claim

Use a concrete counterexample or analogous caller when it can expose a plausible regression.
Inspect the final diff for lost user work, scope growth, compatibility drift, or unintended
artifacts. Remove a mechanism only when it has no useful behavior or protection; do not
invent a deletion to satisfy this review step.

Report checks actually executed and what they establish. Distinguish introduced, pre-existing,
environmental, and unverified failures. State missing evidence and its practical consequence.
For a formal Evidence defect report, `ROOT_CAUSE_ALIGNMENT: PASS` requires repair of the
violated invariant at its owner rather than downstream symptom suppression.
