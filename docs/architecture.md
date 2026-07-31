# ProjectLore architecture

## Purpose

ProjectLore is a workflow-attached project meaning and policy layer. It gives
coding agents a stable, shared understanding of a software project and evaluates
deterministic Rules at supported integration points. It complements source code,
code graphs, and work-management systems; it does not replace them.

## Sources and projections

```text
Human-authored ProjectLore YAML
        |
        v
Safe YAML loading
        |
        v
Strict Pydantic structural contracts
        |
        +--> committed generated JSON Schema
        |
        v
ProjectLore semantic validation
        |
        v
Deterministic immutable ProjectModel
        |
        +--> query and policy services
        +--> CLI and read-only MCP
        +--> optional disposable projections
```

Git-tracked ProjectLore YAML is canonical project knowledge. Strict Pydantic
models are the executable structural contract, and the committed generated JSON
Schema is the portable structural contract. Semantic validation owns cross-file
identity, references, provenance, authority, and version checks. SQLite indexes,
knowledge graphs, embeddings, generated code, and visualizations are rebuildable
projections and are not MVP dependencies.

## Model layers

1. **Vocabulary:** preferred terms, aliases, and definitions.
2. **Concepts:** the important entities and ideas in the project.
3. **Relationships:** typed connections between concepts.
4. **Rules:** normative invariants, prohibitions, obligations, conventions, and
   advisories with severity and provenance.
5. **Provenance:** evidence supporting every assertion.
6. **Implementation anchors:** optional links from concepts to repositories,
   files, revisions, and symbols.

Rule is the sole normative primitive. Suggested and inferred knowledge must
remain distinguishable from asserted project knowledge.

## Integration boundaries

- **ProjectLore:** domain meaning, terminology, Rules, provenance, and stable
  external references.
- **CodeGraph:** code symbols, calls, imports, inheritance, and dependencies.
- **Workflow providers:** optional current authorization context. The built-in
  local provider requires no account or network; Fraimed is one external adapter
  for live Decisions, Validation, attempts, and Outcomes.
- **Git:** authoritative ProjectLore model files, source code, and review history.

Integrations join these systems through stable references. They must not copy
another system's entire state into the canonical model. These ownership
boundaries cannot be demoted by project configuration.

ProjectLore core never requires a workflow provider. Policy bindings declare
`scope_requirement: none` (the default) or `workflow`. Timeless rules run
offline with no scope receipt. Only an applicable workflow-scoped rule becomes
indeterminate when current context is missing or stale. This keeps provider
failure localized instead of disabling project knowledge or unrelated policy.

### Provider-neutral workflow kernel

The canonical workflow boundary is `projectlore.workflow`. A `WorkflowTarget`
binds a provider request to the canonical project-model ID, root-relative model
entrypoint, provider, scope, and optional container. A returned
`WorkflowObservation` repeats that identity, binds the target and observed
content by digest, and states whether its assurance is operator `declared` or
externally `observed`. Configuration cannot promote declared context to
observed context. `WorkflowReceipt` additionally binds the model digest and
evaluation time so evidence cannot be replayed across models or targets.

Provider failures use stable, sanitized machine codes and bounded public
messages. Provider adapters retain their original exception only as an internal
cause and do not expose credentials, URLs, response bodies, or exception text.
The composition root deliberately supports only `local` and `fraimed`; another
provider must demonstrate the need before ProjectLore grows a plugin registry.
Frozen `0.1.x` scope payloads remain outside the kernel and cross the boundary
only through explicit compatibility adapters.

Local context is a durable operator declaration stored under `.projectlore/`.
It remains valid by content identity until explicitly replaced, cleared, or its
optional `expires_at` passes; it does not inherit network-observation age
semantics. External context is an observation and remains subject to its
configured maximum age. Local writes and clears are preview-first, digest-bound,
and atomic, and switching to local context removes an external refresh target
only during the reviewed apply operation.

### CodeGraph composition

The optional CodeGraph adapter sits behind `AdapterRegistry` and accepts only a
bounded, lookup-only client contract. It resolves Concept and Rule
implementation anchors into disposable observations carrying repository,
requested revision, observed revision, path, and symbol identity. The
observation digest is stable; its timestamp describes the lookup, not canonical
project meaning.

Dependency states are explicit: present, absent, stale, or rebuilding. A
required lookup that cannot run is indeterminate, never successful. Broken,
missing, stale, and ambiguous anchors are localized to their owners so unrelated
knowledge remains usable. ProjectLore stores no CodeGraph nodes, edges, or
topology; CodeGraph remains authoritative for its rebuildable code index.

## MCP and CLI behavior

The MCP server exposes read-only status, discovery, lookup, traversal, term
resolution, validation, task context, and policy evaluation. Reads and policy
decisions never modify canonical knowledge. Suggested edits require a separate
reviewable workflow.

The CLI exposes the same deterministic validation and status foundations for
developers, hooks, and CI. Stable diagnostic codes are the machine contract;
diagnostic prose may improve without breaking automation.

## Initial delivery sequence

1. Align the repository with strict contracts, generated JSON Schema, semantic
   validation, and accepted product language.
2. Prove a bounded Homebrew walking skeleton with three real Rules, current
   Fraimed scope resolution, both agent clients, blocking hooks, and a
   clean-checkout gate.
3. Generalize contracts and the compiler only from pilot evidence.
4. Generalize query, policy, MCP, CLI, and capability-aware client adapters.
5. Harden hook and checker trust boundaries.
6. Add repository assurance, CodeGraph resolution, and a contrasting second
   pilot.
7. Add SQLite or a dedicated UI only if measured pilot evidence earns them.

## Enforcement and trust

Policy results are `pass`, `fail`, `not_applicable`, or `indeterminate`.
ProjectLore distinguishes availability, active hooks, local passes, CI passes,
and verified protected enforcement. It never describes a bypassable local hook
or ordinary CI run as non-bypassable repository protection.

External prose and code-derived content are structured, bounded,
provenance-labelled data, not executable instructions. Executable checker
authority lives outside canonical model content.
