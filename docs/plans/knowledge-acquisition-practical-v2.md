# ProjectLore knowledge acquisition - practical implementation plan v2

## Header

### Requested outcome

Implement a standalone ProjectLore knowledge-acquisition layer that gives a new
repository an explicit project-knowledge baseline during onboarding and then
grows that knowledge passively from bounded repository-change evidence. Changes
remain proposals until an explicit review and canonical apply. Claude Code and
Codex CLI use the same vendor-neutral behavior through project-scoped hooks and
a separately versioned read-only MCP sidecar.

### Non-goals

- No Fraimed, CodeGraph, hosted service, database, embeddings, background
  watcher, embedded AI inference, UI, publication, or global user installation.
- No source excerpts, prompts, transcripts, credentials, or tool output in
  acquisition state.
- No automatic acceptance and no mutation from MCP reads.
- No change to the frozen core `projectlore-tools/0.4.0` contract.
- No claim of client/OS support until the exact built candidate is exercised.

### Governing sources and precedence

1. Repository `AGENTS.md` and `docs/architecture.md`.
2. Owner direction: baseline knowledge injection is onboarding; subsequent
   growth should be passive; ProjectLore must work without Fraimed; Claude Code
   and Codex CLI are first-class clients.
3. Committed implementation contract
   `docs/contracts/knowledge-acquisition-v1.md` at baseline.
4. The technically reviewed but unaccepted proposal
   `docs/contracts/proposed/knowledge-acquisition-v0.6.1/`.
5. Current code and tests as repository facts, not product authority.

The proposed v0.6.1 contract becomes governing only when Phase 0 promotes its
reconciled engineering choices. Experimental values remain non-guaranteed until
Phase 5 measures them.

### Baseline and worktree

- Baseline: `a087c22baa3206d7dd82b3bf6d2c7b760fa8a0be` on `main`, three commits ahead
  of `origin/main`.
- Tracked worktree: clean when this plan was authored.
- In-scope untracked planning inputs: acceptance audit 0.3 and proposed contract
  packages v0.1-v0.6.1. They remain uncommitted pending owner review.
- Excluded unrelated file: `docs/maintain-projectlore-model-skill.md`.
- `.codegraph/` is absent, so normal source inspection was used.

### Current anchors

- `src/projectlore/cli.py:64` owns the single CLI parser; it has `init` and
  `remove`, but no `onboard` or `knowledge` command groups.
- `src/projectlore/onboarding.py:19` owns preview-first initialization and
  currently writes integration files sequentially with drift checks.
- `src/projectlore/hook.py:32` is the existing bounded hook entry point.
- `src/projectlore/tool_spec.py:7` freezes core MCP at 0.4.0.
- `src/projectlore/mcp_server.py:277` owns the core server entry point.
- `src/projectlore/removal.py:24` owns preview-first integration cleanup but has
  no acquisition inventory, receipt, repair, or compaction behavior.
- `pyproject.toml:47` owns installed entry points.
- No production acquisition package, state directory, sidecar, proposal/review
  transaction, signal, packet, or recovery implementation exists.

## Governing requirements

| ID | Requirement | Implementation path | Verification | Status |
| --- | --- | --- | --- | --- |
| R1 | Git-tracked ProjectLore YAML remains the only canonical knowledge. | Phases 1-2 | Query snapshots before proposal/review/apply and after apply | Covered |
| R2 | Onboarding creates an immediate evidence packet and a vendor-neutral agent path to submit a provenance-bearing baseline proposal for new and existing repositories. | Phase 2 | New/existing/invalid model fixtures; Claude/Codex proposal parity; preview is no-write | Covered |
| R3 | Accept, reject, and revise are explicit digest-bound decisions; only accept+apply changes canonical knowledge. | Phase 2 | Stale, mixed, retry, denial, and idempotency tests | Covered |
| R4 | Passive growth captures bounded metadata/hash evidence without source prose or provider calls. | Phase 3 | Privacy canaries, offline hook runs, N/N+1 bounds | Covered |
| R5 | SessionStart/CLI deterministically turn pending signals into at most one outstanding packet; terminal evidence does not requeue. | Phase 3 | Restart, concurrency, revise, accept/reject, A-B-A tests | Covered |
| R6 | Canonical and workflow state use atomic roots and recover safely across partial failure and competing writers. | Phases 1-3 | Fault matrix and reader/writer concurrency at filesystem boundary | Covered |
| R7 | Acquisition MCP is read-only and separately versioned; core MCP 0.4 is unchanged. | Phase 4 | Frozen core fixtures, sidecar wire fixtures, no-write snapshots | Covered |
| R8 | Claude Code and Codex CLI receive project-scoped, command-resolvable, journaled integration with honest partial/conflict status. | Phase 4 | Literal config parsing, subprocess resolution, drift/recovery fixtures | Covered |
| R9 | Removal/repair/compaction are preview-first, fail closed, and preserve accepted YAML and query equivalence. | Phase 4 | Inventory, corrupt/fork, removal, and equivalence fixtures | Covered |
| R10 | The installed candidate works offline and support claims are based on real candidate/client evidence. | Phase 5 | Wheelhouse/offline corpus and selected client/OS runs | Covered |

