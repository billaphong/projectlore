# ProjectLore product research and hardened plan

Status: proposed plan of record, pending owner acceptance  
Research date: 2026-07-29

## Executive decision

ProjectLore should be an **agent-neutral project meaning and policy layer attached
to the development workflow**.

It should not become:

- a second work tracker beside Fraimed;
- another code index beside CodeGraph, Augment, Greptile, or Sourcegraph;
- another spec-driven workflow beside Spec Kit or OpenSpec;
- a free-form agent memory store;
- a general ontology platform; or
- a new schema or policy programming language.

Its differentiated job is:

> Give every agent the same versioned, provenance-backed account of what the
> project means and what rules govern a change, then compile the enforceable
> subset into deterministic checks at the points where agents act.

Fraimed remains authoritative for current scope, decisions, validation, attempts,
and outcomes. Git remains authoritative for ProjectLore's project/domain model.
CodeGraph remains authoritative for derived code topology. ProjectLore links these
systems into a coherent context and enforcement contract without copying their
databases.

## Market and open-source landscape

### Code understanding and retrieval

| Product/project | What it does well | Why it does not replace ProjectLore |
|---|---|---|
| Augment Context Engine | Live semantic code/repository context, history, docs, tickets, tribal knowledge, MCP access | Retrieval and curation are primary; it does not define a Git-reviewed domain vocabulary and portable deterministic policy contract |
| Sourcegraph Deep Search / MCP | Cross-repository code search, navigation, cited agent answers | Excellent implementation context, but source-derived understanding is not an explicit project meaning model |
| Greptile | Code graph, custom rules, learned standards, PR validation, agent integrations | Closest commercial enforcement neighbor, but centered on AI code review and learned/code-derived rules rather than an open canonical semantic model |
| Swimm | Continuous documentation and code-linked understanding | Documentation freshness and modernization are primary; its knowledge is not a portable model compiled into local agent gates |
| CodeGraphContext, colbymchenry/codegraph, codebase-memory-mcp, codebase-graph | Local code graphs and MCP retrieval | They model symbols, calls, files, and dependencies—not accepted business meaning, project policy, or provenance-backed terminology |

Conclusion: ProjectLore should integrate with a code graph and never build its own
AST/call graph in the MVP.

### Domain language and knowledge modeling

| Product/project | What it does well | Gap ProjectLore can own |
|---|---|---|
| Contextive | Git-tracked bounded-context glossaries, IDE hover/completion, language-independent terms | Strong direct precedent for ubiquitous language, but limited relationship, provenance, rule, agent, and enforcement semantics |
| LinkML | Rich schema modeling and generation across JSON Schema, Python, RDF/SHACL, SQL, and docs | More metamodel/interoperability machinery than the MVP needs; no native ProjectLore agent workflow or enforcement contract |
| CUE | Unifies data, schema, and policy constraints; strong configuration validation | Compelling constraint engine, but adds another language/runtime and does not solve domain provenance, agent integration, or workflow placement |
| RDF/SHACL/JSON-LD tools | Standards-based graph interchange and constraint validation | Appropriate later for interoperability; too much authoring and runtime complexity for the first useful product |
| Neo4j context graph templates and memory graphs | Graph reasoning and agent memory | Mostly mutable or derived memory; ProjectLore is asserted, reviewed project truth |

Conclusion: use ProjectLore-owned YAML vocabulary, strict Pydantic contracts,
generated committed JSON Schema, and deterministic semantic checks. Preserve a
normalized model boundary so CUE, LinkML, or JSON-LD can be added as adapters when
real users require them.

### Specifications and workflow

| Product/project | What it does well | Boundary with ProjectLore |
|---|---|---|
| GitHub Spec Kit | Mature multi-agent spec/plan/tasks/implementation workflow, constitutions, quality gates, extensions, presets, workflows | Owns how a change is specified and executed; ProjectLore supplies the durable domain meaning and policies those workflows query and validate against |
| OpenSpec | Lightweight brownfield change proposals and spec deltas across many agents | Owns proposed/current behavior specifications; ProjectLore owns reusable project vocabulary, cross-spec relationships, policy, and anchors |
| Amazon Kiro steering/specs/hooks | Integrated agent workflow and automation | Vendor-specific workflow surface; ProjectLore must compile to multiple clients |
| Fraimed | Scope, decisions, validation, attempts, evidence, and outcomes | ProjectLore references active Fraimed context and can enforce that policy evaluation resolved current authoritative scope, but must not duplicate or supersede it |

