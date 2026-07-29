# Support

Use the appropriate channel so questions remain actionable:

- **Usage question or suspected bug:** open an issue with the provided template.
- **Feature proposal:** open a feature request and explain the repository evidence and safety model it should preserve.
- **Security concern:** follow [SECURITY.md](SECURITY.md); never post it publicly.
- **Codex platform behavior:** first reproduce with the latest Codex version and identify whether the behavior belongs to this plugin or the Codex runtime.

Before filing, run:

```bash
codex --version
python3 --version
python3 plugins/rootloom/skills/project-guidance/scripts/seed_project_guidance.py \
  probe --cwd /path/to/repository
python3 plugins/rootloom/skills/setup-rootloom/scripts/setup_rootloom.py \
  list-components
python3 plugins/rootloom/skills/setup-rootloom/scripts/setup_rootloom.py \
  --codex-home /path/to/disposable-codex-home status
```

Redact credentials, private paths, proprietary code, and personal information from all output.
