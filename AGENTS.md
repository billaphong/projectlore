# AGENTS.md — ProjectLore

Repository-wide instructions for coding agents working on ProjectLore.

## Start and recovery

1. Read this file, `README.md`, and `docs/architecture.md`.
2. Run `git status --short --branch`.
3. Preserve pre-existing edits and untracked files unless the user explicitly
   places them in scope.
4. Inspect the relevant schema and examples before changing model semantics.

## Product language

- **ProjectLore** is the product and repository name.
- A **project knowledge model** is the complete model served for a project.
- A **domain model** is a focused portion of a project knowledge model.
- A **domain map** is a view or projection, not the canonical source.
- Do not use **ontology** in user-facing product language unless discussing an
  external standard or contrasting terminology.

## Architectural invariants

- Git-tracked, human-readable files are the canonical source of project
  knowledge.
- Human-authored ProjectLore YAML is canonical project knowledge. Strict
  Pydantic models are the executable structural contract; committed generated
  JSON Schema is the portable structural contract; semantic validation owns
  whole-model identity, reference, provenance, authority, and version checks.
- Generated databases, indexes, graphs, and embeddings are disposable views.
  Never make them the sole source of knowledge.
- Every asserted concept and relationship must support provenance.
- Keep domain semantics separate from code-graph structure. ProjectLore may
  link to code symbols, but it does not replace a code graph.
- MCP tools are read-only by default. Model mutation requires an explicit,
  reviewable workflow and must never happen silently during a read operation.
- Core behavior must not depend on one agent vendor. Claude Code and Codex CLI
  are first-class clients of the same MCP contract.
- Local model data and generated indexes must remain inside `.projectlore/`
  unless the user explicitly configures another location.

## Engineering rules

- Use Python 3.11+, complete type annotations, and small cohesive modules.
- Validate untrusted files at the boundary and return actionable errors with
  source locations when possible.
- Prefer deterministic behavior. If AI inference is introduced, distinguish
  asserted facts from inferred suggestions and retain evidence.
- In-memory operation is the default. SQLite, a network database, embeddings,
  or a hosted service require demonstrated pilot evidence and an accepted
  decision.
- Keep public tool names stable and snake_case.
- Never commit secrets, local indexes, virtual environments, or generated
  caches.
- Add or update tests when behavior changes. Do not weaken tests to obtain a
  pass.

## Initial MCP contract

The intended read-only tool surface is:

- `ontology_status` will be renamed before public release; do not add it.
- `model_status`
- `model_search`
- `model_get_concept`
- `model_resolve_term`
- `model_get_relationships`
- `model_validate`
- `context_for_task`
- `policy_check`

Tool responses must include provenance and distinguish missing information from
an empty result.

## Verification and handoff

- Run the smallest relevant tests while iterating, then the complete local test
  suite for the affected package.
- Validate all checked-in examples when schema behavior changes.
- Report files changed, verification performed, and unresolved design choices.
- Commit, push, publish packages, or create hosted resources only when the user
  authorizes those actions.
