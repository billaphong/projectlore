# Checker and adapter extension contracts

Extensions are operator code around a canonical model, never executable authority
declared by project YAML.

## Knowledge adapters

Implement `KnowledgeAdapter` with a stable snake-case `name` and a bounded,
read-only `resolve_anchors(ProjectModel, required=False)` operation. Register an
already-constructed instance in `AdapterRegistry`. The CodeGraph reference
adapter accepts only `ReadOnlyCodeGraphClient.lookup`; it exposes no mutation
method, caps anchors and matches, localizes failure, carries repository/revision
provenance, and never mirrors graph topology.

Required dependencies must return `indeterminate` when unavailable. Optional
dependencies may return partial observations. Use the versioned
`projectlore-anchor-observation/0.1.0` and
`projectlore-anchor-resolution/0.1.0` payloads.

## Trusted checkers

Construct `TrustedChecker` entries in operator-owned runtime code and register
them in `CheckerRegistry`. Pin the executable SHA-256, fixed argument vector,
working directory, timeout, output bound, and every relevant policy file.
Canonical `checker` labels select an existing entry; they cannot create one or
alter its authority.

Execution never uses a shell, inherits only a small environment allow-list,
confines paths to the project root, bounds output, and terminates the process
group on timeout. External execution fails closed unless a trusted
`NetworkSandbox` supplies an operating-system deny-network boundary. The current
reference backend is digest-pinned bubblewrap on Linux.

Return `projectlore-checker-execution/0.1.0`. Distinguish `pass`, `fail`, and
`indeterminate`; never convert missing dependencies, sandbox failure, timeout,
or malformed output into success.

## Compatibility and tests

Extensions must support Python 3.11+, use complete type annotations, remain
vendor-neutral at the contract boundary, and include:

- success, absence, stale/dependency, timeout, malformed-output, and bound tests;
- provenance and deterministic-order assertions;
- proof that model content cannot broaden executable or mutation authority;
- proof that unrelated knowledge remains usable after localized failure.

Breaking payload or protocol changes require a new major contract version and
migration notes.
