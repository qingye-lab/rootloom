# Semantic refinement

Keep a statement only when all are true:

- it changes a future agent's implementation, review, verification, or safety decision;
- it is durable across ordinary code changes;
- repository evidence supports it;
- it belongs at this directory scope;
- it is not already expressed by a closer source of truth or the managed block.

Prefer a short `## Project-specific invariants` section outside managed markers. Useful
facts include module ownership and dependency direction, public/persisted/security
contracts, generated-file ownership and canonical generators, canonical architecture or
migration documents, and non-obvious domain invariants.

Write one decision-bearing sentence per bullet and cite its supporting path. Delete or
avoid personality prose, generic software advice, copied framework documentation,
generated command lists, speculative architecture, historical narrative, full file
inventories, fixed file-length rules, and mandatory file-header documentation.

Create nested guidance only for a genuine boundary with distinct commands, ownership,
contracts, or invariants. The map should point to the source of truth rather than
duplicate it.
