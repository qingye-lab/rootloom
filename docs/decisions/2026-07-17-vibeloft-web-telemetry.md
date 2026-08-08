# Adopt the official VibeLoft runtime for website telemetry

Status: accepted

Date: 2026-07-17

## Context

Rootloom's public GitHub Pages site needs lightweight deployment telemetry without adding a package manager, a second JavaScript bootstrap path, a direct database dependency, or host-owned fingerprinting logic. The site is one static `index.html` document with hash navigation and no SPA router. GitHub Pages serves it from the registered production origin `https://liyanqing90.github.io/rootloom/`.

The integration changes the website's external dependency and privacy boundary. The browser credential is a revocable product-level write credential intended for the public script tag, but it must not be copied into documentation, tests, logs, or alternate collectors.

## Evidence

| Observation | Kind | Source | Date | Notes |
| --- | --- | --- | --- | --- |
| The production site has one HTML entry and no SPA router | verified fact | `index.html`, `site/main.js` | 2026-07-17 | hash anchors remain in one rendered document |
| GitHub Pages serves the registered HTTPS origin without a Content Security Policy header | verified fact | production response headers from `https://liyanqing90.github.io/rootloom/` | 2026-07-17 | HSTS is enabled; CSP changes are not applicable |
| The earlier readable runtime v0.3.0 derives page URLs from the current HTTPS location, removes query/hash data, honors GPC/DNT, uses omitted fetch credentials, owns retry/backoff, and listens to History API navigation | verified fact | `https://vibeloft.ai/telemetry/v1.js` | 2026-07-17 | upstream runtime inspected directly; no credential included in this record |
| The runtime endpoint validator accepts only the VibeLoft AWS API, with an HTTP exception limited to localhost development endpoints | verified fact | official runtime source | 2026-07-17 | Rootloom does not configure an endpoint override |
| The current published runtime is an obfuscated fixed build with SHA-256 `0901374715934a0234cda527cd95fd4d3c66c989fddd672d06c9df3f43d05bf5` | verified fact | `https://vibeloft.ai/telemetry/v1.js` | 2026-08-08 | upstream representation remains obfuscated, so readable implementation tokens are not an honest verification method |
| In an intercepted Chromium run, the reviewed build attempted only an HTTPS `POST` to the VibeLoft telemetry endpoint with omitted credentials, wrapped `pushState` and `replaceState`, and registered `popstate`; enabling GPC and DNT produced zero request attempts | verified fact | request-blocked browser inspection of the production site | 2026-07-30 | `fetch` was replaced before runtime initialization and every API route was aborted, so no telemetry event left the browser |
| The refreshed fixed build retained the same endpoint, method, `credentials: omit`, History API wrappers, and `popstate` listener; enabling GPC and DNT again produced zero request attempts | verified fact | request-blocked Chromium inspection of the registered production-origin document | 2026-08-08 | the downloaded runtime was fulfilled locally, `fetch` was replaced before initialization, and every unmatched browser route was aborted, so no telemetry event left the browser |
| VibeLoft documents registered HTTPS-origin enforcement, ordinary and SPA navigation coverage, API-only delivery, and no canvas, WebGL, audio, or font fingerprinting | verified fact | [VibeLoft trusted telemetry guide](https://vibeloft.ai/en/articles/trusted-telemetry-for-vibecoding-products/) | 2026-07-30 | primary product documentation, updated 2026-07-16 |

## Decision

`index.html` is the only initialization boundary. It loads the official deferred VibeLoft runtime exactly once with the assigned product ID and browser auth attribute. Rootloom will not install a telemetry package, wrap the runtime, emit manual page views, forge page URLs, configure an alternate endpoint, or access Supabase from the browser.

The official runtime owns its random first-party device ID, coarse environment digest, GPC/DNT handling, History API coverage, retry/backoff, and failure isolation. Rootloom host code does not read or extend those signals. Local HTTP development loads cannot become valid production events because the runtime rejects non-HTTPS product page URLs. Other HTTPS preview origins retain their real origin and depend on VibeLoft's registered-origin enforcement; Rootloom never substitutes the production URL.

There is currently no CSP in source or in the GitHub Pages response, so no directive changes are made. If a CSP is introduced later, its minimum telemetry allowances are `https://vibeloft.ai` in `script-src` and `https://api.vibeloft.ai` in `connect-src`; no other directive may be weakened for this integration.

## Alternatives rejected

- Install an npm telemetry package — rejected because the site has no package runtime and the official global script is the required integration boundary.
- Add a local telemetry wrapper or manual SPA page-view calls — rejected because it would create duplicate initialization and compete with the official runtime's navigation and privacy behavior.
- Post directly to Supabase or another collector — rejected because it would expose a broader data boundary and bypass VibeLoft's registered product and origin contract.
- Proxy events through Rootloom infrastructure — rejected because Rootloom has no website backend and does not need to own telemetry payloads.

## Consequences

- Positive: every rendered production document has one observable, testable telemetry initialization.
- Positive: host code gains no tracking implementation, database credential, alternate endpoint, or extra fingerprinting surface.
- Positive: telemetry failure remains isolated from the website because the deferred runtime catches initialization and delivery failures.
- Negative: the website now depends on a third-party script at runtime; an upstream change can alter collection behavior without a Rootloom commit.
- Negative: visitors who do not enable GPC or DNT may send page URL, a random device ID, and the documented coarse environment digest to VibeLoft.
- Operational: repository validation pins the integration location, product identity, credential digest, single occurrence, and absence of local collectors. Because the official runtime is now obfuscated, `make telemetry-check` downloads it over verified TLS and requires the exact SHA-256 of the zero-egress browser-reviewed build without executing it or emitting an event.
- Operational: an upstream digest change fails closed. Updating the digest requires a new governed, request-blocked browser review of endpoint, method, credential mode, privacy signals, and navigation hooks; a changed build is never accepted from its header comment alone.

## Verification and revisit triggers

Run `make validate`, `make test`, `make telemetry-check`, the Pages production workflow, a request-blocked live browser load, and VibeLoft Deployment Verification. Revisit this decision if the pinned runtime digest changes; if VibeLoft changes the script host, endpoint, privacy signals, payload schema, origin enforcement, device identity, or environment digest; if Rootloom adds another HTML entry or a real SPA router; or if a CSP is introduced.

Rollback is a Git revert that removes the script tag and validation contract, followed by the normal Pages deployment. Disable the VibeLoft product credential if the browser write boundary must be revoked immediately.
