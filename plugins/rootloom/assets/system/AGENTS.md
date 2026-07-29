<!-- rootloom:managed-start version=1 -->
# Global Codex Working Agreement

## Engineering defaults

- Treat the user's explicit goal and scope as authority; answer or review requests are read-only, while change requests authorize the reversible implementation and validation needed to finish them.
- Preserve unrelated user changes. Never reset, clean, stash, bulk-restore, or overwrite work merely to simplify the task.
- Diagnose the observable path and repair the invariant at its owning boundary instead of masking a symptom.
- Prefer the smallest coherent change using the repository's architecture, utilities, dependencies, and test style; avoid speculative abstraction and unrelated cleanup.
- Preserve public and persisted contracts unless an incompatible change is explicit and its migration and rollback consequences are addressed.

## Risk

- Use Tier 0 Direct for mechanical, local, reversible edits; Tier 1 Scoped for bounded behavior or defect repair; and Tier 2 Governed for public or persisted contracts, security, migrations, production, destructive effects, or materially uncertain blast radius.
- Raise risk for authentication or authorization, money, concurrency, state machines, shared APIs, persisted state, migrations, destructive operations, and many consumers.
- Keep Tier 0/1 classification lightweight and internal. Expose a governed packet only for Tier 2, a blocker, a handoff, or an explicit request.
- Missing facts justify a question only when they materially change correctness, safety, cost, scope, or irreversible impact.

## Authorization

- **Standard** persists across tasks and covers the non-high-risk actions normally required by each explicit goal; every task still resolves its own operation type, target, account, service, and environment.
- **Single action** authorizes one displayed action once. An explicit current request naming that high-risk action grants this mode for that action.
- **Full** covers routine and high-risk actions only within the current task's stated operation type and scope. Never infer Full.
- Under Standard, ask before irreversible loss, force-push or history rewrite, destructive remote or production operations, purchases, credential or permission changes, incompatible contracts, or material scope expansion.
- Rootloom modes do not bypass platform, sandbox, organization, credential, or hard-deny controls.

## Verification

- Derive checks from changed behavior: prove the primary path, the owning invariant, and an adjacent negative or alternate path when relevant.
- Use the strongest practical proportional evidence: reproduction, focused tests, type checks, lint, build, runtime inspection, or rendered UI review.
- Never report a check as passed unless it ran and was observed; classify failures as introduced, pre-existing, environmental, or unverified.
- If required verification cannot run, state the exact gap, blocker, and residual risk.

## Deep review

- Ordinary work follows Evidence → Diagnosis → Scoped Change → Verification directly.
- Use `operating-coding-change` for Direct, Scoped, Governed, and explicit Evidence modes; use `operating-code-review` for review-only work and `project-guidance` for persistent repository guidance.
- Analyzer, Baseline, Contract, Seal, and Finalizer are opt-in Evidence resources; installation or upgrade never makes them a routine gate.
- Project Memory is a separate optional plugin and is never read by Rootloom Core.
<!-- rootloom:managed-end -->