Conclusion: ProjectLore is workflow-attached, not a workflow engine. It should
provide a small integration SDK so Spec Kit, OpenSpec, Fraimed, and custom workflows
can request context and invoke policy gates.

APC is the strongest emerging neutral packaging overlap. ProjectLore should not
compete to rename every agent configuration directory. It should keep its typed
canonical model under `projectlore/` for the MVP, emit native client projections,
and add an APC projection/import compatibility gate when APC adoption or stability
justifies it.

### Policy and enforcement

| Product/project | Strength | Fit |
|---|---|---|
| Rosetta | Centralized, versioned instructions, architecture, standards, business rules, governance, and MCP distribution across coding agents | The closest direct product found; ProjectLore must differentiate through an open local canonical model, typed relationships/provenance, deterministic checker contracts, and explicit Fraimed/CodeGraph composition |
| Conteks Base | MCP-served company standards, conventions, and project-scoped governance | Validates demand for agent-consumable governance; appears platform/knowledge-base oriented rather than a Git-native project/domain model with local compiler and gates |
| Agent Project Context (APC) | Proposes a neutral `.apc/` convention across agent tools | Useful emerging packaging precedent; ProjectLore should watch or support it rather than claim a competing universal directory convention |
| RuleSync, Ruler, ai-nexus, and similar compilers | Synchronize instructions across CLAUDE.md, AGENTS.md, Cursor, and other native files | Solve distribution and format drift, not semantic modeling or policy evaluation; ProjectLore can interoperate or borrow managed-block patterns |
| Tandem and agent-governance runtimes | Step-level tool authorization and approval outside model context | Govern agent authority broadly; ProjectLore rules are repository meaning and engineering correctness, not a replacement security sandbox |
| OPA/Rego | General-purpose policy decisions over structured data; strong CI and infrastructure ecosystem | Possible later backend for organization-wide policies, but excessive for the local MVP and requires mapping agent actions into Rego input |
| CUE | Schema and policy constraints over configuration in one model | Useful future optional checker for configuration-heavy projects |
| Cedar | Formally reasoned authorization decisions over principal/action/resource/context | Wrong core abstraction: ProjectLore rules govern engineering changes, not primarily access authorization |
| Semgrep | Deterministic source patterns in local/CI workflows | Excellent checker adapter; not the project/domain model |
| ArchUnit and architecture tests | Precise dependency and architecture enforcement | Excellent language-specific checker adapters |
| Agent hooks | Immediate context injection and pre/post-action blocking | Required integration surface, but client-specific and not sufficient as the only enforcement |

Conclusion: ProjectLore owns rule identity, applicability, severity, evidence, and
checker binding. Existing engines execute specialized checks. The MVP should ship a
small built-in checker registry, not a general expression language.

## Differentiated product contract

ProjectLore has four distinct kinds of truth:

1. **Descriptive knowledge** — concepts, terms, definitions, relationships, and
   implementation anchors.
2. **Normative knowledge** — invariants, prohibitions, obligations, scope
   applicability, severity, and rationale.
3. **Executable checks** — deterministic checker bindings that can return pass,
   fail, not-applicable, or indeterminate with evidence.
4. **External context references** — resolvable pointers to Fraimed, code graphs,
   specs, decisions, tests, and source locations.

These must not be collapsed. A prose rule is useful guidance but is not mechanically
enforced. A checker is not automatically the canonical statement of why the rule
exists. A Fraimed validation item is current work acceptance, not a permanent domain
concept.

## Architecture

```text
                     Git-tracked ProjectLore YAML
                                  |
             +--------------------+--------------------+
             |                                         |
     contracts + semantic compiler              integration manifest
             |                                         |
      immutable ProjectModel              generated agent configuration
             |                                         |
    +--------+---------+-----------+        +-----------+-----------+
    |                  |           |        |                       |
 Query service    Policy service  Adapters  Claude Code hooks     Codex hooks
    |                  |           |        |                       |
    +-------- MCP -----+-----------+--------+-----------------------+
                       |
           local Git hooks / pre-commit / CI
```

### Core modules

- `ModelLoader`: bounded discovery, safe YAML, includes, and source maps.
- `ModelValidator`: strict structural validation plus cross-document semantic
  validation.
