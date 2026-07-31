# Standalone ProjectLore rationalization plan

Status: proposed implementation plan
Date: 2026-07-31
Target: post-`0.1.0a2` working tree, before public-alpha authorization

## Independent verification

An independent repository-aware verifier graded the plan adversarially across
correctness, completeness, sequencing, verifiability, migration safety,
provider independence, security, and feasibility.

- Draft 1: **91/100** — blocked on assurance classes, two-stage evaluation,
  mixed-result precedence, target identity binding, and release-state gating.
- Draft 2: **96/100** — prior blockers resolved; one remaining TOCTOU ambiguity
  between policy planning and evaluation.
- Final: **99/100** — no remaining issue prevents implementation. The retained
  one-point risk is execution complexity across public contracts, migrations,
  hooks, MCP, CLI, and the existing dirty working tree.

## Objective

Make ProjectLore a complete offline-first project knowledge and deterministic
policy product whose core behavior requires no Fraimed account, credential,
network, or workflow system. Workflow context remains optional and
provider-neutral. Fraimed becomes one adapter selected at a composition root,
with failures localized to rules that explicitly require workflow context.

## Non-negotiable invariants

1. Git-tracked human-readable project knowledge remains canonical.
2. Model status, validation, query, task context, and timeless policy work with
   no workflow provider.
3. A policy binding defaults to `scope_requirement: none`; only an applicable
   binding explicitly marked `workflow` or `observed_workflow` may depend on
   workflow context. `workflow` accepts a valid local declaration or external
   observation; `observed_workflow` requires a fresh external observation.
4. Missing, stale, unauthorized, or malformed provider data never becomes a
   pass and never disables unrelated knowledge or timeless rules.
5. Provider implementations never enter the compiler, model, query, or pure
   policy core. They are injected at CLI, hook, evaluation, or MCP composition
   roots.
6. Local declarations are reviewable data, not executable authority.
7. Existing `0.1.x` payloads receive an explicit compatibility path; field
   renames do not happen silently.
8. Local hooks and CI evidence never claim repository certification.

## Current evidence and constraints

- Ruff, strict mypy, the complete test suite, generated-schema check, bytecode
  compilation, `pip check`, workflow YAML parsing, package build, and
  distribution inspection pass on Windows.
- The working tree contains several uncommitted phases. It must be separated
  into coherent commits before release verification.
- CodeGraph MCP is available, but this repository has no `.codegraph/` index.
  Symbol/call-path analysis is therefore not evidence for this plan. Indexing
  remains an owner decision.
- The current provider-neutral core is partially implemented, but public
  surfaces retain Fraimed-specific names and one provider failure path can
  escape structured degradation.

## Binding decisions

| Concern | Decision |
| --- | --- |
| Context requirement | `none`, `workflow`, or `observed_workflow`. Omitted/legacy values migrate to `none`. `workflow` accepts declared or observed context; `observed_workflow` accepts only a fresh external observation. Unknown assurance is indeterminate. |
| Aggregate decision | Deterministic precedence is `fail > indeterminate > pass > not_applicable`. Every applicable binding emits its own finding; provider failure does not erase independent findings. |
| Target selection | Enforcement uses only an operator-configured provider target. Caller-supplied identities are hints that must exactly match provider, scope, container, and project binding; callers cannot select arbitrary authorization scope. |
| Identity binding | Project identity is the canonical model ID plus its canonical root-relative entrypoint; receipts additionally bind the current model digest. Observation, receipt, and gate evidence bind that identity, provider ID, scope ID, optional container ID, target-config digest, observed content digest, and relevant timestamps. Cross-project/container replay is rejected before rule evaluation. |
| Local declaration trust | Local declarations are operator-controlled disposable state and may satisfy `workflow`, never `observed_workflow`. For this release they remain Git-ignored and are not presented as a supported committed artifact. |
| Provider resolution | Pure planning occurs once, provider resolution occurs at most once, and pure evaluation occurs once. Composition roots never infer requirements by inspecting a synthetic finding. |
| Retry/cancellation | No automatic provider retry in an interactive request. Timeouts degrade structurally; cancellation and process shutdown propagate and are never converted into policy results. |

## Work sequence

### Phase 1 — Freeze and inventory the public contract

