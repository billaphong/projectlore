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

## Project-local declarative policy bindings

Projects may add deterministic policy semantics in the Git-reviewable
`.projectlore/policy-bindings.json` registry. The file is optional, limited to
64 KiB, parsed with a strict closed schema, and merged with the built-in
registry. Project-local entries cannot replace built-in rule IDs.

Each entry binds a canonical Rule ID to two facts (or one fact and a literal),
an `lte` or `equal` relation, a `datetime`, `decimal`, or `string` value type,
and a deterministic failure outcome and message. `scope_requirement` defaults
to `none`; use `workflow` only when the rule genuinely depends on current
authorization context:

```json
[
  {
    "rule_id": "lore:merchant-pricing/rule/discount-cap",
    "left_fact": "discount_rate",
    "relation": "lte",
    "right_fact": null,
    "right_literal": "0.30",
    "value_type": "decimal",
    "failure_outcome": "discount_cap_exceeded",
    "failure_message": "Discount exceeds the approved cap.",
    "scope_requirement": "none"
  }
]
```

This registry is data, not executable checker authority. Unknown fields are
rejected, and entries cannot specify commands, arguments, executables,
environments, working directories, or network behavior. Decimal evaluation
uses finite arbitrary-precision values rather than binary floating point.

The generic agent hook evaluates only supported structured policy requests,
including bounded `*.projectlore-policy.json` writes. It does not infer business
facts from arbitrary source-code edits.

For explicitly supported Python source, a project may add the strict
`.projectlore/source-policy-bindings.json` registry:

```json
[
  {
    "path": "pricing.py",
    "fact_name": "discount_rate",
    "selector": "mapping_item",
    "target": "DISCOUNT_RATES",
    "key": "GOLD",
    "value_syntax": "decimal_call"
  }
]
```

The adapter supports exact project-relative `.py` paths, top-level assignment
or string-keyed mapping selectors, and literal `Decimal("value")` calls. It
parses with Python's AST without importing or executing proposed source.
Configured files and proposed content are bounded, links and path escapes are
rejected, selector absence or ambiguity fails closed, and unknown registry
fields cannot add execution authority.

Both declarative registry files should be committed and reviewed. If the
repository otherwise ignores `.projectlore/`, use narrow exceptions while
keeping runtime state ignored:

```gitignore
.projectlore/*
!.projectlore/policy-bindings.json
!.projectlore/source-policy-bindings.json
```

Claude-style full-file `Write` and exact-string `Edit` inputs and Codex
`apply_patch` update/add inputs are reconstructed before evaluation. A relevant
source edit also requires an operator- or workflow-provided, fresh
`.projectlore/scope.json` containing a strict `ScopeSnapshot`; this local file
is disposable integration state, not canonical knowledge, and should remain
Git-ignored. The resulting receipt accurately reports `provided_snapshot`; the
hook does not claim that it independently queried Fraimed.

ProjectLore needs no workflow provider for bindings whose requirement is
`none`. `lore scope local ID --title TITLE` supplies optional standalone context
without an account or network. Configure the optional Fraimed identity with
`lore scope target FRAME_ID SPACE_ID`. `lore scope refresh` and the generated
Claude Code and Codex CLI SessionStart hooks use an environment-only
`FRAIMED_API_TOKEN` to refresh that snapshot through HTTPS Fraimed MCP.
Activation is atomic: a failed or invalid response cannot partially overwrite
the previous snapshot. SessionStart failure is advisory, while a later
policy-relevant edit or source gate still treats absent or stale scope as
indeterminate and fails closed.

`lore source-gate MODEL --all-configured` evaluates the configured facts from
the checked-out files through the same policy core. Use repeated
`--changed-file` arguments for an explicit subset. Its bounded, atomically
written evidence is either `local_advisory` or `ci_job_result`, always includes
provenance and a scope receipt, and always declares
`repository_certified: false`. Protected repository enforcement requires
separate hosted evidence.

This is deliberately not a general static analyzer. Unsupported languages,
computed values, arbitrary expressions, attribute calls such as
`decimal.Decimal(...)`, complex refactors, and unconfigured paths require a
separate trusted adapter or checker at the appropriate hook, commit, or CI
boundary.

## Compatibility and tests

Extensions must support Python 3.11+, use complete type annotations, remain
vendor-neutral at the contract boundary, and include:

- success, absence, stale/dependency, timeout, malformed-output, and bound tests;
- provenance and deterministic-order assertions;
- proof that model content cannot broaden executable or mutation authority;
- proof that unrelated knowledge remains usable after localized failure.

Breaking payload or protocol changes require a new major contract version and
migration notes.