## Scope classification and prior-finding disposition

| Finding | Classification | Disposition |
| --- | --- | --- |
| The original plan accumulated thirteen amendments and a certification-sized preimplementation package. | In scope | Replace it with this dependency-ordered plan; retain history only as research. |
| Exact persisted/MCP/hook/fault/removal contracts were previously underdefined. | Necessary prerequisite | v0.6.1 resolves the technical definitions; Phase 0 promotes only the minimal accepted surface. |
| Candidate wheel hashes, measurements, and real-client receipts do not exist before implementation. | Candidate regression boundary | Generate in Phase 5; do not block Phases 1-4. |
| Acceptance audit 0.3 is not ready against the old contract. | In scope | Supersede after Phase 0 with focused tests per phase; preserve its two frozen core/no-write checks. |
| Existing `init` writes multiple integration files sequentially. | Candidate regression | Do not claim whole-onboarding atomicity; keep canonical and integration transactions separate and journal integration. |
| Existing full suite has a terminology allowlist failure caused by committed plan paths. | Adjacent follow-up | Repair independently before final full-suite evidence; it does not define acquisition behavior. |
| Fraimed/CodeGraph/UI/global install concerns. | Adjacent follow-up | Explicitly outside this implementation. |

## Reconciled engineering choices

The committed plan and contract authorize the outcome and record no open product
decisions. The technically reviewed v0.6.1 package resolves these implementation
choices; they do not require another owner gate:

1. **P01 digest convention:** use RFC 8785 JCS plus domain-separated SHA-256 and
   the v0.6.1 exclusion registry.
2. **P02 public shapes/diagnostics:** use strict versioned objects, unknown-field
   rejection, and the proposed owned `PLKA` diagnostic range.
3. **P03 fault-test seam:** use constructor injection from a test-only support
   module excluded from production wheels; a separately published package is not
   required unless packaging constraints demonstrate the need.
4. **P04 sidecar surface:** use five read-only acquisition tools and page sizes
   1-256/default 50, with core MCP unchanged.
5. **P05 limits/support:** use the proposed resource/time/retention values as
   experimental implementation defaults, not compatibility guarantees, until
   Phase 5 measurements. Claim only OS/client cells actually exercised; an
   unavailable platform does not block implementation or a narrower alpha.
6. **P06 CLI:** use nested `lore onboard`/`lore knowledge`, preserve existing
   `lore remove`, and add explicit quarantine repair.

Client minimum versions are evidence questions, not owner semantics. Do not
publish Claude `2.1.220` or Codex `0.146.0` as minimums unless exact binaries or
authoritative release evidence plus successful selected-platform receipts prove
them. Otherwise support the tested current versions only.

## Phase 0 - Promote the minimal contract and focused tests

### Objective

Promote the technically reviewed v0.6.1 definitions into governing contract
data and replace the stale preimplementation package with focused phase tests.
This covers the contract prerequisite for R2-R10.

### Targets

- `docs/contracts/proposed/knowledge-acquisition-v0.6.1/`
- `docs/contracts/knowledge-acquisition-v1.md`
- `tests/acceptance/`
- `docs/acceptance/knowledge-acquisition-v1/`

### Ordered changes

1. Record P01-P06 as the reconciled engineering choices above; do not reopen
   technically resolved schemas without implementation evidence.
2. Promote the standalone contract to one stable versioned location;
   keep previous proposals as nonnormative history or omit them from the commit.
3. Replace acceptance 0.3 with a small requirement-to-test map organized by
   Phases 1-4. Tests may initially fail on missing public entry points. Candidate-
   bound wheel/client/measurement procedures remain Phase 5 rather than frozen
   preconditions.
4. Freeze core MCP 0.4 fixtures and the read-does-not-write check as permanent
   regression tests.

### Verification and completion

- Every engineering choice is recorded; measured values are labelled
  experimental and have a Phase 5 retention/revision rule.
- Contract JSON parses, all local references close, positive/negative fixtures
  validate, and all 27 requirements map to a phase.
- Completion: no production behavior depends on an unstated choice.

### Non-goals

No production implementation, client run, or candidate evidence generation.

## Phase 1 - Build the acquisition state and transaction kernel

### Objective

