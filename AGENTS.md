# Rootloom repository guidance

- Installable sources are `plugins/rootloom/` for the four-entry Core and `experiments/rootloom-memory/` for separately installed experimental Memory; `.agents/plugins/marketplace.json` must point to those exact directories.
- `main` contains Core plus optional Autonomy/Evidence; Project Memory is a separate optional plugin, and the unmaintained 1.2.19 branch is the Archived Assurance Edition. See `docs/decisions/2026-07-29-rootloom-4-core-reset.md`.
- Component ownership and safety rules belong in the nearest nested `AGENTS.md`; keep this root file limited to constraints that apply across the repository.
- Changes to installation, public behavior, contracts, or user configuration must update both English and Chinese documentation and extend `scripts/validate_repo.py` when an executable repository contract changes.
- Baseline v2–v4 and Summary revision 5 are frozen compatibility formats; do not add Evidence formats, states, or schemas without a separately accepted product decision.
- Release truth lives in GitHub PRs, Actions, tags, and Releases. Keep `CHANGELOG.md` user-observable, batch formal releases, and do not commit one-time plans or publication/final records.
- Preserve unrelated work and default to impact-scoped checks. Use full `make check` only when impact cannot be bounded, shared test-selection infrastructure changes, or an explicit repository or release gate requires it.