Purpose: prevent accidental compatibility decisions during refactoring.

Work:

- Inventory every serialized model and tool surface involving workflow scope:
  `ScopeSnapshot`, `ScopeReceipt`, `PolicyRequest`, `PolicyResult`, MCP
  `policy_check`, CLI `scope` and `evaluate`, lifecycle hooks, evidence files,
  JSON Schema, documentation, and example registries.
- Add contract fixtures for current `0.1.x` payloads before changing names.
- Classify each change as additive, compatible migration, or breaking.
- Decide and document version targets for the model schema, tool contract,
  scope payload, receipt payload, and source-gate evidence independently.
- Record the deliberate compatibility rule: legacy `frame_id`, `frame_title`,
  and Fraimed receipt values remain readable until the selected major contract
  removes them.
- Before implementation edits, create a local audit manifest containing the
  starting commit, `git status`, hashes for every pre-existing modified or
  untracked file, and proposed ownership/disposition. The manifest records
  state; it grants no authority to overwrite, stage, or commit user work.

Acceptance:

- A checked-in compatibility matrix names every public payload, current
  version, target version, compatibility behavior, and migration test.
- Golden fixtures prove old supported payloads either load losslessly or fail
  with a documented migration diagnostic.
- No public contract version remains unchanged by accident.
- The `scope-target/0.1.x` migration explicitly adds canonical model ID and
  root-relative model entrypoint, rejects ambiguous model discovery, and tests
  movement between repositories with different project identities.

Primary files:

- `src/projectlore/scope.py`
- `src/projectlore/policy.py`
- `src/projectlore/query.py`
- `src/projectlore/schema.py`
- `docs/versioning-and-migrations.md`
- `tests/test_portable_contracts.py`

### Phase 2 — Establish the provider-neutral workflow kernel

Purpose: make the dependency boundary mechanically enforceable.

Work:

- Replace the compatibility alias in `fraimed.py` with a canonical
  `WorkflowScopeProvider` protocol owned by `workflow.py`.
- Define provider-neutral request identity (`scope_id`, optional
  `container_id`) and observation types. Keep legacy Frame fields only in a
  versioned compatibility adapter, not in the canonical kernel.
- Define context assurance classes in the kernel: `declared` and `observed`.
  A local declaration can satisfy `workflow` but can never satisfy
  `observed_workflow`. Provider configuration cannot relabel one class as the
  other.
- Define typed failures:
  `WorkflowUnavailable`, `WorkflowTimeout`,
  `WorkflowAuthenticationRequired`, `WorkflowResponseInvalid`, and
  `WorkflowTargetMismatch`.
- Give typed failures stable codes and bounded sanitized public detail. Never
  expose authorization headers, tokens, credential-bearing URLs, arbitrary
  response bodies, or raw exception representations. Preserve causes only for
  internal diagnostics.
- Do not catch `CancelledError`, keyboard interruption, or process shutdown as
  provider unavailability.
- Add a small explicit composition-root dispatch map for `local` and `fraimed`.
  Defer a general plugin registry until another external provider demonstrates
  the need. The core receives an already-constructed provider or no provider.
- Bind each provider request and response to the operator-configured target
  identity and project. Reject caller-selected, cross-container, cross-project,
  or replayed observations before evaluation.
- Add an import-boundary test that fails if compiler, loader, models, query, or
  pure policy modules import `projectlore.fraimed` or another provider module.

Acceptance:

- Core query and pure policy tests pass with provider packages unavailable.
- Provider failures have stable machine codes and bounded safe messages.
- Static import-boundary tests prove provider directionality.
- No `Fraimed*` symbol appears in core module signatures.

Primary files:

- `src/projectlore/workflow.py`
- `src/projectlore/fraimed.py`
- `src/projectlore/policy.py`
- `src/projectlore/mcp_server.py`
- new provider-boundary tests

### Phase 3 — Define local declared-scope semantics

Purpose: make standalone workflow context useful rather than a short-lived
simulation of a network observation.

Decision to implement:

- External provider scope is an **observation** and uses age-based freshness.
- Local scope is a **declaration** and uses content identity plus optional
  explicit `expires_at`; it does not become stale merely because five minutes
  elapsed.
