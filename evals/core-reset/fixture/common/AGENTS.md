# Evaluation fixture guidance

- Treat the task's allowed paths as the complete implementation scope.
- Preserve unrelated tracked and untracked work exactly.
- Use `python3 -m unittest discover -s tests -v` unless the task names another command.
- Report only commands that actually ran and distinguish their result from repository state.
- Use only Rootloom capabilities exposed by the current Codex session. If a requested
  Rootloom capability is absent, do not search outside this repository or the current
  `CODEX_HOME` to discover another installation.
