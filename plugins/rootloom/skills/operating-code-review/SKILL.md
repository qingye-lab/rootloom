---
name: operating-code-review
description: Review without editing; report evidence-backed defects by severity and disclose material verification gaps.
---

# Code review

Review only. Do not modify files or execute external changes unless the user explicitly
changes the task. Preserve unrelated work and respect the active access and approval rules.

Read the relevant diff and enough callers, consumers, contracts, or tests to assess its
behavior. Treat the author's explanation and previous findings as leads, not proof. Load
specialized References only for the affected surface:

- security or trust boundaries: [security-review.md](references/security-review.md);
- persistent data or migrations: [data-and-migration-review.md](references/data-and-migration-review.md);
- dependencies, packaging, or release: [dependency-and-release-review.md](references/dependency-and-release-review.md);
- rendered UI or interaction: [ui-review.md](references/ui-review.md).

For a defect repair, verify that the changed owner explains and fixes the original trigger.
Challenge a completion claim with a concrete counterexample where useful; inspect an
analogous implementation only when it could reveal the same failure. Consider cancellation,
retries, partial failure, and compatibility when the changed behavior makes them relevant.
Do not require every review to traverse every failure category or run a fixed test suite.

Report material findings by severity (Critical, High, Medium, Low), with an exact location,
trigger and impact, supporting evidence, confidence, and the smallest concrete correction.
Keep questions and optional improvements separate; style preferences are not defects.

If there are no material findings, say so and describe the reviewed scope and material
gaps. Distinguish executed checks from suggested checks and do not claim unobserved success.
Explain root-cause alignment for defect reviews; emit a machine-style status field only
when an applicable reporting contract requires it. No empty sections or inapplicable
checklist fields are needed.