Implement the smallest provider-neutral foundation for immutable evidence,
workflow generations, digest identities, locks, atomic roots, and recovery.
Covers R1, R3, R6 and prerequisites for R2/R4/R5/R9.

### Targets

- New cohesive modules under `src/projectlore/acquisition/`: `models.py`,
  `digest.py`, `store.py`, `transactions.py`, `validation.py`.
- Generated acquisition JSON Schema in the repository's existing schema
  convention.
- Test-only fault adapter in a separate non-production package/path.

### Ordered changes and invariants

1. Implement strict Pydantic models from the accepted contract and generate the
   portable schema; keep semantic validation separate from structure.
2. Implement domain-separated identities and root-confined immutable object
   storage under `.projectlore/knowledge/`.
3. Implement one workflow-root activation per batch, canonical-then-workflow
   lock ordering, continuous locks after claim, universal canonical-writer
   admission, and old/new recovery.
4. Route every future canonical acquisition apply through the shared transaction
   boundary. Existing reads remain unaware of unactivated proposals.
5. Provide deterministic test-only failure injection without exposing it from
   the production wheel.

### Verification, recovery, and completion

- Schema/digest vectors, hostile paths/symlinks, immutable-write, lock ordering,
  competing writers/readers, and the proportional claim/commit/recovery fault
  matrix pass.
- Crash before root replacement leaves old state; crash after canonical commit
  rolls workflow forward; supported traces never produce `neither`.
- Completion: a multi-signal no-op transaction can be staged, activated,
  recovered, and read as one complete generation without changing canonical
  YAML.

### Non-goals

No repository scan, hooks, proposal authoring, MCP, or client integration.

## Phase 2 - Deliver onboarding, review, and canonical promotion

### Objective

Give new and existing repositories an immediate knowledge baseline and a complete
human-reviewable promotion lifecycle. Covers R1-R3 and the active CLI portion of
R6.

### Targets

- `src/projectlore/onboarding.py`
- `src/projectlore/cli.py`
- New `src/projectlore/acquisition/onboarding.py`, `proposal.py`, `review.py`
- Relevant onboarding, CLI, loader, refresh, and acceptance tests

### Ordered changes and invariants

1. Add `lore onboard start|status` without removing or silently changing
   existing `lore init` behavior.
2. Build a deterministic metadata-only baseline packet from repository/model
   identity, Git state, existing ProjectLore YAML, and explicitly allowed
   project metadata. This bootstrap packet identifies bounded high-value source
   paths and known/missing model areas; it does not pretend hashes contain domain
   meaning.
3. Add a vendor-neutral proposal submission path: the sidecar/CLI lets an agent
   read the packet, the agent inspects the cited repository files through its
   normal read tools, and `lore knowledge propose --packet <id> --input <json>`
   validates a strict provenance-bearing proposal. Managed instructions give
   Claude and Codex the same operation; ProjectLore persists no source excerpts.
4. Add `lore knowledge status|propose|review|apply|recover`. Review accepts only
   `accept`, `reject`, or `revise` against exact proposal/evidence digests.
5. Apply accepted candidates through Phase 1's canonical transaction using
   immutable fragments/index plus one canonical-root activation. Proposal,
   reject, and revise states never appear in core queries.
6. Keep canonical activation and multi-file client integration as separate
   transactions; a later integration failure never rolls back accepted YAML.

### Verification, recovery, and completion

- New/existing model, no Git, detached Git, sparse evidence/explicit unknowns,
  malformed input, equivalent Claude/Codex submissions, stale review, mixed
  disposition, concurrent apply, crash, retry, and idempotency tests pass.
- Core queries prove no proposal leakage and rediscover accepted knowledge with
  provenance after apply.
- Completion: a clean temporary repository completes preview -> baseline packet
  -> agent-authored proposal -> review -> apply -> core query without Fraimed,
  network, or manual YAML authoring.

### Non-goals

No passive capture or client-hook changes yet.

## Phase 3 - Add passive signals and deterministic packets

### Objective

Grow knowledge passively from ordinary repository work while retaining explicit
review. Covers R4-R6.

### Targets

- `src/projectlore/hook.py` and `hook_event.py`
- New `src/projectlore/acquisition/signals.py`, `packets.py`, `hooks.py`
- `src/projectlore/cli.py` for `knowledge scan` and `knowledge packet next`

### Ordered changes and invariants

1. Normalize only trusted Stop and SessionStart fields; discard prompt,
   transcript, assistant message, tool payload, and environment content.
2. Stop records a bounded content-addressed repository-state transition. Repeated
   unchanged Stop calls deduplicate; A-B-A remains three auditable observations.
3. SessionStart and CLI use the same locked materializer to create at most one
   outstanding packet from pending signals. Source/HEAD/model drift aborts the
   attempt without acknowledging evidence.