- Local declarations remain disposable under `.projectlore/` by default. A
  local declaration is Git-ignored for this release and ProjectLore neither
  commits it nor advertises committed declarations as supported behavior.

Work:

- Introduce distinct versioned `observed` and `declared` workflow-context
  variants with a discriminated union.
- Require provenance fields appropriate to each variant.
- Route CLI, hooks, source gate, and policy evaluation through the actual
  `LocalScopeProvider`; remove duplicate direct parsing paths.
- Make `lore scope local` preview-only by default and require `--apply` to
  write. The preview contains before/after digests and discloses removal of an
  external target; there is no interactive prompt.
- Add preview-first `lore scope clear --target-digest sha256:...`; `--apply`
  removes state only when the exact current target/context digest still matches,
  preventing preview/apply races.
- Preserve atomic writes, size limits, root confinement, and link rejection.
- Define migration as validate-old, construct-new, validate-new, atomically
  replace. Preserve the last valid state until replacement succeeds. Migration
  is idempotent; unsupported downgrade returns an actionable diagnostic rather
  than rewriting state. Test corrupt, oversized, truncated, symlinked, and
  interrupted inputs. If a backup is retained, bound it to one exact previous
  version inside `.projectlore/` and document removal.

Acceptance:

- A local declaration remains valid across wall-clock advancement unless its
  explicit expiration passes or its content becomes invalid.
- External observations become stale at their configured maximum age.
- Switching providers cannot leave a hidden target that later overwrites local
  context on SessionStart.
- Failure and interruption tests prove previous valid state survives.

Primary files:

- `src/projectlore/workflow.py`
- `src/projectlore/scope.py`
- `src/projectlore/scope_cache.py`
- `src/projectlore/scope_hook.py`
- `src/projectlore/cli.py`

### Phase 4 — Rationalize policy evaluation and degradation

Purpose: ensure scope dependence is explicit, composable, and localized.

Work:

- Introduce a first-class two-stage API. `plan_policy(facts, registry, model,
  target_identity)` returns a strict immutable `PolicyEvaluationPlan` containing
  normalized fact values, applicable binding snapshots and IDs, exact context
  requirements, model digest, registry digest, target-config digest, and a
  digest of the complete plan. `evaluate_policy(plan, resolution)` accepts no
  replacement facts or registry and rejects model/target identity drift.
  Composition roots use the plan—not inspection of a synthetic first-pass
  finding—to decide whether provider resolution is necessary.
- Define `WorkflowResolution` as a discriminated union: `valid_context`,
  `missing_context`, or `provider_failure` carrying only a sanitized typed code.
  The pure evaluator—not composition roots—converts missing/failure resolutions
  into per-binding indeterminate findings.
- Evaluate timeless bindings even when a provider is absent or broken.
- For a mixed request, return findings for timeless bindings plus an
  indeterminate finding for each workflow-dependent binding that cannot run;
  do not collapse the whole request before evaluating independent rules.
- Freeze aggregate precedence as `fail > indeterminate > pass >
  not_applicable`. Emit one stable finding per applicable binding in canonical
  binding order. Receipt association must identify which workflow findings
  consumed which context; unrelated timeless findings carry no implied scope
  claim.
- Make scope receipts optional and attach them only to findings that actually
  consumed workflow context, or document and version a result-level receipt if
  that granularity is deliberately retained.
- Load project-local declarative policy registries consistently in CLI, hook,
  source gate, and MCP.
- Reject unknown `scope_requirement` values and attempts to grant executable
  authority.
- Define the compatibility mapping explicitly: legacy or omitted requirement
  becomes `none`; existing `workflow` accepts either declared or observed
  context; `observed_workflow` is the opt-in external freshness requirement.

Acceptance:

- Truth-table tests cover timeless-only, workflow-only, mixed, missing,
  declared-versus-observed assurance, expired, timeout, authentication,
  malformed response, target mismatch, and successful local/external context.
- Plan tests prove identical facts and registry produce byte-equivalent
  `PolicyEvaluationPlan` output and provider lookup occurs at most once.
- TOCTOU tests mutate original fact dictionaries, registry files, model files,
  and target configuration after planning. Evaluation uses the immutable
  snapshot or deterministically rejects drift and requires replanning; it never
  evaluates a mixed generation.
