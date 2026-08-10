# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.2.2] - 2026-08-10

### Fixed

- Make optional global setup merge only Rootloom's marker-bounded block in
  `~/.codex/AGENTS.md`. Existing user guidance is preserved during install and upgrade,
  content outside the block no longer counts as drift, and malformed markers stop
  instead of falling back to whole-file replacement.

## [4.2.1] - 2026-08-10

### Fixed

- Require post-cutover consumer evidence before runtime compatibility is introduced.
  Regenerable internal versioned artifacts now remain Scoped, use only the current
  contract, restore the complete old release for rollback, and use the matching old
  runtime for historical replay.
- Add a Core Reset regression that rejects legacy readers, adapters, dual paths, flags,
  and migrations for a regenerable plan record while preserving Governed coverage for
  real public APIs and irreplaceable stored data.
- Keep generated `__pycache__/*.pyc` verification residue visible in Core Reset evidence
  without misclassifying it as a source-scope escape; scoring contract v5 continues to
  reject every real path outside the declared implementation scope.

## [4.2.0] - 2026-08-08

### Added

- Add an isolated Agent Plugins 1.0.0 portable preview with Change, Review, and
  self-contained Project Guidance, a
  deterministic source synchronizer, offline manifest/containment/parity checks, and a
  disposable Codex installation smoke.
- Document the exact portable capability matrix, client-owned installation boundary,
  native/portable coexistence rule, and additive rollback in English and Chinese.
- Document zero-fork loading of the same Agent Plugins package in Cursor, VS Code,
  GitHub Copilot CLI, and Kiro, including host lifecycle and runtime smoke gates.
- Add deterministic, opt-in consumer-repository SessionStart templates for Cursor,
  VS Code/GitHub Copilot, and Kiro, with one byte-identical bounded read-only renderer,
  a machine-readable capability contract, and explicit pending live-runtime status.

### Changed

- Make Skills-only Change fail closed when plugin-wide Evidence helpers are unavailable,
  and provide durable-decision headings when the native template is absent.
- Keep checked-in Skill frontmatter in a deterministic two-field scalar subset and
  reject native-manifest or source-symlink changes that would break package isolation.
- Make the shared Change Skill refer to the host instruction chain without assuming
  Codex, while retaining Codex as the native adapter for non-portable capabilities.
- Require Hook config version 1 for the shared VS Code/Copilot adapter, validate the
  complete repository-to-source symlink chain, and keep non-Codex diagnostics out of
  agent context. Keep shared Project Guidance invocation wording host-neutral and reject
  unapproved Skill-local files before portable packaging.
- Keep Direct shell work batched, recognize equivalent migration no-op wording in Core
  Reset scoring, and compare elapsed time only across task-successful variant pairs.

### Fixed

- Recover interrupted optional Setup apply and rollback operations from a bounded staged
  transaction journal, while refusing post-interruption target drift and preserving the
  existing backup and rollback chain.

### Security

- Re-review and pin the refreshed official VibeLoft browser runtime after a zero-egress
  Chromium inspection confirmed the existing endpoint, credential, privacy, and
  navigation boundaries.

## [4.1.0] - 2026-07-30

### Added

- Add the Core Reset v2 evaluator: actual Codex token-usage fields, isolated randomized
  repetitions, exact public-Skill/Reference route checks, and Guidance/Setup scenarios.
- Add `orchestrate_evidence.py prepare` and `finish` as an additive, lower-turn strict
  Evidence path while retaining the frozen Baseline v2–v4, Summary revision 5, contract,
  manifest, seal, and existing low-level CLI formats.
- Add a formal `core-reset-release-eval` target that requires a supplied v2 scored matrix
  with at least three repetitions.
- Load the official VibeLoft browser telemetry runtime exactly once on the public GitHub
  Pages site, with a repository contract for the registered product, production origin,
  privacy signals, and collector boundary.

### Changed

- Make Direct Change a real fast path: it reads no Reference, limits inspection to the
  exact target, runs the smallest relevant check, and treats a dirty worktree as a
  preservation constraint rather than an escalation signal.
- Make Governed and Evidence Reference loading explicit and route-scored rather than
  relying on implicit composition.
- Require Governed and Evidence References before the first edit, add a compact
  Governed completion contract, and stop when a required Reference cannot load.
- Advance Core Reset scoring to mechanical v4 so successful relative Reference reads
  (including quoted plugin paths containing spaces) and bounded equivalent
  Review/Migration wording are scored from their actual evidence instead of reported
  as route or quality regressions.
- Distinguish exact user authorization from a pre-launch host-policy refusal; Rootloom
  does not repeat consent prompts or misreport that platform blocker as missing consent.
- Require Project Guidance completion to detect and remove only current-task
  verification artifacts, preventing cache, coverage, or build output from escaping the
  authorized guidance path.
- Make Direct and Scoped self-contained routine routes with no Reference load, batch
  independent inspection, and retain behavior-mapped verification plus one challenge
  pass inside the Change Skill.
- Keep initially unknown defect causes in bounded Scoped diagnosis and escalate only
  material root-cause uncertainty that remains afterward.
- Allow repository guidance to request automatic validation while requiring explicit
  user intent or one exact consumable marker for persistent refinement.
- Define the Evidence orchestrator as a single-verification-command convenience path;
  heterogeneous governed evidence continues through the low-level lifecycle.
- Retain the sanitized 126-run 4.1 candidate matrix and report, and enforce that result
  in a version-tag workflow that fails closed when the formal rubric is not satisfied.
- Refresh that matrix against the self-contained Routine tree so previous token
  efficiency, route, and quality failures pass without weakening thresholds.

### Fixed

- Keep the website workflow cards equal in height and prevent hover styling from
  changing padding, content position, or layout.

### Security

- Exclude unsafe `package.json` script names from generated SessionStart project context
  so untrusted script metadata cannot be rendered as a suggested shell command.
- Keep the VibeLoft browser credential only in the global script configuration, forbid
  local/manual collectors and Supabase access, and pin the exact upstream build whose
  GPC/DNT, navigation, API-only, and `credentials: omit` behavior was verified with all
  telemetry requests blocked before network delivery.

## [4.0.0] - 2026-07-29

### Changed

- Contract the Rootloom Core public Skill catalog from nine entries to four: Change,
  Review, Project Guidance, and Setup.
- Route Direct, Scoped, Governed, Evidence, and External Action work through
  `$operating-coding-change`, loading detailed References only when required.
- Move Analyzer, Baseline, Contract, Seal, Finalizer, and Runner helpers from the
  discoverable Skill tree to `plugins/rootloom/resources/evidence/` without changing
  Baseline v2–v4 or Summary revision 5 wire formats.
- Merge deterministic seeding and semantic refinement under `$project-guidance`.
- Move experimental Project Memory to the separately installed `rootloom-memory`
  plugin while preserving `rootloom-project-memory-v1`.
- Fold durable decision recording into Governed Change and remove compatibility alias
  Skills so Core discovery remains exactly four entries.

### Added

- Add the No Rootloom / Rootloom 3.4 / Rootloom 4.0 Core Reset ablation matrix,
  structural context gate, behavioral release rubric, and 3.x migration guides.

## [3.4.0] - 2026-07-16

### Changed

- Bound SessionStart additional context to 4 KiB with a dedicated compact renderer, skip Plan sessions, omit repository maps/module candidates/generic verification prose, and inject commands only when project guidance is absent.
- Keep Experimental Project Memory out of Analyzer and Finalizer assessments by default; relevant memory is read only when the caller explicitly passes `--include-project-memory`.

## [3.3.0] - 2026-07-16

### Changed

