# Dedicated UI decision

## Decision

ProjectLore has not earned a dedicated UI. Keep the product headless for the
public alpha and continue serving people and agents through Git-tracked model
files, the CLI, MCP, editor diagnostics, and reviewable generated artifacts.

This is an explicit Phase 7 decision made under the owner's delegation to
complete the phase autonomously. A future UI requires a separately authorized
Frame after one of the measurable triggers below is observed.

## Pilot evidence

The decision uses two retained pilots with materially different domains:

- The Homebrew forecast-trust pilot encoded a Python/TypeScript timestamp trust
  boundary. It achieved 6/6 retrieval and provenance correctness, 3/3
  correction rediscovery, 0/3 false policy violations, and 0.108 ms p95
  query/policy latency.
- The Sienna campaign-authority pilot encoded deterministic C# simulation
  authority. It achieved 3/3 retrieval and provenance correctness, 2/2
  correction rediscovery, 0/2 false policy violations, and 0.159 ms p95
  query/policy latency.

Across both pilots:

- **Authoring:** the difficult work was selecting accepted project meaning and
  citing authoritative evidence, not manipulating the YAML syntax. A graphical
  editor would not remove that judgment.
- **Discoverability:** agents retrieved concepts, rules, relationships, and
  provenance through the same MCP contract without bespoke client prompts.
- **Graph comprehension:** the bounded domain slices were understandable through
  focused relationship queries and source citations. Neither pilot recorded a
  failed task caused by the absence of a visual graph.
- **Diagnostics:** stable validation and policy diagnostics were sufficient for
  corrections. Neither pilot recorded a need to browse a diagnostic dashboard.
- **Audit:** Git diffs, provenance, evaluation corpora, and retained result JSON
  supplied reviewable evidence. Neither pilot required a second mutable audit
  store.

This evidence is enough to reject speculative UI construction. It is not proof
that a UI will never be useful.

## Options considered

| Option | Pilot-supported benefit | Cost and trust impact | Decision |
| --- | --- | --- | --- |
| No dedicated UI | Preserves the working CLI/MCP/Git flow with no new surface | Lowest maintenance; canonical files remain obvious | **Choose now** |
| Generated static reports | Shareable summaries without runtime state | Small bounded generator and accessibility burden | Add only when a recurring human review cannot consume existing Markdown/JSON |
| IDE-native diagnostics | Puts source-located errors in the authoring loop | Client-specific adapters and compatibility testing | Prefer as the first interactive enhancement after measured demand |
| Local read-only explorer | Helps humans traverse larger models and provenance | New frontend/runtime/security surface; must remain disposable | Consider only after repeated graph-comprehension failures |
| Full editor/dashboard | Could combine authoring, diagnostics, and audit workflows | Highest maintenance and greatest risk of becoming competing authority | Reject until sustained multi-user authoring evidence exists |

## Candidate UI contract

No UI is proposed now. If a future trigger is met, the smallest candidate is a
local read-only explorer, not an editor or hosted dashboard.

- **Users:** project maintainers and reviewers who do not primarily use MCP or
  the CLI.
- **Jobs:** inspect a concept and its provenance, traverse a bounded
  relationship neighborhood, and review localized diagnostics.
- **Workflow:** open a repository-local model, inspect only validated
  last-known-good data, follow source links, and return to Git for edits.
- **Measurable benefit:** reduce median time for a named review task by at least
  30% across at least five observed tasks, or eliminate at least three repeated
  graph-comprehension failures across two projects.
- **Trust boundary:** localhost by default; read-only; no telemetry, network
  service, or unique database authority; untrusted model files pass through the
  existing bounded loader and validator.
- **Maintenance budget:** at most one small optional package, no always-on
  service, and no more than 10% of release engineering effort. Exceeding this
  budget requires a new product decision.

## Re-evaluation triggers

Open a separately scoped UI Frame only when retained evidence shows one of:

1. Three or more failed or materially delayed tasks across at least two projects
   attributable to relationship or provenance comprehension.
2. Five or more recurring human review tasks whose median completion time a
   prototype static report or read-only explorer improves by at least 30%.
3. Repeated source-located diagnostics that users cannot act on through the CLI
   or editor integration.
4. A multi-user authoring workflow where Git review alone produces documented
   conflict, provenance, or accessibility failures.

Any future surface reads canonical Git-tracked model files and disposable
projections. Its database, cache, or index must be rebuildable and can never
become the unique source of project knowledge.
