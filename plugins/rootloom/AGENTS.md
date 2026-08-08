# Rootloom plugin guidance

- Keep runtime helpers local, bounded, network-free, and standard-library-only unless a public dependency decision explicitly changes that contract.
- `hooks/run_component_hook.py` owns lifecycle enablement: only managed component policy with exact integer `version: 1` may enable a Hook; absent, malformed, future-version, or symlinked policy fails closed.
- The SessionStart project-context Hook is read-only. Only an explicit `project-guidance` invocation may create or refresh repository `AGENTS.md`.
- `skills/project-guidance/scripts/seed_project_guidance.py` owns the canonical bounded session-context renderer and host protocol envelopes. Consumer-repository adapters must vendor it byte-for-byte rather than fork its semantics.
- Host adapter templates live outside the installable plugin under `adapters/rootloom/`; they are opt-in, non-installing, and must not add permission gates or host configuration to `portable/rootloom/`.
- Portable packaging uses an explicit per-Skill file allowlist. Reject unapproved source files instead of copying local, hidden, or temporary artifacts into the generated package.
- Personal Core must not regain Human Review, approval state machines, immutable audit chains, recovery journals, or other Archived Assurance machinery by default.
- Keep secret-material privacy classification and security-domain risk classification centralized in `lib/rootloom_paths.py`; consumers must not grow divergent copies.