- Define the everyday product as Core Change/Review/Guidance, with Autonomy and Evidence explicitly optional and Project Memory experimental; describe the preserved 1.2.19 branch as Archived Assurance Edition.
- Expose only `skills-only`, `guidance`, and `personal` as public setup presets, rename the canonical Rules capability to `autonomy`, and retain `engineering` / `command-safety` as input-only compatibility aliases.
- Make the SessionStart project-guidance Hook read-only: it injects temporary detected context, while only an explicit `$seed-project-guidance` request may create or refresh `AGENTS.md`.
- Reduce the installed global working agreement to root-cause repair, unrelated-work preservation, risk tiers, proportional verification, opt-in deep review, and minimal authorization semantics.
- Position Personal Core as an inspectable engineering workflow rather than a verified-quality layer, and state the path-based secret-classification and independent-assurance limits explicitly.
- Move the pinned `actions/setup-node` runtime to v6.4.0 so CI no longer relies on GitHub's deprecated Node 20 action runtime.

### Fixed

- Require component Hook policy to contain exact integer `version: 1`; missing, string, zero, and future versions now fail closed.
- Keep historical Baseline v4 wire validation separate from current execution policy. Finalizer returns `reintake-required` before reviewable content capture when an old declaration no longer satisfies current policy.
- Derive `reviewability_policy.policy_provenance` from the actually validated intake chain and report final identity metadata as `captured_files_provenance: final-capture-observed`; the compatibility `source` field now uses the same honest value.
- Enforce an independent 64-file Reviewable Path ceiling instead of reusing the much larger sensitive-path budget.

### Security

- Prevent reviewability overrides for `privkey.pem`, `privatekey.pem`, `rsa-key.pem`, `ec-key.pem`, `ecdsa-key.pem`, `ed25519-key.pem`, `encryption-key.pem`, and `decryption-key.pem`.

## [3.2.0] - 2026-07-15

### Fixed

- Reject ignored and Git-index-suppressed `--reviewable-path` declarations before Intake publication and during every stable capture, normalize accepted declarations to Git's actual repository spelling, and disclose the sealed exception plus captured identity/link metadata in Summary revision 5.
- Treat `.der` as ambiguous sensitive material rather than a certificate-specific public format, and make common `key.pem`, client/server/host/SSH/identity key names non-overridable.

### Security

- Require every reviewable target to be a single-link regular non-symlink file without `assume-unchanged` or `skip-worktree` at Intake and capture time so hardlink aliases and Index-suppressed changes cannot bypass `diff.patch`.

### Compatibility

- Keep default baseline v3 and the published baseline-v4 schema unchanged. Baseline v2/v3/v4 schemas remain readable and sealable while unsafe reviewable declarations fail closed instead of silently changing v4 capture semantics. The additive `reviewability_policy` Summary field makes the aggregate release impact Minor.

## [3.1.0] - 2026-07-15

### Added

- Add Intake-only `begin_review.py --reviewable-path FILE` for an exact existing regular non-symlink file. The declaration may pin an already-reviewable template or public certificate, can downgrade ambiguous material such as a public `.pem`, is stored in opt-in `rootloom-change-baseline-v4`, is included in the sensitive-policy hash, and remains a high-risk security-domain signal.

### Changed

- Classify `.env`, `.envrc`, and non-template `.env.<name>` files as secret material while keeping `.env.example`, `.env.sample`, `.env.template`, and `.env.dist` patch-readable security configuration. Unrelated `.environment`, `.envelope`, and `.envoy` names are ordinary paths.
- Keep public certificate formats (`.crt`, `.cer`, `.der`, `.p7b`, and `.p7c`) patch-readable and high risk; private-key and keystore formats remain metadata-only, and ambiguous `.pem` stays material unless explicitly downgraded at Intake.

### Security

- Refuse reviewability exceptions for globs, directories, missing files, symlinks, case-insensitive duplicates, explicit sensitive roots, environment secrets, private keys, keystores, and other strong secret names. Finalizer has no option to add or alter reviewable paths after Intake.

### Compatibility

- Calls that do not use `--reviewable-path` continue to produce the existing baseline v3 schema. Readers, sealers, and Finalizer accept baseline v2, v3, and v4; only consumers opting into the new CLI capability must add v4 support. This additive opt-in contract is a Minor release.

## [3.0.0] - 2026-07-15

### Added

- Add finite-positive `--max-capture-seconds` to analyzer, intake, and finalizer entry points. Each stable capture uses one 90-second default monotonic deadline across both consistency passes while retaining the independent per-Git-command ceiling.
- Add stable `evidence_complete` capability output plus capture limit and duration evidence to revision-5 summaries.
- Add `rootloom-change-baseline-v3` with identity-neutral `intake-sealed` provenance while retaining baseline-v2 read/seal compatibility.

### Changed

- Split secret-material privacy classification from security-domain risk classification. Security source remains patch-readable and raises risk; secret material alone drives metadata-only capture and Sensitive Quarantine.
- Add CamelCase identifier tokenization and targeted material discovery for `clientSecret.json`, `apiToken.json`, `serviceAccountKey.json`, certificate, private-key, and keystore forms.
- Advance `rootloom-engineering-summary-v1` to revision 5 and replace identity-suggesting provenance outputs with `intake-sealed` for the baseline and `workflow-sealed` for sealed contracts/claims.
- Define public JSON/CLI SemVer governance: additive capabilities are Minor, compatible semantic corrections are Patch, and removed fields, changed enum/exit semantics, or incompatible reinterpretations are Major.

### Fixed

- Keep ordinary security-domain source such as `src/auth/token.py`, `src/credential_store.ts`, and `internal/secret_manager.go` out of privacy redaction and dangerous-deletion confirmation while preserving high-risk verification signals.
- Detect common CamelCase secret material that targeted Git discovery previously found but the Python classifier discarded.
- Bound aggregate stable-capture time instead of resetting the full time budget for every Git child.

### Compatibility

- This is a Major release because revision-5 `evidence_provenance` enum values and the newly produced baseline format intentionally change public/persisted contracts. Existing revision-4 summaries are not rewritten, baseline v2 remains readable/sealable, and valid legacy sealed v2 intakes normalize to the new provenance names when finalized by 3.0.0. `quality_status`, quality exits, artifact names, and the 2.4.0 tag remain unchanged.

## [2.4.0] - 2026-07-15

### Added

- Add finite-positive `--max-git-seconds` and positive `--max-sensitive-paths` capture budgets to analyzer, intake, and finalizer entry points; summaries record the effective limits.
- Add exact, idempotent `seal_contract.py --recover` support for matching interrupted contract/seal publication.

### Changed

- Advance `rootloom-engineering-summary-v1` to revision 4: rename the complete governed state to `REVIEW_EVIDENCE_COMPLETE`, expose `semantic_review` separately, and name unsealed semantic assertions `SEMANTIC_REVIEW_ASSERTED`.
- Route every Git child through the existing controlled process-tree owner, with timeout, output ceiling, descendant cleanup, and a bounded post-exit grace for Windows Job Object accounting convergence.
- Discover tracked and ignored sensitive paths through shared case-insensitive Git pathspecs plus literal declared roots before Python reclassification, instead of enumerating every path.
- Replace recursive `TODO` substring matching with one exact Rootloom draft placeholder while continuing to reject exact legacy generated placeholders.

### Fixed

