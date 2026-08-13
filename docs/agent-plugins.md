# Agent Plugins portable preview

Rootloom ships two independent package roots:

| Package | Public Skills | Runtime boundary |
| --- | --- | --- |
| `plugins/rootloom/` | Change, Review, Project Guidance, Setup | Native OpenAI Codex plugin, including optional Hook and setup |
| `portable/rootloom/` | Change, Review, Project Guidance | Agent Plugins 1.0.0 portable preview; Skills only |

The portable package has a root `plugin.json` using the canonical
`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` identifier. Compatible
clients discover its immediate `skills/` children according to the Agent Plugins and
Agent Skills specifications. It deliberately does not contain `.codex-plugin`, Hooks,
host configuration, OpenAI interface metadata, Setup, Rules, Memory, or MCP servers.
Project Guidance is self-contained: its deterministic helper and lock implementation
are vendored from native source, while Codex `agents/` metadata is excluded.

Agent Plugins 1.0.0 is currently a Working Draft. The standard defines package loading
and component discovery, but leaves distribution, installation, permissions, updates,
and client UX to each client. Follow the target client's installation flow and select
`portable/rootloom/` as the plugin root. Do not install both the native and portable
Rootloom packages into the same client; the standard does not define duplicate-Skill precedence.

## One package, host-specific loaders

Rootloom uses the standard package without a Cursor manifest, VS Code extension, Copilot
manifest, or Kiro legacy `POWER.md`. Cursor, VS Code, GitHub Copilot, and Kiro all document
root `plugin.json` Agent Plugins support. The three Skills remain identical across
hosts. Optional consumer-repository templates under `adapters/rootloom/` provide only
the lifecycle envelope that Agent Plugins v1 does not standardize.

| Host | Package | Current entry point | Runtime evidence |
| --- | --- | --- | --- |
| Cursor IDE | `portable/rootloom/` unchanged | Local plugin directory | Official loader documented; Rootloom runtime smoke pending |
| VS Code | `portable/rootloom/` unchanged | `chat.pluginLocations` | Official loader documented; Rootloom runtime smoke pending |
| GitHub Copilot CLI | `portable/rootloom/` unchanged | `--plugin-dir` or `plugin install` | Official loader documented; Rootloom runtime smoke pending |
| GitHub Copilot coding agent | Same standard format | Requires a resolvable Copilot marketplace entry | Rootloom has no current cloud install channel |
| Kiro IDE | `portable/rootloom/` unchanged | Import Power from a local folder | Official loader documented; Rootloom runtime smoke pending |
| Codex | `plugins/rootloom/` native package | Existing Rootloom marketplace | Native compatibility smoke; full four-Skill surface |

The package has no platform fork. A future host-only feature must use an Agent Plugins
client extension or a separate adapter only when the standard cannot express it, and
must not change the portable Skills for every other host.

### Optional read-only SessionStart adapters

`adapters/rootloom/` contains non-installing templates for Cursor, a shared VS
Code/GitHub Copilot hook file, and Kiro. Each invokes the same vendored Project Guidance
renderer, permits read-only inspection of the selected repository, caps the complete
advisory context at 4 KiB, and never creates or updates `AGENTS.md`. The templates add
no tool gates, permissions, Rules, MCP servers, or automatic setup.
The shared `.github/hooks/rootloom.json` carries the required exact integer
`"version": 1`; malformed input and host-incompatible diagnostics go only to stderr,
never into agent context.

Before copying a template, inspect existing `.cursor/`, `.github/hooks/`, `.kiro/hooks/`,
and `.rootloom/rootloom-adapter/` paths. Resolve any owner or command conflict instead
of overwriting it. Copy the contents of exactly one applicable `template/` directory
into the consumer repository root. To remove it, delete only the exact Rootloom hook
JSON and the two files under `.rootloom/rootloom-adapter/`, after confirming they still
match the template and are not shared. Start a new agent session afterward.

Static schema, source-equality, path-with-spaces, malformed-input, and synthetic
envelope checks pass in this repository. Live Cursor, VS Code, Copilot, and Kiro
runtime smokes remain pending; these templates are not a runtime-parity claim.