- `ModelCompiler`: deterministic immutable `ProjectModel`.
- `QueryService`: terminology, concepts, relationships, rules, anchors,
  provenance, and scoped context bundles.
- `PolicyService`: resolves applicable rules and evaluates registered checkers.
- `AdapterRegistry`: optional read-only resolvers for Fraimed, CodeGraph, specs, and
  source hosts.
- `IntegrationCompiler`: emits or verifies agent-specific MCP, instruction, hook,
  pre-commit, and CI configuration from one project manifest.

The MCP server, CLI, hooks, and CI invoke these services. They do not implement
separate interpretations of the model.

## Model additions required for enforcement

Add these entities to the earlier knowledge model:

### Rule

- stable `id`;
- human-readable statement and rationale;
- `kind`: invariant, prohibition, obligation, convention, or advisory;
- `severity`: blocker, error, warning, or info;
- `scope`: project, domain, paths, symbols, entity kinds, and optional change kinds;
- provenance;
- `enforcement`: advisory, required-context, pre-action, post-action, commit, or CI;
- zero or more checker bindings;
- remediation guidance;
- explicit owner and lifecycle status.

`Constraint` is not a second normative primitive. The earlier `Constraint` entity is
replaced by `Rule`. A concept can reference applicable rules; rules alone own
normative severity, applicability, enforcement, and checker bindings.

### CheckerBinding

- stable checker kind, such as `projectlore.reference-integrity`,
  `command.forbidden`, `path.required`, `test.command`, `semgrep.rule`,
  `archunit.test`, or `external.command`;
- versioned parameters validated by a checker-specific schema;
- bounded timeout and working-directory policy;
- allowed enforcement points;
- evidence format;
- failure behavior.

Arbitrary shell is not allowed in canonical model files by default. An
`external.command` binding is opt-in through trusted repository configuration, uses
an argv array rather than shell text, has a timeout, and is never callable merely
because untrusted model content names it.

### ContextProfile

Defines a bounded context bundle for a task or path:

- domains and concepts to include;
- applicable rules;
- Fraimed reference requirements;
- code graph queries or anchors;
- token/result budget;
- freshness requirements;
- behavior when a dependency is unavailable.

### IntegrationManifest

Declares supported clients, required integration level, generated file ownership,
hook placement, MCP command, and CI/pre-commit gates. Generated blocks carry a
digest so `lore integration check` detects manual drift without overwriting user
content.

### ScopeReceipt

A gate cannot prove that a model understood prose. It can prove that policy
evaluation resolved current authoritative scope. A versioned receipt records:

- Fraimed Frame ID and adapter identity;
- confirmed scope version or explicit absence;
- frame closure generation and status;
- digests of applicable decisions, governing specs, and open Validation items;
- observation time, freshness policy, and freshness result;
- ProjectLore model digest and policy-evaluation ID.

A separate session receipt may record that a client hook requested the context
bundle, but it must never be described as proof of cognition.

Required gates revalidate the authoritative closure/scope generation immediately
before decision or enforce a bounded maximum receipt age. Evidence records the
revision and time actually evaluated; a receipt does not remain valid merely because
it was fresh when created.

### Authority and supersession

Every source reference declares source system, authority role, observed version or
digest, effective status, and optional supersession link. The compiler reports
conflicts rather than silently preferring Git prose, Fraimed decisions, local specs,
or code-derived evidence. Project-specific authority policy determines which
conflicts block a gate.

System boundaries are not configurable: Fraimed owns live scope, decisions,
Validation, attempts, and outcomes; Git owns reviewed ProjectLore model files; and
CodeGraph owns derived code topology. Project policy may rank sources only within
their legitimate domains or make conflict handling stricter. It cannot demote those
system authorities.

## Enforcement model

ProjectLore must report an enforcement result as one of:

- `pass`;
- `fail`;
- `not_applicable`;
- `indeterminate` (missing dependency, stale model, timeout, or unsupported check).

Fail-open versus fail-closed is declared per enforcement point, not improvised by
the client adapter:

- interactive advisory lookup: fail open with visible diagnostics;
- required context handshake: block when the canonical model is invalid or the
  required authoritative source cannot be obtained;
- pre-action checks: block only deterministic high-confidence violations;
- post-action checks: provide immediate correction feedback but do not pretend to
  undo completed side effects;
- commit and CI gates: fail closed for blocker/error rules and indeterminate
  required checks, while reporting the actual assurance achieved.