- Cap an otherwise-complete sensitive quarantine at `REVIEW_REQUIRED_WITH_REDACTIONS` and `passed: false`, so metadata-only/redacted evidence cannot return a complete review result.
- Refuse mismatched, seal-only, or not-yet-started recovery attempts without overwriting or deleting existing files.
- Keep byte-identical pre-existing untracked files out of dirty-baseline task scope while retaining conservative attribution for changed aggregate tracked patches and changed per-path untracked fingerprints.
- Apply that task partition before risk analysis and reuse it for `diff.patch`, so exact unchanged user-owned text cannot trigger task claims or enter the review patch.
- Close stdin for every bounded Git child, preventing `hash-object --stdin` from waiting on an inherited interactive pipe in unborn repositories.
- Keep deliberately overmatching pathspec candidates under a separate bounded ceiling and apply `--max-sensitive-paths` only to reclassified sensitive results.

### Compatibility

- Keep summary/artifact field and format names, advisory bundle exits, baseline/contract/manifest/seal formats, and existing CLI defaults. Exact revision-3 `VERIFIED_CHANGE` consumers must switch to `REVIEW_EVIDENCE_COMPLETE` when `schema_revision >= 4`.

## [2.3.0] - 2026-07-14

### Added

- Add three explicit authorization modes: a one-time Single action, persistent cross-task Standard permission for non-high-risk work, and task-scoped Full permission that can include high-risk steps.
- Add independent English and Chinese architecture diagrams with no release-number binding, plus rendered review fallbacks and validator-enforced language isolation.

### Changed

- Make Standard permission the reusable ordinary default across tasks while resolving each new goal's operation type and scope; keep Full permission bounded to the current task and never infer it.
- Let static command Rules classify represented routine and high-risk commands without duplicating conversational authorization prompts; catastrophic recursive deletion remains forbidden and platform controls remain authoritative.
- Make command-safety automatically include global policy so installed Rules always have the guidance that owns authorization mode and scope.
- Make README product labels and architecture surfaces evergreen instead of embedding current Personal Core or retained Assurance release numbers.

### Fixed

- Replace the stale shared architecture image that still described the former product version and local-versus-external action boundary, and stop reusing an English-only diagram in Chinese documentation.

## [2.2.2] - 2026-07-14

### Added

- Add a transactional review intake with editable draft contracts, explicit immutable sealing, strict evidence JSON, and hash binding across the baseline, manifest, final contract, and seal.

### Changed

- Require two identical bounded repository captures, unchanged HEAD/ref/index, post-verification evidence revalidation, structured sealed claims, and an explicit semantic-review assertion before strict evidence can reach `VERIFIED_CHANGE`.
- Make strict review use quality exit codes by default, retain `--strict-bundle-only` as the explicit nonblocking path, parse every verification command before execution, and conservatively attribute dirty-baseline overlap.
- Include bounded non-sensitive untracked text in risk analysis, apply segment-aware scope globs, and keep legacy evidence readable only as self-declared compatibility input.

### Fixed

- Quarantine sensitive replacements, renames, nested paths, and newly discovered ignored additions before ordinary content capture, including after verification; synthesize ignored sensitive changes into scope without reading their contents or allowing values to enter patches through simultaneously changed ordinary files.
- Reject symlink-redirection and paths inside either the worktree or resolved Git common directory for intake, baseline, seal, evidence, and bundle output; revalidate paths before publication so linked-worktree output cannot occupy Git refs or objects.
- Prevent stale summaries, mixed-time repository state, partial command execution, slash-crossing scope matches, nonexclusive intake publication, and Windows fallback misclassification from overstating review quality.

## [2.2.1] - 2026-07-14

### Fixed

- Require an operator-sealed `begin_review.py` run manifest before strict review output can claim `VERIFIED_CHANGE`; analyzer-created or after-the-fact baselines remain self-declared and produce `MECHANICALLY_VERIFIED`.
- Read and hash baseline evidence through no-follow descriptor validation before parsing, so symlinked baseline inputs are rejected before content hashing.
- Report `detached_descendant_possible: true` with `isolation: process-group-only`, avoiding an overclaim about verification process containment.
- Treat transient Windows lock-create `PermissionError` as a busy cooperative lock so concurrent Project Memory writers can retry instead of dropping an update.

## [2.2.0] - 2026-07-14

### Added

- Add opt-in `rootloom-change-baseline-v1` pre-change snapshots for strict Tier 1/2 review, including bounded ordinary-untracked fingerprints/text patches and metadata-only ignored, secret-like, user-sensitive, directory, and symlink state.
- Add `rootloom-change-contract-v1` allowed/forbidden path enforcement, root-cause alignment, verification command/claim mapping, explicit `verification_coverage`, and `quality_status`.
- Add explicit setup `install` and `upgrade` operations while retaining compatibility `apply`.

### Changed

- Stream Git status/diff and verification output through execution-time budgets; terminate controlled process trees on timeout, output overflow, or leaked descendants and record observed/retained bytes plus convergence.
- Share strict Engineering Memory schema, bounds, legacy identity, relevance, lifecycle, and no-follow descriptor reads between the CLI and analyzer. Serialize explicit writers through `.project-memory/memory.lock`.
- Treat dependency manifests/lockfiles as supply-chain inputs and split `_`, `-`, and `.` path stems for risk signals.
- Require external output directories to be absent, empty, or Rootloom-owned; distinguish `VERIFIED_CHANGE`, `NO_CHANGE`, `FAILED`, and `UNVERIFIED`; serialize non-UTF-8 paths safely.
- Make setup upgrades preserve the installed preset, record version-only updates without redundant backups, refuse post-install drift, and backup/remove pristine targets retired by a new catalog so rollback can restore them.
- Make plugin install/upgrade complete without global setup or automatic analyzer/baseline/contract/finalizer runs. The optional global policy explicitly keeps deep review out of routine Tier 0/1 work.

### Fixed

- Detect same-path untracked rewrites during verification and include bounded ordinary text additions in the review patch; hash binary/large files without treating them as text.
- Protect ignored `.env` and broader secret-like paths with metadata-only intake baselines, shared path rules, and exact dangerous-deletion confirmation without reading sensitive content.
- Separate command success, capture preservation, verification coverage, and quality status so an unrelated passing command cannot set compatibility `passed: true`.
- Enforce allowed/forbidden paths and root-cause alignment when a machine change contract is supplied; explicit `--strict` makes incomplete Tier 1/2 evidence blocking.
- Classify dependency manifests and lockfiles as supply-chain inputs and split `_`, `-`, and `.` path stems for domain signals.
- Stream Git and verification output through execution-time limits, terminate leaked/timeout/overflow process trees, and record observed versus retained bytes.
- Serialize Engineering Memory writers, share one strict schema/reader/relevance contract, and close no-follow descriptor races.
- Refuse unsafe review output reuse, distinguish `NO_CHANGE`, and serialize non-UTF-8 Git paths safely.

### Compatibility

- Keep the existing summary format name, artifact filenames, `--verify`, `--risk`, and compatibility `passed` field. Default advisory mode remains non-blocking when commands pass and capture is stable, but incomplete evidence stays `UNVERIFIED` with `passed: false`. Strict Tier 1/2 callers add `--strict`, a pre-change baseline, machine change contract, and verification claims. Pure verification requires `--allow-no-change`.

## [2.1.0] - 2026-07-14

### Added

- Add an explainable, standard-library-only change analyzer that combines task text, anticipated/current paths, Git operations, bounded tracked diff signals, active project memory, and detected repository commands into a minimum Tier, effective risk, confidence, reasons, and verification plan.
- Add risk-specific verification behaviors for authentication, persisted data/migrations, money, concurrency/state machines, infrastructure, public consumers, destructive effects, and matching historical lessons. Suggested commands are explicitly `suggested-not-executed` and never count as test evidence.
- Add relevant engineering-memory retrieval by repeatable path/query with bounded results, selection metadata, stale warnings, optional historical inclusion, deterministic entry IDs, evidence references, expiry, lifecycle status, and exact duplicate suppression.

