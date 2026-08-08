# Maturity, guarantees, and compatibility

Rootloom Core is an early-stage, single-maintainer product. Its goal is to make Codex
engineering behavior more deliberate and inspectable without imposing deep-review cost
on installation or routine work. The repository does not yet contain completed
comparative model evidence that it reduces defects or review time, or a third-party
security audit or fuzzing report.

Release `v2.0.0` passed the repository's Linux Python 3.11–3.14, macOS, Windows, and pinned Codex CLI contract matrix. That proves the checked mechanics on those environments, not model-level engineering quality.

## What is executable

- deterministic, network-free project-context scanning with a 4 KiB SessionStart cap, Plan-session skip, and repository writes reserved for explicit seeding;
- fail-closed Hook enablement from managed local policy with exact integer `version: 1`;
- explicit install/upgrade/status/rollback behavior for the personal setup targets, with installed-hash drift refusal;
- ordinary local lock serialization, staged recovery-journal replay, and per-file atomic replacement;
- drift-refusing backup restoration;
- all-command preflight parsing followed by no-shell execution, streaming output/time ceilings, and descendant-process cleanup shared by verification and Git capture;
- out-of-repository, ownership-marked review bundles with bounded status, patch, fingerprints, command count, and aggregate log;
- opt-in atomic no-replace pre-change baselines plus explicit draft-to-sealed strict Tier 1/2 contracts;
- two-pass stable repository capture, strict evidence JSON, segment-aware scope globs, and unchanged HEAD/ref/index binding;
- ordinary untracked content fingerprints, task-partitioned applyable bounded text patches and risk signals, with separate targeted-candidate and classified-result path ceilings, recursive metadata-observed sensitive capture, and sensitive-change quarantine;
- evidence-honest revision-4 review states that keep the operator semantic assertion separate and make redacted reviews non-passing;
- exact dangerous-path deletion confirmation;
- explainable static risk floors over task, path, tracked/non-sensitive-untracked diff, and operation;
- risk-specific verification recommendations kept separate from executed test evidence;
- separately installed, bounded, stale-aware Project Memory with locked explicit updates
  and a strict reader contract that Core does not import;
- an isolated Agent Plugins 1.0.0 preview with a closed manifest, exact Change/Review/
  Project Guidance allowlist, path containment, relative-Reference checks, deterministic
  source parity, opt-in read-only host-adapter templates, and a disposable Codex installation smoke;
- repository validation, unit tests, and an offline Codex compatibility smoke.

## What remains semantic

Rootloom does not mechanically prove:

- that collected evidence is complete or true;
- that the diagnosed root cause is correct;
- that the change contract captures every consumer;
- that chosen tests are sufficient;
- that a final review missed no defect;
- that static risk classification captures every semantic effect;
- that a suggested verification command is safe, sufficient, or has run;
- that project memory is current or correct.

Skills guide these decisions; current repository and runtime evidence must verify them.

## Personal safety boundary

The personal artifact bundle is mutable and local. Verification commands are trusted operator input, not sandboxed workloads; argv and output are retained verbatim and must not carry credentials. Capture does not cover non-sensitive ignored files, Git administrative files, external state, detached managers, or a secret copied to an ordinary path without an observable change at its sensitive source. Rootloom's privacy classifier is path-based, not a content-aware secret scanner; broader detection requires a separate trusted local scanner whose findings are redacted before they enter Rootloom evidence. The setup lock is cooperative and ordinary. Setup is atomic per file but not across the complete target set. Backup/rollback is designed for normal local mistakes, not power-loss recovery, hostile same-user races, signed approval, immutable audit, regulated retention, or multi-operator environments.

Those assurance mechanisms remain as the unmaintained Archived Assurance Edition on
`codex/enterprise-assurance`; they are not implied by Rootloom Core or presented as an
active product line.

## Compatibility

Normal CI validates Python 3.11–3.14 on Linux and portable contracts on macOS/Windows.
The pinned Codex compatibility job proves native marketplace/plugin installation has no
global-policy or review-gate side effects, then separately exercises the optional
personal setup round trip and command Rules. A separate live smoke is manual because it
requires a logged-in Codex session and a real model turn.

The Agent Plugins preview is mechanically validated against the repository's pinned
1.0.0 Working Draft contract: manifest shape, exact Skills, containment, relative
resources, and native-source synchronization. An optional disposable-Codex smoke also
proves package installation and the exact three-directory Skill surface plus
self-contained helper in the installed Codex CLI. Static and synthetic adapter checks
prove envelope equality and non-destructive failure behavior. This does not prove runtime discovery, activation, tool availability, model
behavior, installation UX, or feature parity in Cursor, VS Code, GitHub Copilot, Kiro,
or another client. Codex remains the fully exercised native runtime; cross-client
support claims require client-version-specific smoke evidence.

Cursor, VS Code, GitHub Copilot CLI, and Kiro now document direct loaders for the same
standard package; no platform manifest or Skill fork is required. Optional templates
adapt only the host lifecycle envelope. That establishes a documented structural path,
not a Rootloom runtime pass. Copilot coding-agent use also
remains unavailable as an install claim until a compatible marketplace entry is
published and exercised. No passed current-version runtime evidence for these non-Codex
hosts is checked in, so their smoke gates remain explicitly pending.

Personal Core 2.0 intentionally breaks the 1.2.19 high-assurance Skill, strict Runner CLI, custom-agent/profile setup, Human Review formats, protected-deletion approval, and recovery-journal contracts. Migrate by rolling back with 1.2.19 first.

Personal Core 2.1 keeps `rootloom-project-memory-v1` envelopes and legacy entries readable. New ID, evidence, status, path, and expiry fields are additive. The existing `rootloom-engineering-summary-v1` fields remain; `risk_assessment` and `verification_plan` are additive, and old `--risk low|medium|high` calls still work. A supplied risk can no longer lower the static detected floor.