ProjectLore reports assurance without exaggeration:

- `available`;
- `hook_active`;
- `local_gate_passed`;
- `ci_gate_passed`;
- `protected_gate_enforced`.

The last state is reported only after verifying that the hosted required check and
its bypass policy protect the target branch. A pre-commit hook or ordinary CI run
alone never means that a change “cannot be accepted.” Hosted evidence includes the
repository, branch, observed configuration revision/time, and verifier permission
scope.

### Five enforcement levels

| Level | Behavior | Mechanism |
|---|---|---|
| E0 — available | Agent can query meaning | read-only MCP |
| E1 — loaded | Every session receives a compact model/status/context handshake | AGENTS.md/CLAUDE.md bootstrap plus SessionStart/InstructionsLoaded hooks |
| E2 — consulted | Material prompts or scoped changes receive applicable concepts and rules | UserPromptSubmit and path-aware context hooks |
| E3 — guarded | Risky tool actions and modified files are evaluated immediately | PreToolUse, PostToolUse, FileChanged, and Stop hooks |
| E4 — certified | Deterministic gates pass and the achieved repository assurance level is disclosed | pre-commit, CI, and optional verified branch protection |

E4 is the durable enforcement boundary. Agent hooks improve the loop but can be
disabled, bypassed, unavailable, or vendor-specific.

### Claude Code

Claude Code currently provides project-shared settings, project MCP configuration,
and lifecycle hooks including SessionStart, InstructionsLoaded, UserPromptSubmit,
PreToolUse, PostToolUse, FileChanged, and Stop. PreToolUse can block an action. MCP
tools can themselves be hook handlers.

ProjectLore should generate:

- a small managed section in `CLAUDE.md`;
- `.mcp.json` or documented project MCP registration;
- `.claude/settings.json` hook entries;
- thin hook commands that call `lore gate` with structured event JSON.

### Codex CLI

Codex currently provides layered `AGENTS.md`, project `.codex/config.toml` MCP
configuration, and lifecycle hooks including SessionStart, UserPromptSubmit,
PreToolUse, PostToolUse, and Stop. PreToolUse can deny an operation.

ProjectLore should generate:

- a small managed section in `AGENTS.md`;
- project-scoped MCP configuration;
- project hook configuration invoking the same `lore gate` event contract.

Client adapters translate native hook JSON into a versioned
`ProjectLoreAgentEvent`. Policy evaluation remains client-neutral.

Client parity is capability-aware, not assumed. ProjectLore maintains a versioned
matrix of native events, blocking behavior, project trust, configuration scope,
subagent behavior, and managed-policy limitations. Contract tests require equivalent
decisions only for normalized events supported by both clients and declare
degradation elsewhere. `lore doctor` verifies installed client versions, project
trust, MCP startup, hook firing, and actual block behavior.

External prose and derived code text are untrusted data at the context boundary.
Adapters return structured fields with source/trust labels, bounded sizes,
deterministic truncation, and provenance. ProjectLore never splices retrieved text
into generated instructions as executable directives.

## MCP contract

Keep the six proposed read tools and add two orchestration tools:

- `model_status`
- `model_search`
- `model_get_concept`
- `model_resolve_term`
- `model_get_relationships`
- `model_validate`
- `context_for_task`: returns a bounded, provenance-backed context bundle and the
  applicable rule set for a task, paths, or external work reference.
- `policy_check`: evaluates a proposed or observed structured action without
  mutating canonical knowledge.

The CLI provides equivalent non-MCP entry points:

- `lore context --task ... --paths ... --json`
- `lore gate --event ... --input ... --json`
- `lore check [--changed|--all]`
- `lore integration install|check|diff`

MCP remains read-only with respect to canonical knowledge. `policy_check` computes a
decision; it does not perform the action.

## Sync and freshness

The canonical model syncs through Git. ProjectLore computes a digest over ordered
model files, schema version, integration manifest, and checker configuration.

Runtime status distinguishes:

- source model digest;
- compiled snapshot digest;
- external adapter freshness;
- code anchor resolution revision;
- integration configuration digest.

Model file refresh preserves the last valid snapshot, but required gates disclose
and reject a stale snapshot when a rule requires current source. Fraimed and
CodeGraph are queried through bounded adapters and cached only as disposable
projections with source IDs and observation times.

## Hardened implementation plan