### Changed

- Make finalizer risk automatic. Existing `--risk low|medium|high` input remains accepted and may raise, but can no longer lower, the detected floor. Add `risk_assessment` and `verification_plan` to the existing lightweight summary while retaining its prior fields and artifact names.
- Reframe Project Memory as Engineering Memory across the Skill, plugin metadata, English/Chinese README, architecture, maturity, troubleshooting, and product diagram. Memory now feeds the risk and verification decisions only when relevant.
- Advance the plugin manifest to 2.1.0 without adding a database, vector index, network service, daemon, automatic memory write, approval flow, audit chain, or multi-agent runner.

### Compatibility

- Preserve `rootloom-project-memory-v1` envelopes and accept legacy entries without ID, status, paths, evidence, or expiry. Context reads never migrate or rewrite them.
- Preserve existing `rootloom-engineering-summary-v1` fields, `diff.patch`, `test.log`, `summary.json`, and old explicit-risk finalizer calls; new assessment and planning fields are additive.

### Safety

- Bound memory collections, architecture context, result counts, tracked patch analysis, and memory matches. Refuse unsafe repository-relative memory paths and symlinked memory write boundaries; the analyzer ignores malformed, oversized, or symlinked memory with explicit warnings.
- Keep untracked contents unread, require bundle output outside the captured repository, execute only explicit no-shell `--verify` commands, bound patch/command/aggregate-log size, and retain exact dangerous-deletion plus verification-drift refusal.

## [2.0.0] - 2026-07-13

### Changed

- Reposition `main` as Rootloom Personal Core: a single-agent quality loop for risk classification, evidence, root-cause diagnosis, scoped implementation, intelligent verification, and final review summaries.
- Replace `$high-assurance-coding-change` with `$engineering-change` and its lightweight `diff.patch`, `test.log`, and `summary.json` bundle.
- Make the `personal` setup preset the default; retain `engineering` only as an alias for migration.
- Simplify setup to an ordinary local lock, pre-mutation file backups, atomic per-file writes, drift-refusing status, and explicit rollback.

### Added

- Add `$project-memory` and `.project-memory/` for reviewable architecture, known risks, decision indexes, and evidence-backed failure lessons.
- Add a lightweight dangerous-deletion guard for exact `.env`, secret, migration, and database paths.

### Removed

- Remove Human Review, Decision Pair, protected-deletion approval, strict multi-agent Runner, hardened Artifact transactions, custom-agent/profile assets, SubagentStart audit, and setup recovery journals from `main`.
- Preserve the complete Rootloom 1.2.19 Assurance product on branch `codex/enterprise-assurance`.

### Migration

- Roll back a 1.2.19 Assurance setup with that version before installing Personal Core. Users who still need the former audited workflow should use the enterprise branch rather than expecting compatibility on `main`.

### Fixed

- Fail lightweight verification bundles when a verification command changes the tracked patch or captured path set, and re-check tracked or captured-untracked dangerous deletions after verification.
- Preserve the intentional empty capability selection installed by `skills-only` instead of falling back to the `personal` preset.
- Generate review bundles in Git repositories that have not created their first commit yet.
- Preserve Windows executable-path backslashes when parsing verification commands.
- Replace stale Assurance-oriented README imagery with the Personal Core product split and reuse the synchronized artwork in English and Chinese documentation.

## [1.2.19] - 2026-07-13

### Security

- Add typed Human Review verification outcomes: malformed or unsafe evidence is `INVALID`/9, completed current-state mismatch is `STALE`/12, and Git, permission, I/O, deadline, topology, or local resource-ceiling failures are `UNVERIFIED`/13. The verifier no longer claims staleness when observation did not complete.
- Require the exact `rootloom-human-review-result-v1` Envelope before any Decision Pair or current-state validation. Protected deletions must be nonempty, deletion-only, canonical, authorized, zero-repair, index-preserving, exactly represented by metadata records, and backed by bound metadata/Delta Artifacts plus Runner/run identity.
- Treat persisted Binding policy as production evidence only. Verification applies independent local ceilings for ignored/state paths, state bytes, per/total Artifact bytes, and time; a recorded limit above the local ceiling returns `UNVERIFIED` before recapture.
- Run verifier repository recapture with `GIT_OPTIONAL_LOCKS=0` and command-scoped `core.fsmonitor=false` / `core.untrackedCache=false`, and regression-test the complete repository, Git-control, Run Directory, index, index-lock, and repository-lock filesystem snapshot.

### Changed

- Rootloom is now version 1.2.19 and the strict high-assurance runner is version 2.24.
- Add verifier flags `--max-artifact-bytes`, `--max-total-bytes`, `--max-state-paths`, `--max-state-bytes`, `--max-ignored-paths`, and `--timeout` without allowing persisted evidence to raise them implicitly.
- Require canonical control-free reviewer/local-account fields, a null or nonnegative local UID, and canonical microsecond UTC decision timestamps from the shared producer/consumer field validator.
- Add Binding cross-field checks for repository counts and budgets, Run Directory mode 0700, exact protected-deletion cardinality, and bound Result Artifact references.
- Move shared errors, public status/resource contracts, and verifier Git environment into neutral `runner/` modules. Human Review modules no longer import `run_pipeline.py`; the public CLI injects the Runner runtime explicitly.

### Compatibility

- Binding v4 and Decision v4 remain unchanged. Older Human Review Results without Result Envelope v1 fail closed as `INVALID` and must be regenerated; they are never inferred, rewritten, or silently upgraded.

### Tests

- Add Git-unavailable, permission, deadline, temporary-I/O, topology, consumer-ceiling, real repository/protected/Artifact drift, incomplete Result, canonical Decision, schema cross-field, read-only filesystem, and dependency-direction regressions.

## [1.2.18] - 2026-07-13

### Security

- Validate the complete Human Review v4 Binding schema before any repository or reviewed-Artifact recapture: exact fields, repository/run identity, Git and Result hashes, canonical state policy and path sets, repository commitment hashes, bounded Artifact fingerprints, and protected-deletion parent commitments must be internally valid and agree with Result.
- Reserve `STALE` exclusively for structurally valid Decision Pairs whose current repository, Artifact, or protected-deletion state no longer matches. Malformed, unsafe, noncanonical, or internally inconsistent evidence is always `INVALID` with public exit 9; internal Pipeline stage exit codes no longer escape the verifier protocol.
- Preflight Terminal and Summary against their shared 1 MiB producer/consumer budget before either file is created. Reviewer and local-account identities are nonempty and limited to 4096 UTF-8 bytes.

### Changed

- Rootloom is now version 1.2.18 and the strict high-assurance runner is version 2.23.
- Keep verify stdout machine-stable as exactly `VALID`, `INVALID`, or `STALE`, while emitting one bounded reason on stderr for invalid or stale evidence. Diagnostics never serialize Artifact bytes.
- Canonicalize Human Review sensitive-path policy as a unique sorted list. Persisted v4 fields and meanings remain unchanged; manually edited or noncanonical v4 evidence fails closed and must be rerun.
- Split Human Review composition into `human_review/schema.py`, `binding.py`, `pinned_io.py`, `decision.py`, and `verify.py`; `review_decision.py` is now the thin public CLI and compatibility export surface.

### Tests

- Add `INVALID`/9 regressions for malformed metadata floors, sensitive paths, protected deletions, Run Directory identity, repository commitments, Artifact maps, protected commitments, Result hashes, and Binding field sets, including proof that invalid schema never starts repository recapture.
- Add exact/over-limit Decision Pair byte tests, overlong reviewer/local-account refusal before file creation, Summary preflight, immediate successful-pair verification, diagnostic stderr, and retained real-drift `STALE`/12 coverage.

