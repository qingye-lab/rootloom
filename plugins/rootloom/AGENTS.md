# Rootloom plugin guidance

- Keep runtime helpers local, bounded, network-free, and standard-library-only unless a public dependency decision explicitly changes that contract.
- `hooks/run_component_hook.py` owns lifecycle enablement: only managed component policy with exact integer `version: 1` may enable a Hook; absent, malformed, future-version, or symlinked policy fails closed.
- The SessionStart project-context Hook is read-only. Only an explicit `project-guidance` invocation may create or refresh repository `AGENTS.md`.
- Personal Core must not regain Human Review, approval state machines, immutable audit chains, recovery journals, or other Archived Assurance machinery by default.
- Keep secret-material privacy classification and security-domain risk classification centralized in `lib/rootloom_paths.py`; consumers must not grow divergent copies.