### Phase 0 — Accept the product boundary

Deliverables:

- owner accepts or revises this product boundary and phase order;
- governing Fraimed spec is revised;
- local README, AGENTS.md, and architecture align;
- LinkML authority is explicitly replaced;
- choose the first pilot slice in Homebrew.

Gate:

- no contested architecture remains;
- baseline tests pass;
- no implementation beyond scaffold proceeds before acceptance.

### Phase 1 — Homebrew enforcement walking skeleton

Deliverables:

- choose one bounded Homebrew domain and encode only the concepts and source
  references required for three real invariants;
- minimal strict Pydantic/YAML contract and deterministic validation;
- minimal `context_for_task`, `model_status`, and `policy_check`;
- read-only Fraimed resolution producing a `ScopeReceipt`;
- project MCP registration for Claude Code and Codex;
- one supported blocking pre-action hook per client;
- `lore check` runnable from a clean checkout;
- a fixed before/after task and violation corpus.
- minimum hook safety: explicit user installation/trust, built-in checkers only, no
  model-selected external commands, fixed argv invocation, repository-root
  confinement, bounded input/output and timeout, sanitized inherited environment,
  and no network access.

Gate:

- both clients report the same model/contract digest and resolve current Fraimed
  scope;
- equivalent supported hook events produce equivalent policy decisions;
- three real violations are caught by the interactive gate and clean-checkout check;
- compliant cases pass and canonical files remain byte-identical;
- record retrieval success, provenance correctness, catch rate, false positives,
  latency, context size, and rediscovery/correction counts;
- record the baseline, then owner-accept or pre-register comparative thresholds
  before running the after-corpus;
- no Homebrew workflow or branch-protection change occurs without separate owner
  approval.

Exit criterion:

- the integration-and-enforcement loop is useful before a general platform is
  designed.

### Phase 2 — Harden contracts and compiler from pilot evidence

Deliverables:

- complete strict Pydantic entities for concepts, terms, relationships, rules,
  checker bindings, context profiles, sources, anchors, receipts, and integration;
- generated committed JSON Schema;
- safe YAML loader, source maps, normalized immutable model, authority/supersession
  semantics, and stable diagnostics;
- valid and hostile fixtures;
- formalize only abstractions exercised or required by the walking skeleton.

Gate:

- schema regeneration has zero diff;
- fixtures cover duplicate IDs, dangling references, missing provenance, conflict
  and supersession, invalid checker parameters, unsafe paths, incompatible versions,
  and arbitrary-command rejection;
- identical input produces byte-equivalent normalized output;
- the Phase 1 corpus still passes without semantic changes.

### Phase 3 — Generalize query, policy, MCP, and client adapters

Deliverables:

- in-memory `QueryService` and `PolicyService`;
- eight read-only MCP tools and equivalent CLI commands;
- task/path applicability, explicit outcome semantics, and receipts;
- preview-first managed-block generator with nested-instruction precedence rules;
- versioned Claude/Codex capability matrix and degradation behavior;
- `lore doctor` integration probes.

Gate:

- both clients query equal model digests and contract versions;
- session start records a context request without claiming cognition;
- generated integration drift is detected;
- capability probes prove actual hook firing/blocking for pinned minimum versions;
- canonical model files remain byte-identical after every tool call;
- fixed questions, conflicts, ambiguity, stale dependencies, and timeouts have
  golden outcomes.

### Phase 4 — Security envelope and interactive enforcement

Deliverables:

- E3 adapters for supported native hook events and subagents;
- pre-action deterministic blocker checks;
- post-edit/path-aware checks and Stop summary;
- executable checker allowlists stored outside model content;
- explicit repository trust, sanitized environment, bounded output, process-tree
  timeout/termination, repository/symlink boundaries, dependency pinning, secret
  redaction, and network policy;
- structured untrusted-context handling and audit records.

Gate:

- contract tests replay identical normalized events through Claude and Codex
  adapters and produce the same decisions where both support the event;
- bypass, unavailable dependency, stale model, timeout, malformed event, and
  subagent cases are tested;
- prompt-injection fixtures remain quoted data;
- hooks add no network or shell authority beyond explicitly trusted configuration;
- checker termination leaves no child process running.

### Phase 5 — Durable repository assurance

Deliverables:

- pre-commit integration and CI command for E4;
- changed-file impact resolution;
- pluggable Semgrep, architecture-test, and project-test checkers;
- machine-readable evidence artifact and stable exit codes;
- `lore integration check` with the five assurance states;
- optional read-only verification of required-check/branch-protection configuration.

Gate:

- a violating change is blocked locally and in a clean CI-like checkout;
- a compliant change passes without credentials or hosted ProjectLore service;
- CI invokes existing project tests rather than reimplementing their semantics;
- deterministic checks have no LLM dependency;
- ProjectLore never reports `protected_gate_enforced` without verified hosted
  configuration and bypass policy.

### Phase 6 — Expand adapters, checkers, and project coverage

Deliverables:

- CodeGraph adapter for anchor and changed-symbol resolution;
- pluggable Semgrep, architecture-test, and project-test checkers;
- deepen the Homebrew model only where measured value warrants it;
- pilot one contrasting slice in Sophie or Sienna;
- rerun comparative measurements and record maintenance cost.

Gate:

- policy evaluation cannot pass a required gate without a current `ScopeReceipt`;
- adapter failure never silently converts required context into success;
- broken code anchors remain localized diagnostics;
- measured retrieval, provenance, catch rate, false positives, latency, context size,
  and correction loops meet thresholds set from Phase 1 evidence.

### Phase 7 — Projection, refresh, and scale only after pilot

Deliverables:

- SQLite/FTS projection behind unchanged service contracts;
- transactional rebuild, last-valid snapshot, watcher, and bounded caches;
- performance and resource budgets derived from the pilot.

Gate:

- the same repository contract suite passes in-memory and SQLite;
- valid refresh is visible without client restart;
- invalid refresh never replaces the last valid snapshot;
- no graph database or embedding dependency is added without measured need.

### Phase 8 — Public alpha

Deliverables:

- package/release policy, migrations, security policy, contribution guide, public
  safe example, clean installation, Windows/Linux/macOS checks;
- adapter and checker SDK documentation;
- compatibility matrix for supported agent versions and hook capabilities.

Gate:

- fresh-install offline suite passes;
- package contains no private data or generated local state;
- public release requires separate owner authorization.

## Explicit deferrals

- hosted synchronization and multi-user service;
- autonomous model writes by agents;
- learned rules entering canonical knowledge;
- embeddings or GraphRAG;
- a graph database;
- custom rule expression language;
- OPA, CUE, Cedar, LinkML, RDF, or SHACL as a required runtime;
- mirroring Fraimed or CodeGraph databases;
- organization-wide policy distribution.
- claiming a new universal agent-configuration directory convention.

## Research sources

- Contextive terminology and bounded contexts:
  https://docs.contextive.tech/community/v/1.17.8/guides/defining-terminology/
- Augment Context Engine MCP:
  https://docs.augmentcode.com/context-services/mcp/overview
- Greptile custom context and validation:
  https://www.greptile.com/learning
- Greptile graph context:
  https://www.greptile.com/docs/how-greptile-works/graph-based-codebase-context
- Sourcegraph Deep Search:
  https://sourcegraph.com/docs/deep-search
- Swimm continuous knowledge:
  https://swimm.io/blog/docs-as-part-of-your-ci-swimm-for-gitlab
- GitHub Spec Kit:
  https://github.github.com/spec-kit/
- OpenSpec:
  https://github.com/Fission-AI/OpenSpec
- CUE configuration and policy:
  https://cuelang.org/docs/concept/how-cue-enables-configuration/
- Open Policy Agent:
  https://www.openpolicyagent.org/docs
- OPA in CI:
  https://www.openpolicyagent.org/docs/cicd
- Cedar authorization model:
  https://docs.cedarpolicy.com/auth/authorization.html
- Claude Code hooks:
  https://code.claude.com/docs/en/hooks
- Claude Code MCP:
  https://code.claude.com/docs/en/mcp
- Codex AGENTS.md:
  https://learn.chatgpt.com/docs/agent-configuration/agents-md.md
- Codex hooks:
  https://learn.chatgpt.com/docs/hooks.md
- Codex MCP:
  https://learn.chatgpt.com/docs/extend/mcp.md
- Rosetta:
  https://griddynamics.github.io/rosetta/docs/introduction/
- Conteks Base:
  https://conteksbase.com/
- Agent Project Context:
  https://agentprojectcontext.com/en/docs/introduction/
- RuleSync:
  https://www.rulesync.dev/
- Tandem:
  https://tandem.ac/