## [1.2.17] - 2026-07-13

### Security

- Re-hash the exact Terminal and Summary payloads through their pinned descriptors at the final Human Review v4 commit gate. Canonical name, inode, single-link status, mode, exact byte count, size, and SHA-256 must all still match; any failure compensates both original files to empty and returns nonzero.
- Add a bounded, no-follow, regular-single-link Decision Pair reader and a read-only `review_decision.py verify` command. Verification checks the Result binding, canonical Terminal/Summary agreement, Terminal content hash, repository/protected-deletion commitment, and Run Directory identity without acquiring or writing the repository lock.

### Added

- Report `VALID` with exit 0 for a current valid pair, `INVALID` with exit 9 for malformed or internally inconsistent evidence, and `STALE` with exit 12 when valid recorded evidence no longer matches the repository state.

### Changed

- Rootloom is now version 1.2.17 and the strict high-assurance runner is version 2.22.
- Human Review remains format v4 because the persisted fields and their meaning are unchanged. Its local security scope is now frozen as attributable final review for trusted personal or small-team environments; hostile local approval requires an external immutable execution, signing, or audit boundary.
- Describe the shared filesystem lock as a hardened cooperative lock. It rejects indirect or multi-linked lock paths but is not an irreplaceable lease: a same-UID process can rename/unlink the locked inode and create a replacement path.

### Tests

- Add equal-length, same-inode Terminal, Summary, and simultaneous pair overwrites, proving final rejection, two-file compensation, and successful retry.
- Add read-only verifier coverage for valid unchanged evidence, coherent-but-wrong binding, multi-linked Terminal, malformed pair content, and stale repository state.

## [1.2.16] - 2026-07-13

### Security

- Require canonical `result.json` and every reviewed Artifact name to keep identifying the exact regular single-link descriptor before and after its bounded read. Stable descriptor metadata alone can no longer authorize bytes after a directory-entry replacement.
- Commit the exact reviewed Artifact name set before and after hashing, rejecting additions, removals, or renames during Binding instead of accepting a one-sided directory enumeration.
- Make Terminal and Summary one compensating pinned-descriptor transaction under a pinned Run Directory. A decision commits only after both outputs are durable and a final Result, repository commitment, Run Directory, Terminal, and Summary identity check passes; any earlier failure truncates both pinned originals to an unambiguous retryable empty state.
- Prevent descriptor-cleanup errors after that final commit point from converting a durable two-output decision into a reported failure; cleanup cannot reopen or mutate either path.

### Changed

- Rootloom is now version 1.2.16 and the strict high-assurance runner is version 2.21.
- Human Review remains format v4 because the persisted evidence and interpretation are unchanged. Existing valid v4 Results need no migration; older non-empty Terminal-without-Summary states remain fail closed rather than being inferred or rewritten.

### Tests

- Add real Result, Artifact, Terminal, and Run Directory rename/replacement regressions, including filesystems whose opened-descriptor metadata appears stable.
- Add Artifact name-set drift, Summary hardlink victim preservation, forced Summary-write compensation, retry-after-compensation, and final two-output validation coverage.
- Add a post-commit descriptor-close fault injection so cleanup cannot recreate the Terminal-without-reported-success ambiguity.

## [1.2.15] - 2026-07-13

### Security

- Treat `human-review.ndjson` creation, append, validation, and compensation as one pinned descriptor transaction. The terminal file is opened relative to the stable Run Directory, must remain a regular single-link inode at its original name, and is never reopened for rollback, so prepared hardlinks and create-to-append or compensation-time path replacement cannot write, chmod, or truncate an external victim.
- Carry the final repository-contract state into initial Human Review v4 Binding. Its complete metadata-only floor is applied before content fingerprinting and its canonical repository commitment must match the recapture, so a non-cooperative writer cannot make the Binding absorb a post-validation state or read a newly declassified protected file.
- Enforce Human Review Artifact bytes at the descriptor read source. Each observed chunk immediately consumes the file's per-Artifact and remaining aggregate allowance, and the first excess byte fails without reading to EOF.

### Changed

- Rootloom is now version 1.2.15 and the strict high-assurance runner is version 2.20.
- Human Review remains format v4; existing valid v4 Results need no migration because the stored metadata floor and repository commitment already contain the required evidence. Versions 2 and 3 remain fail closed.

### Tests

- Add terminal-decision hardlink victim, create-to-append replacement, and compensation-time replacement regressions with content and mode preservation.
- Add final-contract-to-initial-Binding declassification/commitment drift coverage and an observed-byte growth regression that stops on the first byte beyond budget.

## [1.2.14] - 2026-07-13

### Security

- Route Setup, project-guidance, and Strict Runner repository locks through one shared hardened opener. POSIX uses parent-relative `O_NOFOLLOW` descriptors and Windows uses reparse-point-aware handles; both reject non-regular, multi-linked, replaced, or indirect lock paths and acquire the lock before truncating or writing owner data.
- Advance Human Review to v4. Revalidation carries the complete final metadata-only floor into every repository capture, so a changed ignore or sensitivity rule cannot make formerly protected content readable before drift rejection.
- Bind the canonical run-directory path and stable directory identity, require Result's `run_dir` to match the supplied directory, and safely re-read the complete canonical Result through no-follow directory-relative descriptors after writing and after recomputing the decision binding. Any mismatch compensates the terminal record.
- Bound Human Review Artifact hashing by per-file bytes, aggregate bytes, fixed Artifact count, and a wall-clock binding deadline. Result itself has a bounded safe reader and a pre-write document-size gate.

### Changed

- Rootloom is now version 1.2.14 and the strict high-assurance runner is version 2.19.
- Human Review binding and decision records advance to version 4. Existing v2/v3 results fail closed and require a new run or an explicitly external review process.
- Preserve the documented isolation-launcher boundary: stable pre-spawn identity checks still do not eliminate the final path-to-`exec` race or attest launcher semantics; stronger containment remains an external supervisor/container responsibility.

### Tests

- Add shared-lock symlink, hardlink, symlinked-parent, contention, Setup, Guidance, and Runner victim-preservation regressions, including portable Windows execution.
- Add copied-run rejection, complete Result reread compensation, metadata-floor declassification, Human Review Artifact per-file/aggregate/deadline limits, bounded Result hardlink refusal, and v3 compatibility refusal coverage.

## [1.2.13] - 2026-07-13

### Security

- Replace Human Review v2's HEAD/status-only repository check with a v3 canonical commitment over bounded visible content fingerprints, metadata-only fingerprints, the Git index, Git control state, and status/path sets. Every authorized protected deletion also carries an exact-missing assertion and stable lexical parent-boundary fingerprints, so recreating an ignored target refuses a decision.
- Serialize accept/reject under the Strict Runner repository lock, re-read Result in the lock, recheck state after appending the terminal decision, and compensate the just-written record if a non-cooperative writer changes repository state during that interval.
- Reject isolation launchers inside the target repository or Artifact run root, capture their configured identity through a stable no-follow descriptor, and repeat the same identity check immediately before every model-stage and deterministic-verification spawn. Command records distinguish configured identity from actual pre-spawn identity.
- Transfer ownership to `run_managed()` cleanup immediately after `Popen`, including selector construction, nonblocking setup, and registration failures. Directory fingerprints are now metadata-only, and verification entrypoints fail closed when they resolve to a directory instead of invoking unbounded nested Git commands.
- Version Setup Recovery target schemas independently of the current plugin catalog. New Manifests record producer version, recovery schema, and target type; the reader preserves the implicit 1.2.12 schema so a future target removal or rename cannot orphan an interrupted transaction.

### Changed