- A failing timeless rule still fails when the provider is down.
- A passing timeless rule never becomes indeterminate solely because a
  provider is down.
- A workflow rule never passes from absent, stale, or mismatched context.
- An `observed_workflow` rule never passes from a local declaration even when
  that declaration is otherwise valid.
- Every result retains deterministic ordering and provenance.
- Provider call-count tests prove zero calls for timeless or non-applicable
  plans and exactly one call for plans that require context.

Primary files:

- `src/projectlore/policy.py`
- `src/projectlore/hook.py`
- `src/projectlore/source_gate.py`
- `src/projectlore/mcp_server.py`
- policy and integration tests

### Phase 5 — Unify CLI, MCP, hooks, evaluation, and documentation

Purpose: make the public product tell one provider-neutral story.

Work:

- Update capability metadata so MCP `policy_check` requires only `facts` and
  exposes optional context requirements and configured-target identity in its
  schema rather than a bare argument-name list.
- Replace Fraimed-shaped general CLI help with provider-neutral commands:
  `lore scope local`, `lore scope status`, `lore scope clear`, and an explicit
  `lore scope target --provider fraimed ...` compatibility route.
- Refactor `evaluation.py` so its default is offline/local; Fraimed evaluation
  requires explicit provider selection.
- Keep SessionStart refresh a no-op unless an external target is configured.
- Rename generic status fields and messages from Frame/Space terminology while
  retaining versioned compatibility output where promised by Phase 1.
- Generalize checker source labels from the fixed `fraimed` value to bounded
  workflow-provider provenance.
- Require MCP, CLI, hooks, and evaluation to match any supplied identity against
  the operator-configured target. No public request may widen the target.
- Update README, architecture, getting-started, extension SDK, compatibility,
  examples, and removal instructions.

Acceptance:

- A fresh installation can initialize, validate, query, run timeless policy,
  and use the source gate with all Fraimed variables absent.
- MCP tool schemas and documented arguments match runtime signatures exactly.
- A checked-in allow-list defines the exact adapter, pilot-history, and
  migration paths where Fraimed terminology may remain. Searching all other
  source and general product docs yields no Fraimed-specific identity.
- Claude Code and Codex configurations remain equivalent and preserve
  client-owned content.

Primary files:

- `src/projectlore/query.py`
- `src/projectlore/cli.py`
- `src/projectlore/evaluation.py`
- `src/projectlore/checker.py`
- onboarding and documentation

### Phase 6 — Provider conformance and adversarial tests

Purpose: prove optional providers cannot weaken the standalone core.

Work:

- Create a reusable provider conformance suite covering local, fake external,
  and Fraimed adapters.
- Exercise bounds, cancellation, timeout, authentication failure, malformed
  content, replay, mismatched identity, stale observations, link/path attacks,
  and attempted prompt or credential injection.
- Add cross-project, cross-container, arbitrary caller-target, stale replay,
  target-config drift, and observation replay cases.
- Assert public errors redact credentials, authorization headers,
  credential-bearing URLs, and arbitrary provider response bodies.
- Prove imports, MCP startup, and every core command work with Fraimed variables
  absent and malformed, without eager adapter construction or network calls.
- Verify safe exception translation at MCP, CLI, SessionStart, hook, and CI
  boundaries.
- Add deterministic receipt/evidence golden files and secret-redaction tests.
- Add Windows tests and Linux/macOS-compatible cases; gate platform-specific
  behavior explicitly rather than silently skipping it.

Acceptance:

- Every provider passes the same conformance contract.
- Provider outages return structured indeterminate findings and never raw
  exception groups or stack traces through public tools.
- Cancellation and shutdown propagation is tested independently at MCP, CLI,
  SessionStart hook, pre-action hook, source-gate, and evaluation boundaries.
- No test requires a real hosted credential except a separately selected live
  acceptance job. Live Fraimed acceptance is credential-gated and does not
  block standalone-core release conformance.
- Negative tests prove a provider cannot mutate canonical model files or widen
  checker execution authority.

### Phase 7 — Repository consolidation and reproducible release candidate

Purpose: turn the currently healthy dirty tree into reviewable evidence.

Work:

- Produce a reviewed diff manifest that attributes pre-existing edits and
  proposes coherent commit groups: release hardening, source-policy
  enforcement, workflow lifecycle/source gate, standalone kernel, and
  documentation/schema. Create those commits only after explicit owner
  authorization.
- Before each commit, inspect overlap with pre-existing user changes; do not
  rewrite unrelated work.
- Run full source verification after the final commit.
- Build wheel and sdist from the exact commit, inspect their allow-list, and
  run fresh offline installation without source-tree imports.
- Run the configured Windows/Linux/macOS and Python 3.11/3.13 CI matrix.
- Run dependency-vulnerability, license, and static-security scans using tools
  and exact versions from a checked-in security-tool manifest; record the exact
  invocations and machine-readable output paths.
- Retain machine-readable dependency, license, and static-security reports.
  The release gate permits no unresolved critical/high vulnerability, secret,
  unsafe-deserialization, shell-injection, or path-traversal finding; lower
  findings require documented disposition rather than blanket suppression.
- Test uninstall/removal of generated SessionStart, PreToolUse, MCP, trust, and
  disposable state entries while preserving all client-owned content.
- If the owner enables CodeGraph, index the final commit and audit provider
  boundaries and blast radius; absence of CodeGraph is not a release blocker.

Acceptance:

- Implementation-ready: source suite, schema, build, package inspection, fresh
  offline smoke, migration tests, security reports, and the proposed diff
  manifest pass without requiring staging or commits.
- Owner-gated release-candidate: clean working tree at the exact authorized
  candidate commit and all hosted CI matrix jobs pass.
- Owner-gated release-candidate: artifact hashes and embedded metadata match
  the release manifest.
- Security scan findings are resolved or explicitly owner-accepted with scope
  before release-candidate status.
- No publish, tag, Release, or hosted mutation occurs without separate owner
  authorization.

Implementation-ready acceptance ends when the source tree changes, migrations,
tests, documentation, and proposed diff/commit manifest are complete and all
local checks pass. It does not require a clean tree or commits. Release-candidate
acceptance is a later owner-gated state requiring authorization to create the
proposed commits, a clean exact commit, hosted CI, security artifacts, and
release-manifest verification.

## Commit strategy

After explicit owner authorization, the implementation should normally land in
these review units:

1. `test: freeze workflow and policy compatibility contracts`
2. `refactor: introduce provider-neutral workflow kernel`
3. `feat: add durable local declared workflow context`
4. `refactor: localize workflow-dependent policy degradation`
5. `refactor: unify provider-neutral CLI MCP and lifecycle surfaces`
6. `test: add provider conformance and adversarial coverage`
7. `docs: align standalone architecture and migration guidance`

Do not mechanically split already-interdependent dirty changes merely to match
these labels. Each commit must compile and should pass its smallest relevant
suite; the final commit must pass every release-candidate check.

## Rollback strategy

- Contract fixtures make serialization regressions visible before activation.
- Provider-neutral changes remain behind composition roots until their tests
  pass; Fraimed adapter behavior is not removed before compatibility coverage.
- Local state migration writes a new file atomically and preserves the prior
  version until validation succeeds.
- If mixed policy evaluation changes produce unexpected outcomes, revert the
  evaluator commit without reverting canonical model or source-binding data.
- Publication remains a separate owner-gated action, so implementation rollback
  never requires deleting a published artifact.

## Explicit non-goals

- Building a work tracker into ProjectLore.
- Mirroring Fraimed, GitHub, Linear, or CodeGraph state.
- Adding SQLite, embeddings, a hosted service, or a dedicated UI.
- General arbitrary-language static analysis.
- Automatically committing local workflow declarations.
- Claiming protected-branch enforcement from local or ordinary CI evidence.

## Final definition of done

ProjectLore is rationalized when a clean machine with no Fraimed configuration
can install the exact wheel, initialize a repository, validate and query its
project knowledge model, run timeless policy and source gates, optionally use a
durable local declared context, and receive honest structured degradation only
for rules that explicitly require an unavailable workflow provider. Fraimed
conformance remains tested as an optional adapter. All public contracts are
versioned, migrated, documented, reproducible from a clean commit, and verified
across the supported CI matrix.
