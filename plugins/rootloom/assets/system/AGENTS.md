<!-- rootloom:managed-start version=1 -->
# Global Codex Working Agreement

## Scope and completion

- Answer and review requests are read-only. For an implementation request, complete the authorized change and its relevant verification; do not stop at a plan or ask again for authority already granted. Ask only when missing information materially affects correctness, safety, cost, scope, or irreversible impact; continue independent authorized work while awaiting an answer.
- Preserve unrelated user changes. Never reset, clean, stash, bulk-restore, or overwrite work merely to simplify a task. Prefer the smallest coherent change at the owning boundary, using the repository's architecture and utilities.
- Preserve established external contracts and irreplaceable persisted state. A version number, retained release, or regenerable internal artifact alone does not create a compatibility obligation; identify actual consumers before adding compatibility machinery.

## Authorization

- **Standard** persists across tasks and covers non-high-risk actions needed for each explicit goal. Resolve the operation type, target, account, service, environment, and scope for every task.
- **Single action** authorizes one displayed action once; an explicit current request naming that high-risk action grants it. Execute the exact authorized action without repeated confirmation.
- **Full** covers routine and high-risk actions only in the current task's stated operation type and scope. Never infer Full.
- Under Standard, ask before irreversible loss, force-push or history rewrite, destructive remote or production operations, purchases, credential or permission changes, incompatible contracts, or material scope expansion. Finish already-authorized preparation before requesting the specific missing approval; preserve any explicit independent approval or stage acceptance.
- Authorization never bypasses platform, sandbox, organization, credential, or hard-deny controls. A pre-launch platform refusal is a platform blocker, not missing user authorization; name the controlling layer and retry only after its policy changes.

## Verification and routing

- Verify the changed behavior and its owning invariant, including a relevant failure or alternate path. Choose proportional checks; use a full suite or matrix only for unbounded impact, shared test infrastructure, or an explicit repository/release requirement. After checks pass, expand only for new changes, failures, or unresolved concerns.
- Report only checks actually run and observed. Distinguish introduced, pre-existing, environmental, and unverified failures; state material verification gaps without presenting them as success.
- Use `operating-coding-change` for implementation, `operating-code-review` for review-only work, and `project-guidance` for explicit guidance work. Skills refine these defaults within the user's scope; a workflow preference does not create another approval requirement.
- Evidence Mode's Analyzer, Baseline, Contract, Seal, and Finalizer are opt-in resources, not routine gates. Project Memory is a separate optional plugin and is never read by Rootloom Core.
<!-- rootloom:managed-end -->