- Rootloom is now version 1.2.13 and the strict high-assurance runner is version 2.18.
- Name the canonical launcher-presence gate `--require-isolation-launcher`; retain `--require-isolation` as a compatibility alias so the option no longer implies Rootloom attests isolation semantics.
- Split canonical Runner state commitments and stable process identity into `scripts/runner/`, and split Setup transaction writes and versioned recovery schemas into `scripts/setup/`, leaving the CLI files responsible for orchestration and compatibility wrappers.
- Human Review binding/decision records advance to version 3. Existing version-2 review results fail closed and must be rerun or handled through an explicitly external review process; they are never silently upgraded from evidence they did not capture.

### Tests

- Add ignored protected-target recreation, repository-lock contention, post-write drift compensation, in-repository/run-root launcher rejection, per-spawn launcher drift, selector-initialization cleanup, metadata-only directory fingerprint, and historical Recovery target-schema regressions.

## [1.2.12] - 2026-07-13

### Security

- Fail closed with Runner exit 125 whenever a managed command reaches the output-drain deadline or leaves an original process group, while retaining the direct process status separately for audit. Evidence, Diagnosis, Implementation, Review, and deterministic verification now share this owning-boundary result, so a detached child cannot preserve automatic PASS by returning 0 before a delayed mutation.
- Complete every streamed Artifact write across valid short writes, reject zero/invalid progress, verify actual file-size growth, and compensate partial verification-NDJSON appends on one pinned no-follow regular-file descriptor.
- Roll back the complete ordinary-untracked patch batch when any per-file capture fails instead of retaining patches from earlier files in the failed batch.
- Bound repository-topology/allowed-path traversal, visible path manifests, Git status/index/control output, task/role input, and model structured JSON before downstream materialization; reuse content hashes only when stable file identity metadata matches inside the locked run.
- Add a fingerprinted isolation-launcher interface with a required-mode preflight, drift-bound Human Review decisions, and phase-journaled setup orphan recovery.
- Journal rollback before its first mutation and bind every recovery Journal to its complete Manifest. Recovery and ordinary v2 rollback verify that binding; recovery then allowlists unique managed targets and validates all backup/state bytes, hashes, before/after modes, and current before/after state before writing.
- Bind Human Review to the canonical final Result core, hash reviewed Artifacts through stable directory-relative no-follow descriptors, create terminal records through no-follow descriptors, fsync the decision record, and atomically replace the reconstructable summary without following a destination symlink.
- Enter the existing `msvcrt` lock branches on native Windows without calling the unavailable POSIX-only `os.fchmod`; POSIX platforms still harden lock descriptors to mode `0600`.
- Scope exact before/after mode-drift contracts to POSIX filesystems and preserve the active LF/CRLF style while managing `config.toml`, avoiding false drift on native Windows.

### Changed

- Version verification records as `rootloom-verification-ndjson-v2` plus `rootloom-verification-summary-v2`. Records distinguish raw `command_exit_code`, lifecycle-governed `runner_exit_code`, and final persisted `exit_code` when Artifact truncation forces output-limit failure.
- Rootloom is now version 1.2.12 and the strict high-assurance runner is version 2.17. Reproduced defects require competing hypotheses plus contradiction evidence, GO requires a rejected alternative, and PASS requires a concrete counterexample/analog/complexity challenge. Provenance is classified as `repository` or `runtime_external`: local source records stay compact while runtime/external records machine-require their stronger attribution fields.
- Treat supplied findings as leads across review workflows: inspect an analogous path, attempt the strongest counterexample, report discovery yield, and reject mechanisms that cannot name the decision they change. This reuses existing stages instead of adding another audit Skill or agent.
- State limits and isolation metadata remain explicit contracts; Human Review binding/decision and setup recovery advance to version 2 for Result-core and Manifest-bound recovery semantics.
- Replace four implementation-specific state/output knobs with `--max-state-paths` and `--max-state-bytes`.

### Tests

- Add detached delayed-mutation, all-model-stage lifecycle rejection, successful and zero-progress short-write, complete untracked-batch rollback, raw/effective exit-code, and partial NDJSON-append compensation regressions.
- Add state-budget, digest-cache invalidation, structured-output, isolation, Human Review Result drift, apply/rollback interruption recovery, superseded-terminal-journal, Manifest/backup/mode tamper, unknown-target, no-follow terminal-file, and full-capacity Artifact regressions; expand CI contracts to Linux, macOS, and portable Windows scopes.
- Add fail-before/pass-after regressions for competing hypotheses, contradiction provenance, rejected alternatives, challenged PASS, the consolidated state limits, and content-only recovery on platforms without exact POSIX modes. The release suite contains 51 repository tests and 82 focused Runner tests.
- Exercise portable setup, guidance, and Hook contracts on Windows CI so platform-only lock failures block publication.

## [1.2.11] - 2026-07-12

### Security

- Start original process-group cleanup and the one-second output drain as soon as the direct parent exits with stdout still open, so a quiet detached descriptor holder cannot consume the remaining stage timeout or repository-lock lease.
- Stream staged, unstaged, `HEAD`-to-worktree, and ordinary-untracked binary patches into bounded private artifacts. Complete Delta capture now fails closed before Review when the 32 MiB aggregate or 8 MiB untracked-patch default is exceeded.
- Govern deterministic-verification persistence by actual serialized NDJSON bytes with a 64 MiB default, including explicit UTF-8, JSON-record, and cumulative artifact byte accounting.
- Apply one shared stage deadline and the parent-exit drain to each complete Runner-owned Git capture, disable repository textconv drivers, restore partial artifacts after every capture failure, and keep only fixed-size patch excerpts in model-facing memory.
- Count JSON string escape bytes before materializing verification records and preflight the worst-case minimum record before executing each command, preventing rejected serialization expansion and unrecorded command execution.

### Changed

- Add `--max-delta-bytes`, `--max-untracked-patch-bytes`, and `--max-verification-artifact-bytes` as positive additive Runner controls.
- Replace repeated aggregate verification JSON rewrites with append-only NDJSON plus a small summary index, eliminating O(n²) persistence as command count grows.
- Version private verification and Delta record formats explicitly as `ndjson-v1` and `complete-patch-with-bounded-prompt-excerpt-v1`.
- Preserve the direct parent's exit code after a quiet detached child holds stdout; structured drain-cutoff and detached-descendant fields continue to expose the incomplete containment boundary.
- The Rootloom plugin is now version 1.2.11 and the strict high-assurance runner is version 2.13.

### Tests

- Add long-stage-timeout detached-pipe, Runner-owned capture timeout/drain/shared-deadline, textconv suppression, selector/write-failure compensation, streamed tracked/untracked Delta limit and excerpt, append-only NDJSON, preflight, exact JSON-byte prediction, and full-command-budget control-character expansion regressions. The focused Runner suite now contains 71 tests.

## [1.2.10] - 2026-07-12

### Security

- Replace unbounded merged-output buffering with selector-based streaming and an 8 MiB default per-command byte budget. Only a bounded tail is retained; exceeding the budget terminates the original process group and returns a stable output-limit failure.
- Bound cumulative deterministic-verification retention to 32 MiB by default, reject batches above 64 commands, and cap the model-facing verification summary at 120,000 characters.
- Run deterministic verification with a minimal environment allowlist instead of inheriting every host variable. Additional existing variables require repeatable explicit `--verify-env NAME` authorization, and artifacts record names only.

### Changed

