# Evidence resource guidance

- Baseline v2–v4, Summary revision 5, contract, manifest, and seal wire formats are frozen; readers validate historical structure and hashes separately from current execution policy.
- `finalize_change.py` owns review bundle output, current-policy gates, dangerous-deletion confirmation, command execution, and evidence-honest provenance. Changes require focused regression coverage.
- `begin_review.py`, `seal_contract.py`, and `runner/` own the opt-in draft/seal lifecycle, stable capture, repository-base binding, strict JSON, scope, and verification contracts.
- `runner/evidence_paths.py` owns lexical evidence/output paths and containment in both the worktree and resolved Git common directory.
- `runner/intelligence.py` remains advisory, local, explainable, bounded, and unable to execute its suggested commands.
- Reviewable content may be read only after current policy passes; incompatible historical declarations return `reintake-required` first.
