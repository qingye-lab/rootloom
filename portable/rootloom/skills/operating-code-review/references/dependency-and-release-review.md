# Dependency and release review

For dependencies inspect need, maintenance, security, license, transitive packages,
install scripts or binaries, runtime/bundle cost, supported platforms, manifest/lockfile
scope, and rollback. Reject broad unrelated upgrades.

For build, CI, packaging, deployment, or release changes inspect generated artifacts,
versioning, mixed-version behavior, configuration compatibility, least privilege,
dry-run/canary path, failure detection, rollback, and post-action verification. A
successful submission is not proof of resulting external state.