- Add `--max-command-output-bytes` and structured managed-command fields for observed/retained bytes, truncation, output-limit failure, drain cutoff, and detached-descendant risk.
- Add `--max-verification-output-bytes`, persist structured `*-command.json` sidecars for model stages, and propagate batch-budget state into repair and Review prompts.
- Improve stage and verification timeout diagnostics so they describe original process-group cleanup without implying complete descendant isolation.
- Clean the original process group on exceptional exits even when its direct parent has already exited.
- The strict high-assurance runner is now version 2.12.

### Tests

- Add real log-storm termination, bounded-tail, stdin/stdout streaming, minimal-environment, explicit environment opt-in, post-parent-exit interruption cleanup, verification-batch budgeting, command-count and prompt bounding, model-stage sidecars, compact Reviewer-state propagation, and structured detached-drain regressions. The focused Runner suite now contains 57 tests.

## [1.2.9] - 2026-07-12

### Security

- Bound the final managed-command output drain after process-group cleanup. A detached descendant that retains the inherited stdout pipe can no longer hold the Runner or repository lock indefinitely; local capture closes at the deadline and the command remains a timeout failure.

### Changed

- Document that POSIX process-group cleanup cannot terminate descendants that create a new session or otherwise escape the original group. Hostile verification commands still require container, cgroup, or equivalent job isolation.
- The strict high-assurance runner is now version 2.11.

### Tests

- Added a real detached-child regression that starts a new session, retains stdout, and proves the Runner returns within a fixed upper bound with an explicit fail-closed diagnostic.

## [1.2.8] - 2026-07-12

### Security

- Preserve every baseline ignored or sensitive-untracked path as metadata-only for the complete high-assurance run. Changes to `.gitignore`, `.git/info/exclude`, or current sensitivity classification can no longer make protected content readable or patchable in later snapshots.
- Reject attempts to declassify an existing baseline-protected path even when its metadata did not otherwise change.
- Poll managed process groups directly during cleanup and escalate from SIGTERM to SIGKILL when descendants remain, including children that ignore SIGTERM after the direct parent exits.

### Changed

- Repository state now records the effective monotonic `metadata_only_paths` boundary, and standalone contract enforcement derives that boundary from its baseline automatically.
- The strict high-assurance runner is now version 2.10.

### Tests

- Added regressions for protected-path declassification through `.gitignore` and `.git/info/exclude`, pre-delta content-read prevention, SIGTERM-ignoring descendant cleanup, and direct timed-out processes that ignore SIGTERM.

## [1.2.7] - 2026-07-12

### Security

- Route every verification-entrypoint content fingerprint through the repository state's ignored and sensitive-untracked classification. Protected harnesses and protected symlink targets now fail before content reads or hashes.
- Validate every verification command immediately before execution and recheck repository state immediately after it, preventing one verification command from mutating a later command's harness before that later command runs.
- Inspect and record symlinks in every entrypoint path component, not only a final symlink.
- Clean up surviving process-group children after both successful and failed commands. Failed commands retain their original exit code and record that leftover children were terminated.

### Changed

- `--bind-verification-path` is now a command-scoped stability dependency. Use `verify-N:path` when multiple user verification commands are configured; the path-only form remains accepted for one user command.
- Operator-bound harnesses and directly executed repository scripts must resolve to existing repository-internal regular files. Missing paths, directories, and protected paths fail closed.
- Pytest positional paths are treated as test selectors, including missing regression-test paths that the Writer is expected to create.

### Tests

- Added regression coverage for ignored and sensitive harness read prevention, protected symlink targets, invalid and ambiguous explicit bindings, missing pytest selectors, parent-directory symlinks, failed-command child cleanup, and verification-batch mutation.

## [1.2.6] - 2026-07-12

### Security

- Include missing common verification entrypoint candidates in the baseline, so writer-created `GNUmakefile`, `makefile`, `pytest.ini`, and related files are treated as verification entrypoint drift.
- Expand verification entrypoint discovery for `./path`, `python -m pytest`, `uv run pytest`, `poetry run pytest`, `make -f`, `pytest -c`, `npm --prefix`, and explicit repeatable `--bind-verification-path` harnesses.
- Bind repository-internal symlink entrypoints to their resolved chain and final target content, not only the symlink target string.
- Fail closed when a successfully returned managed command leaves a live process group; leftover children are terminated.

### Changed

- Directory selectors such as `pytest tests/unit` are no longer treated as verification entrypoints, reducing false positives from broad directory fingerprints.

### Tests

- Added regression coverage for missing candidate creation, wrapper command discovery, explicit harness binding, symlink target mutation, directory selector exclusion, and successful-stage leftover child cleanup.

## [1.2.5] - 2026-07-12

### Security

- Bind detected verification entrypoints across the write stage. Explicit repository-relative verification path tokens, `make` files, JavaScript package manifests, and pytest configuration files are fingerprinted before the writer and must remain unchanged before deterministic verification runs.
- Re-run allowed-path and verification-command symlink checks after every writer or repair writer, before verification executes.
- Reject protected deletion mode when `--allow-dirty` is enabled or repair cycles are configured; deletion-only runs now require a clean baseline and `--max-repair-cycles 0`.

### Changed

- Clarify that verification command path detection covers explicit/common entrypoints and is not a generic shell or CLI semantic parser.

### Tests

- Added regression coverage for writer-created verification symlink replacement, writer-modified Makefile/package/pytest harness files, and protected deletion runtime option rejection.

## [1.2.4] - 2026-07-12

### Security

- Tightened `--allow-protected-path-delete` into a deletion-only run contract. If any protected deletion is authorized, the net repository change must be exactly the approved protected deletion set; ordinary code edits, visible untracked creations, renames, or moves must happen in a separate run.
- Added pre-writer protected deletion validation. Authorized deletion paths must exist in the baseline, be classified as protected, be non-directory exact targets, and be included in the diagnosis `allowed_paths` before the implementation stage can run.
- Reject allowed-path and repository-relative verification command entries that cross an existing symlink outside the repository.
- Recheck unsupported repository topology immediately after deterministic verification, in addition to startup, writer, and final review checkpoints.

### Tests

- Added regression coverage for protected `.env` rename into an ordinary allowed path, invalid deletion authorization preflight, out-of-repository symlink boundaries, and the Runner 2.6 contract.

## [1.2.3] - 2026-07-12

### Security

- Reject automated acceptance after detecting writer creation, modification, or deletion of ignored and sensitive visible-untracked paths, before Delta capture and even when the diagnosis `allowed_paths` includes them. This post-write gate does not claim OS-level prevention or rollback.
- Add a narrow repeatable `--allow-protected-path-delete <exact-path>` exception. It accepts only deletion of an existing baseline protected path, rejects globs/directories and unused authorizations, never reads the former content, and cannot receive automated PASS.
- Successful verification and review of an authorized protected deletion now produce `HUMAN_REVIEW_REQUIRED` with a stable nonzero exit and explicit `protected_deletions` result data.

### Changed

- Recheck unsupported gitlinks, submodules, and nested repositories after every implementation/repair writer and again after final review before acceptance, while keeping redundant topology scans disabled for read-only stage snapshots.
- Rename “user-supplied behavior command” to the accurate “user-supplied verification command”; command execution linkage still does not prove test semantics.

### Tests

- Added protected ignored/sensitive modification and creation rejection, capture-before-failure, exact/unused deletion authorization, human-review outcome, and post-start topology checkpoint coverage.

## [1.2.2] - 2026-07-12

### Security

- Classify known and caller-configured sensitive visible-untracked paths before repository-state fingerprinting, so their contents are never opened or hashed and their redacted metadata never contains `sha256`.
- Expanded known secret-like coverage for npm, PyPI, netrc, Git credential, Docker, Kubernetes, auth, and service-account files.
- Added repeatable exact/recursive `--sensitive-path` rules and opt-in `--redact-untracked-dotfiles` protection for repository-specific cases.