### Cursor IDE

Clone this repository, then place or link the complete standard package root in Cursor's
local plugin directory:

```bash
mkdir -p ~/.cursor/plugins/local
ln -s "/absolute/path/to/rootloom/portable/rootloom" \
  ~/.cursor/plugins/local/rootloom
```

Restart Cursor or run **Developer: Reload Window**. Updating the checkout followed by a
reload updates a linked install. Manage Skill invocation in **Customize → Skills**. To
remove this exact linked preview, run `unlink ~/.cursor/plugins/local/rootloom`, reload,
and start a new chat. Cursor Marketplace installation is not claimed: the current
Rootloom repository URL resolves to the repository root, while the package manifest is
nested under `portable/rootloom/`; the public submission flow has not been verified for
that monorepo path. See [Cursor plugins](https://cursor.com/docs/plugins).

### VS Code

Enable Agent Plugins and register the same package root in user settings:

```json
{
  "chat.plugins.enabled": true,
  "chat.pluginLocations": {
    "/absolute/path/to/rootloom/portable/rootloom": true
  }
}
```

A workspace setting may instead use the relative path `portable/rootloom`. Set the
mapping to `false` to disable it or remove the mapping to unregister it, then run
**Developer: Reload Window**. **Chat: Install Plugin From Source** documents a repository
URL but no monorepo-subdirectory selector, so the Rootloom repository root is not a
verified direct-source install. See [VS Code Agent Plugins](https://code.visualstudio.com/docs/agent-customization/agent-plugins)
and [AI settings](https://code.visualstudio.com/docs/agents/reference/ai-settings).

### GitHub Copilot CLI and coding agent

Copilot CLI can load the same directory for one invocation or install the exact remote
subdirectory:

```bash
copilot --plugin-dir "$PWD/portable/rootloom" \
  -p "Use operating-code-review to review this repository without editing files."
copilot plugin install "$PWD/portable/rootloom"
copilot plugin install liyanqing90/rootloom:portable/rootloom
```

Use `copilot plugin list`, `copilot plugin update rootloom`, `copilot plugin disable
rootloom`, `copilot plugin enable rootloom`, and `copilot plugin uninstall rootloom` for
the installed lifecycle. VS Code can also discover Copilot's installed-plugin directory.
See the [Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference).

GitHub Copilot's coding agent is listed as an Agent Plugins-compatible client, but its
repository `enabledPlugins` setting expects a plugin spec that resolves through a known
marketplace. Rootloom does not yet publish the portable package through such a
marketplace. Do not add an `OWNER/REPO:portable/rootloom` `enabledPlugins` entry and call
it installed; cloud support remains a release-channel and live-smoke gate.

### Kiro IDE

In **Powers → Add Custom Power → Import power from a folder**, select
`portable/rootloom/` and install it. Kiro's current Power format is Agent Plugins, so no
`POWER.md` or `dev.kiro/` adapter is required. The GitHub import flow requires
`plugin.json` at the repository root and therefore cannot consume the current Rootloom
repository URL directly. Use the local folder until a release source exposes the
portable package as its root. Kiro documents update controls but not a stable removal
or storage contract. Do not delete an assumed cache path; a release smoke must use the
current Powers UI to disable or remove the Power, start a new chat, and confirm all three
Rootloom Skills disappear before Rootloom claims rollback support. See
[Kiro Powers](https://kiro.dev/docs/powers/) and [Power installation](https://kiro.dev/docs/powers/installation/).

### Runtime smoke gates

For Cursor, VS Code, Copilot CLI, and Kiro, a release-specific smoke must show exactly
`operating-code-review`, `operating-coding-change`, and `project-guidance`; invoke Review
without changing a fixture worktree; complete a small Change with reported verification;
inject the same bounded read-only context through the selected opt-in adapter; and make
an explicit Evidence request fail closed. Claiming Artifact Context support additionally
requires a cache-miss fixture to run in a no-history worker, finalize to a bounded receipt,
and repeat as a cache hit without reading the raw file again. It must also confirm that no Rules, Setup,
permission policy, or MCP configuration appeared. The repository does not yet contain passed,
current-version runtime evidence for those hosts, so these checks remain pending rather
than reported as passed.

## Capability boundary

| Capability | Portable status |
| --- | --- |
| Review workflow and its four relative References | Included |
| Direct and Scoped Change | Included |
| Governed reasoning and verification contract | Included |
| Durable decision template | Uses the headings embedded in the Governed Reference when the native template is absent |
| Evidence Mode | Unavailable; the portable package fails closed because plugin-wide Evidence helpers are absent |
| Project Guidance probe/seed/validate | Included; persistent writes require exact user intent |
| Read-only 4 KiB SessionStart context | Same renderer; Codex native Hook or optional host adapter |
| Artifact Context identity/cache/24 KiB receipt | Included; semantic misses require a no-history worker supplied by the host |
| Setup, `~/.codex`, command Rules, Hook enablement | Codex-native only |
| MCP servers | Not shipped |

Portable packaging does not prove equivalent model behavior or tool availability in
every client. Repository CI validates the manifest contract, Agent Skills envelopes,
package containment, relative References, an exact three-Skill allowlist, and byte-for-byte
synchronization with the native source Skills. Codex has a separate compatibility smoke;
Cursor, VS Code, GitHub Copilot, Kiro, and other clients still require release-specific
runtime smoke tests before Rootloom claims feature parity.

The Artifact Context helper is portable, network-free, and standard-library-only. It can
prepare and validate receipts in any compatible host, but the Skill must stop before reading
raw artifacts unless that host exposes a worker with no inherited conversation. A normal conversation-inheriting child is not an equivalent fallback. The lane does not use an MCP
server and does not modify already-recorded task history.

## Maintainer workflow

The native Skill directories remain the single editable source. Regenerate the checked-in
portable mirror after changing Change, Review, or Project Guidance. Regenerate the
host templates after changing the Project Guidance helper or lock:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_portable_plugin.py --write
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_portable_plugin.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_host_adapters.py --write
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_host_adapters.py
make portable-compatibility-smoke
```

Checked-in Rootloom Skills deliberately use a canonical, single-line Agent Skills
frontmatter subset containing only `name` and `description`: values start with an ASCII
letter, use printable ASCII, and exclude YAML `:` and `#` delimiters. This keeps
validation standard-library-only while rejecting ambiguous or structured YAML values.
Do not add optional fields or broaden this scalar subset without extending the parser,
tests, and portability contract together.

`scripts/validate_repo.py` fails if the portable package or adapters drift, contain an
unexpected file or symlink, expose Setup, use an invalid manifest, or no longer match
their native source and shared identity fields. Portable synchronization also uses an
explicit per-Skill file allowlist and rejects local, hidden, or temporary source files
instead of silently publishing them. The optional smoke installs the isolated portable
package into a disposable Codex home; it does not establish behavior in other clients.

## Migration and rollback

Existing Codex users do not migrate automatically and keep installing
`rootloom@rootloom`. The portable package is an additional preview channel, not an
upgrade of the native package. This preview does not publish a user-facing portable
Codex marketplace entry, so Codex users should keep the native package. Native Codex and
portable installations in another host may coexist because they are different clients;
do not load both package roots in one client.

If you uninstall the native Codex package for another reason, first use
`$setup-rootloom` to inspect and roll back any optional Setup, then run
`codex plugin remove rootloom@rootloom` and end the current task. Plugin removal alone
does not remove copied `~/.codex` guidance, Rules, Hook policy, or setup state.

Removing or disabling the portable package is client-managed and does not undo
repository changes made during earlier tasks; start a new task after removal so the
client refreshes Skill discovery. Maintainer rollback of this packaging feature is
additive and local: remove the portable package, synchronization/validation, and
portability documentation while leaving the native Codex package and marketplace untouched.

See the [Agent Plugins specification](https://agent-plugins.org/specification),
[Agent Skills specification](https://agentskills.io/specification), and the current
[compatible-client directory](https://agent-plugins.org/compatible-clients).
