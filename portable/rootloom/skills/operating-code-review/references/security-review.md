# Security review

Check authentication versus authorization, tenant/resource ownership, default-deny
behavior, privilege transitions, input normalization, injection, unsafe deserialization,
path traversal, secret exposure, logging, cryptography usage, token/session lifetime,
CSRF/SSRF, and unintended network or external effects.

Trace both the allowed and denied path through the real boundary. Verify tests cover a
valid principal, an invalid or cross-scope principal, and failure without leaking
sensitive detail. Treat security scanners as evidence sources, not proof of absence.