### Changed

- Delta and baseline untracked manifests now derive from the already classified repository state instead of re-enumerating and re-fingerprinting files.
- Repository-topology traversal runs once at strict-runner startup rather than at every stage snapshot; full incremental tracked-file fingerprinting remains planned work.
- A GO diagnosis must map at least one verification requirement to a user-supplied command instead of relying exclusively on the built-in `git diff --check` command.
- Reconciled the published 1.2.1 ExecPlan with its actual tag, Release, authorization, and successful CI result.

### Tests

- Added fail-on-read sensitive-file regression coverage, metadata-shape assertions that reject content hashes, known/custom/dotfile matcher coverage, ordinary-untracked negative coverage, and behavior-command mapping enforcement.

## [1.2.1] - 2026-07-12

### Security

- Prevented ignored files and sensitive visible-untracked paths such as `.env*`, private keys, credentials, secrets, and tokens from entering content hashes, Git patches, runner artifacts, or reviewer Delta prompts. These paths are represented only by path, type, and filesystem metadata.
- Moved the allowed-path and Git-state gates ahead of Delta capture, so rejected out-of-contract changes are not read into content-bearing artifacts first.

### Added

- Added a fail-closed ignored-path enumeration budget, configurable with `--max-ignored-paths` and defaulting to 50,000 paths.
- Linked each diagnosis verification requirement to stable machine command IDs and require every mapped command to have an observed successful result.
- Added explicit strict-runner platform gating for Linux, macOS, and WSL; native Windows is not supported by this runner.

### Changed

- Clarified that native role/model routing is installed but not attested on the currently verified spawn surface, the cumulative child budget is behavioral rather than preventive, Rules are argv-prefix defense in depth, and compatibility smoke tests integration shape without live model calls.
- Added regression coverage for ignored-content non-disclosure, scope-before-capture, sensitive untracked redaction, ignored-path budgets, platform gates, and verification-command coverage.

## [1.2.0] - 2026-07-12

### Added

- Added `$record-engineering-decision` and a concise repository-owned decision template for durable architecture, contract, dependency, security, data, and operational choices.
- Added evidence-provenance and invariant-derived verification contracts across ordinary, governed, review, and high-assurance workflows.
- Added bilingual maturity and guarantee boundaries that distinguish deterministic process mechanics from factual or outcome correctness.
- Added a non-blocking scheduled compatibility probe against the latest Codex CLI while retaining the pinned required baseline.

### Changed

- The strict runner now requires every observed fact and reproduction to reference stable provenance IDs, plus a three-part verification map before a GO diagnosis.
- The strict runner content-hashes deliverable tracked/untracked files while using metadata fingerprints for ignored cache/build files.
- Setup now serializes operations with a cross-process lock, prepares recovery state before mutation, compensates apply and rollback state-commit failures, and restores original file modes.
- Project guidance seeding now excludes symlinked/out-of-repository evidence and protects writes with a Git-common-dir lock plus an exact pre-write snapshot check.
- Pinned and latest Codex compatibility jobs now exercise the full offline plugin lifecycle rather than only command-policy parsing.
- Security response windows are documented as single-maintainer, best-effort targets rather than service-level guarantees.

## [1.1.0] - 2026-07-12

### Added

- Unified task intake around Tier 0 Direct, Tier 1 Scoped, and Tier 2 Governed work without adding another always-on routing Skill.
- Added a Software 3.0 completeness gate, progressive context rules, tier-aware user-facing task packets, and explicit root-cause-alignment review.
- Added deterministic repository validation for the shared tier vocabulary and false-fix prevention contracts.

### Changed

- Behavioral defects now default to Tier 1 or higher, while trivial mechanical work remains bureaucracy-free.
- Ordinary, high-risk, review, and high-assurance Skills now distinguish evidence-backed root-cause fixes from transparent mitigations.

## [1.0.1] - 2026-07-11

### Changed

- Replaced the diagram-like plugin icon with a minimal woven `R` monogram that remains legible at small sizes.
- Simplified the light and dark wordmarks and documented the separation between the compact icon and extended brand narrative.

## [1.0.0] - 2026-07-11

### Added

- Five selectable capability levels: `skills-only`, `guidance`, `engineering`, `delegated`, and `full`.
- A polished, installable global `AGENTS.md`, deterministic project-guidance seeding, and semantic guidance refinement.
- Plan/apply/status/rollback setup with dependency closure, atomic writes, conflict refusal, backups, hash-aware rollback, and semantic config preservation.
- Ordinary coding, review-only, high-risk, and opt-in high-assurance workflow Skills.
- Four model-routed custom Agent templates, a quality-first profile, and tested command Rules that distinguish local commits from remote publication and destructive operations.
- Independently gated `SessionStart` and advisory `SubagentStart` Hooks, disabled by default until setup applies the corresponding capability.
- A deterministic high-assurance `codex exec` runner with one writer, exact scope gates, structured outputs, real verification, independent review, and a bounded repair cycle.
- Bilingual documentation, architecture and capability visuals, tests, CI, security policy, contribution guidance, and release governance.

[Unreleased]: https://github.com/liyanqing90/rootloom/compare/v4.2.1...HEAD
[4.2.1]: https://github.com/liyanqing90/rootloom/compare/v4.2.0...v4.2.1
[4.2.0]: https://github.com/liyanqing90/rootloom/compare/v4.1.0...v4.2.0
[4.1.0]: https://github.com/liyanqing90/rootloom/compare/v4.0.0...v4.1.0
[4.0.0]: https://github.com/liyanqing90/rootloom/compare/v3.4.0...v4.0.0
[3.4.0]: https://github.com/liyanqing90/rootloom/compare/v3.3.0...v3.4.0
[3.3.0]: https://github.com/liyanqing90/rootloom/compare/v3.2.0...v3.3.0
[3.2.0]: https://github.com/liyanqing90/rootloom/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/liyanqing90/rootloom/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/liyanqing90/rootloom/compare/v2.4.0...v3.0.0
[2.4.0]: https://github.com/liyanqing90/rootloom/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/liyanqing90/rootloom/compare/v2.2.2...v2.3.0
[2.2.2]: https://github.com/liyanqing90/rootloom/compare/v2.2.1...v2.2.2
[2.2.1]: https://github.com/liyanqing90/rootloom/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/liyanqing90/rootloom/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/liyanqing90/rootloom/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/liyanqing90/rootloom/compare/v1.2.19...v2.0.0
[1.2.11]: https://github.com/liyanqing90/rootloom/compare/v1.2.10...v1.2.11
[1.2.10]: https://github.com/liyanqing90/rootloom/compare/v1.2.9...v1.2.10
[1.2.9]: https://github.com/liyanqing90/rootloom/compare/v1.2.8...v1.2.9
[1.2.8]: https://github.com/liyanqing90/rootloom/compare/v1.2.7...v1.2.8
[1.2.7]: https://github.com/liyanqing90/rootloom/compare/v1.2.6...v1.2.7
[1.2.6]: https://github.com/liyanqing90/rootloom/compare/v1.2.5...v1.2.6
[1.2.5]: https://github.com/liyanqing90/rootloom/compare/v1.2.4...v1.2.5
[1.2.4]: https://github.com/liyanqing90/rootloom/compare/v1.2.3...v1.2.4
[1.2.3]: https://github.com/liyanqing90/rootloom/compare/v1.2.2...v1.2.3
[1.2.2]: https://github.com/liyanqing90/rootloom/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/liyanqing90/rootloom/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/liyanqing90/rootloom/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/liyanqing90/rootloom/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/liyanqing90/rootloom/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/liyanqing90/rootloom/releases/tag/v1.0.0