Personal Core 2.2 retains the summary format name while revision 3 tightens explicit governed evidence. Advisory finalization remains non-blocking by default. Strict review uses a draft → seal lifecycle, stable two-pass capture, strict JSON, post-verification evidence/base revalidation, reference-aware sensitive-change quarantine, worktree plus Git-common-directory containment, unchanged HEAD/ref/index, and structured sealed claims. It defaults to quality exit codes; `--strict-bundle-only` preserves an explicit non-blocking strict bundle. `semantic_coverage: reviewed` is an operator assertion, not machine proof. Unknown semantics can reach at most `MECHANICALLY_VERIFIED`, and only sealed mechanical evidence plus that assertion yields `VERIFIED_CHANGE`/`passed: true`. Pure verification requires `--allow-no-change`, but invalid evidence and process/capture failures take priority over `NO_CHANGE`.

Summary revision 4 deliberately changes the exact highest-status value from `VERIFIED_CHANGE` to `REVIEW_EVIDENCE_COMPLETE` and exposes `semantic_review: operator-asserted` separately. An assertion without a sealed chain is `SEMANTIC_REVIEW_ASSERTED`; sensitive quarantine caps an otherwise-complete result at `REVIEW_REQUIRED_WITH_REDACTIONS` with `passed: false`. Strict quality exit zero belongs only to `REVIEW_EVIDENCE_COMPLETE`; advisory bundle exits remain non-blocking. Revision-3 exact-value consumers must branch on `schema_revision`. Git now shares the controlled process-tree owner, closed stdin, and an explicit time budget with verification; sensitive discovery uses shared targeted pathspecs with separate candidate and classified-result ceilings; dirty-baseline risk and patch output reuse the same task partition; and exact `seal_contract --recover` completes only matching interrupted publications.

Personal Core 3.0 advances the same summary format to revision 5 and changes provenance enum values from identity-suggesting `operator-sealed` to `intake-sealed` / `workflow-sealed`. New intakes produce `rootloom-change-baseline-v3`; baseline v2 remains readable and sealable. `evidence_complete` is the stable automation capability, while detailed quality statuses remain diagnostic. Secret-material privacy and security-domain source risk are now separate classifiers: security code stays patch-readable, and CamelCase material remains metadata-only. Each stable two-pass capture also has one 90-second default aggregate monotonic deadline in addition to the 30-second default per-Git ceiling. These public/persisted contract changes make 3.0 a Major release; historical revision-4 and baseline-v2 artifacts are not rewritten.

Personal Core 3.1 narrows secret-material naming without changing Summary revision 5. Environment templates and public certificate formats remain patch-readable security-domain evidence, while unrelated `.env*` names are ordinary. Default Intake output remains baseline v3. The additive Intake-only `--reviewable-path` capability emits baseline v4 only when used, seals exact declarations into the policy hash, can pin already-reviewable artifacts or downgrade ambiguous material, and refuses strong or explicitly declared secrets. Baseline v2/v3/v4 readers and sealers coexist; consumers that do not opt into the new flag receive the existing v3 contract.

Personal Core 3.2 keeps the v3/v4 wire formats but rejects ignored or Git-index-suppressed reviewable targets, hardlinks, case ambiguity, and common private-key names. DER joins PEM as ambiguous metadata-only material because either encoding may contain private keys. Summary revision 5 additively exposes the sealed reviewability policy and captured file identity metadata; under the repository's SemVer policy, that optional field makes 3.2 a Minor release.

Personal Core 3.3 batches the Core Reset while keeping those wire versions frozen. Historical Baseline readers validate structure and hashes without applying the latest reviewability classifier; Finalizer applies current policy separately and returns `reintake-required` before reading incompatible reviewable content. Reviewable declarations have a fixed 64-path ceiling, provenance distinguishes validated intake policy from final capture observation, SessionStart context is read-only, and Project Memory is explicitly experimental.

Personal Core 3.4 completes the executable boundary for dynamic context and Experimental Project Memory without changing Baseline or Summary formats. SessionStart uses a dedicated incremental renderer, caps the complete additional context at 4 KiB, and skips Plan sessions. Analyzer and Finalizer no longer infer consent from a checked-in `.project-memory/`; callers opt in with the additive `--include-project-memory` flag, while sensitive-change quarantine still prevents repository reads. Existing automation that did not rely on implicit Memory reads keeps its prior CLI and evidence contracts.

Rootloom 4.0 contracts the public Core to Change, Review, Project Guidance, and Setup.
High-risk and Evidence behavior becomes on-demand Change mode References; deterministic
Evidence helpers move to `plugins/rootloom/resources/evidence/`; Seeder and Refiner
merge under `project-guidance`; durable decision recording becomes a Governed step.
Project Memory moves to the separately installed `rootloom-memory` plugin, and Core
Analyzer/Finalizer remove `--include-project-memory`. Baseline v2–v4, Summary revision
5, contract, manifest, and seal wire formats remain unchanged. See the
[3.x migration guide](migration-4.0.md) and [Core Reset evaluation](../evals/core-reset/).

Rootloom 4.1 preserves those frozen formats and public four-Skill boundary. Its v2
evaluation harness records actual Codex token fields, exact routes, and repeated
isolated runs, but a formal behavioral acceptance still requires a reviewed
three-repetition candidate result bound to the final Core tree. The `prepare`/`finish`
Evidence orchestration is an additive ergonomic wrapper, not a new assurance state or
machine proof; its semantic-review flag remains an operator assertion. SessionStart
omits unsafe package-script names rather than rendering untrusted command-like text.
