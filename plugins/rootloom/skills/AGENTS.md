# Rootloom Skills guidance

- `project-guidance/scripts/seed_project_guidance.py` owns deterministic repository evidence collection; `project-guidance/references/semantic-refinement.md` owns model-dependent semantic judgment. Do not move semantic inference into Hooks or scanners.
- Durable decision records are a governed Change mode, not a public Skill; record only accepted architecture, contract, dependency, security, data, or operational choices.
- Keep Evidence references out of Direct mode. Project Memory belongs to the separate `rootloom-memory` plugin and must not return to this Skill catalog.