4. Expose packet contents through the same read-only packet operation used in
   Phase 2, and accept proposals only through the same strict submission path.
   Passive capture therefore discovers evidence; an agent supplies meaning.
5. Accept/reject terminally consume exact evidence; revise releases its packet
   lease; later canonical changes do not resurrect terminal signals.
6. Overflow creates an honest reconciliation requirement and never claims
   complete history when Git history is missing.

### Verification, rollback, and completion

- Raw Claude/Codex fixtures, malformed/oversized inputs, privacy canaries,
  disabled hooks, concurrency, restart, clock jumps, drift, overflow, revise,
  accept/reject, and A-B-A pass.
- Hook failure remains advisory and disabling hooks leaves the explicit CLI path.
- Completion: ordinary edit -> Stop -> next SessionStart packet -> proposal ->
  review/apply -> next SessionStart no requeue, with no manual scan in the
  trusted default path.

### Non-goals

No source prose capture, background watcher, model call, or automatic apply.

## Phase 4 - Expose the sidecar and finish client lifecycle

### Objective

Make acquisition state safely usable by both agent clients and removable without
coupling it to core MCP. Covers R7-R9.

### Targets

- New `src/projectlore/acquisition_mcp.py`
- `pyproject.toml` entry points
- `src/projectlore/onboarding.py`, `integration.py`, `doctor.py`, `removal.py`
- Client, sidecar, removal, and installed-entrypoint tests

### Ordered changes and invariants

1. Add the accepted five-tool read-only acquisition sidecar. Its reads load one
   validated generation and never scan, acknowledge, review, repair, or write.
2. Preserve the core 0.4 registry and response bytes. Sidecar failure does not
   change core answers.
3. Render literal project-scoped Claude/Codex configuration using executables
   resolved from the same installed distribution. Journal per-file before/after
   hashes; settings/hooks are written only after prerequisites.
4. Report `ready`, `partial`, `conflict`, hook inactive, overflow, and recovery
   states honestly in onboarding status and doctor.
5. Extend existing `lore remove` compatibly and add preview-digest-bound repair/
   compact behavior. Preserve accepted YAML and verify core query equivalence.

### Verification, recovery, and completion

- MCP wire/schema/pagination/provenance/no-write tests pass.
- Literal client configs parse; command resolution works from an installed wheel;
  every integration write prefix supports resume or hash-safe compensation.
- Removal, drift, corrupt/fork repair/refusal, compaction, and query-equivalence
  tests pass.
- Completion: both project configurations start the same sidecar contract in
  deterministic fixtures, and complete removal leaves canonical model answers
  unchanged.

### Non-goals

No user-global configuration, hosted server, or write-capable MCP tool.

## Phase 5 - Prove the candidate and decide support claims

### Objective

Verify R10 and convert experimental limits/support claims into measured release
claims without delaying core implementation.

### Targets

- Build/distribution verification scripts and the accepted pinned corpus
- Candidate evidence under a noncanonical evidence directory
- README/getting-started/release documentation

### Ordered work

1. Build wheel/sdist from a clean candidate and bind hashes, dependency locks,
   wheelhouses, fixture bytes, source tree, and contract version.
2. Run the installed wheel offline with OS-level network denial; prove no
   Fraimed, CodeGraph, vendor credentials, or source checkout dependency.
3. Run boundary/resource measurements and either retain or revise experimental
   P05 values through a separately reviewed contract change.
4. Exercise each available OS/client support cell selected for the alpha using literal project
   configuration and a preauthenticated real client. Timeout, indeterminate,
   missing, duplicate, or wrong-version evidence is non-pass.
5. Run the full suite, schema/example checks, packaging inventory, removal, and
   the real edit-to-rediscovery product E2E. Repair the adjacent terminology
   allowlist independently rather than weakening it.
6. Document only the versions/platforms actually proven. Do not infer historical
   minima from current documentation.

### Rollback and completion

- A failed support cell removes that support claim; it does not roll back a
  locally correct implementation.
- A failed safety, privacy, canonical-consistency, or offline-core check blocks
  candidate readiness and returns to the owning phase.
- Completion: all 27 governing rows pass against the exact candidate, all
  selected support cells succeed, and no unexplained skip or tracked diff
  remains.

## Readiness

The technical sequence is executable and every governing requirement has an
implementation and proportional verification path. Candidate-bound evidence is
correctly deferred to Phase 5 rather than treated as a preimplementation fact.

**Current outcome: Ready to implement.** The governing requirements are covered,
the agent-facing evidence-to-proposal path is explicit, and no demonstrated
in-scope blocker remains. Experimental limits and platform/version support are
validated and narrowed in Phase 5 rather than used as preimplementation gates.
