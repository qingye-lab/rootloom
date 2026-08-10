# Setup guidance

- `scripts/setup_rootloom.py` owns Codex-home writes and capability-to-artifact mapping; keep it plan-first, conflict-refusing, lock-serialized, backup-backed, hash-aware, mode-preserving on rollback, and atomic per file. Treat global `AGENTS.md` as a marker-bounded managed block, preserve all content outside it, and never turn malformed markers into whole-file replacement.
- Public presets are only `skills-only`, `guidance`, and `personal`; `engineering` remains a hidden compatibility alias.
- `autonomy` is the canonical optional authorization capability; accept legacy `command-safety` input without presenting it as deterministic safety.
- Setup is the only supported writer for component policy and must always emit exact integer `version: 1`.
