# ProjectLore knowledge acquisition plan — reviewed amendment

Plan ID: `projectlore-knowledge-acquisition`

Plan version: `1.1.0`

Status: frozen for independent review

Plan author: Codex primary agent

Decision authority: ProjectLore owner

## Exact plan composition

This is a normative, self-identifying amendment to
`docs/plans/knowledge-acquisition-v1.md` at raw-byte
`sha256:9cd6821a0578c4b24d6748966d94942c9ad4b3e08bbbd4cae9abbe39cf09fca0`.
The base plan's requested outcome, authority, repository identity, requirements
R01-R20 except the replacement text below, facts F01-F14, risks K01-K18 except
the replacement text below, and phase sections except the replacement text
below remain normative. This amendment is applied after the base; on conflict,
this file supersedes it. Both exact files are required delivery artifacts and
must be read before implementation.

This composition preserves the failed 1.0.0 bytes and detached review rather
than rewriting history. The 1.0.0 review found five issues: KA-REV-001 through
KA-REV-005. This version accepts all five and resolves them below.

Repository baseline remains
`7354658a7e1424f18fdc5228e942371a781dc8af`, with the same included worktree
identity and unrelated-file exclusion recorded in the base plan. Before
implementation, recompute the base-plan digest, this amendment's digest, all
pinned source hashes, and the worktree identity. Semantic drift invalidates the
plan package.

## Finding disposition ledger

| Finding | Disposition | Governing evidence | Resolution in 1.1.0 |
| --- | --- | --- | --- |
| KA-REV-001 | Accepted | Recursive multi-file loader and request refresh permit reads between replacements. | Immutable versioned indexes/fragments plus one atomic root activation; cross-process writers serialize through an atomic directory lock. |
| KA-REV-002 | Accepted | One global core tool contract changes every existing response digest. | Acquisition uses a separate read-only `projectlore-knowledge-mcp` server and independently versioned contract; core 0.4 server/tool bytes remain unchanged. |
| KA-REV-003 | Accepted | No detector can prove arbitrary source excerpts contain no secret. | Source packets persist metadata and hashes only—never source excerpts. Proposal validation detects known credential shapes, while the requirement is narrowed to an observable boundary. |
| KA-REV-004 | Accepted | Baseline claimed `reviewed` without an operation or receipt. | The shared digest-bound `KnowledgeReview` contract moves to Phase 1 and an explicit onboarding review transition moves into Phase 2. |
| KA-REV-005 | Accepted | Initial plan lacked detached review and manifest. | 1.0.0 historical review/manifest are preserved; this exact version receives its own detached review and manifest after grading. |

No finding requires a product decision: each is resolved through repository
contracts and the decision-resolution ladder.

## Replacement decisions

These rows replace D04, D06, and D07 in the base plan.

| ID | Question | Ladder evidence consulted | Alternatives and consequences | Recommendation | Classification | Authority/citation |
| --- | --- | --- | --- | --- | --- | --- |
| D04 | How can accepted additions activate without exposing a multi-file intermediate state? | Loader reads explicit nested includes; refresh can run concurrently; canonical YAML must remain Git-tracked and human-readable. | Mutating a stable index and root creates two activation points; immutable indexes referenced by one root replacement create one. | Each transaction writes immutable content-addressed fragments and a new immutable versioned index unreferenced, validates a staged root, then atomically replaces only the root entrypoint to update both index reference and model version. Retain prior indexes/fragments. | Recommended engineering choice | `loader.py:79-174`; `refresh.py:37-75`; KA-REV-001 |
| D06 | How can agents read acquisition state without changing the frozen core MCP contract? | One core 0.4 version/digest covers all eight tools; adding any schema changes existing envelopes. | Same-server addition breaks R14; CLI-only weakens integration; a sidecar preserves both. | Register a second project-scoped, read-only `projectlore-knowledge-mcp` with `projectlore-acquisition-tools/0.1.0`. It shares local acquisition parsers but no core contract/version/digest. | Resolved by evidence | `tool_spec.py:7`; `query.py:13-52`; KA-REV-002 |
| D07 | What repository content may acquisition persist? | Files may contain unknown credentials even when tracked/public-looking; prompts/transcripts/tool output are private hook fields. | Excerpts improve convenience but cannot meet the privacy proof; path/hash metadata lets the already-authorized agent read sources directly. | Packets/signals persist root-relative paths, kind, size, Git status, content hash, and optional line-number targets only. They persist no source bytes/excerpts. Proposal prose is agent-authored and rejected when known credential patterns appear; no claim detects every possible secret. | Recommended engineering choice | Security invariants; KA-REV-003 |

Decision reconciliation replaces the base count: 10 total; 4 Resolved by
authority, 3 Resolved by evidence, 3 Recommended engineering choice, 0 Genuine
human decision.

## Replacement requirements

These rows replace R08, R12, R14, and R15. All other requirement rows and their
coverage remain unchanged.

| ID | Exact authority location | Required outcome or absence | Plan phase/step | Verification obligation | Status |
| --- | --- | --- | --- | --- | --- |
| R08 | Product vendor-neutrality invariant | Claude Code and Codex consume one portable packet/proposal contract and one independently versioned acquisition MCP contract. | P1, P4, P5 | Cross-client normalized events/packets/proposals are equal; both clients use the same sidecar schemas. | Covered |
| R12 | MCP read-only invariant | Both the core MCP and acquisition sidecar are read-only; neither writes canonical, proposal, cursor, signal, or review files. | P5.1-P5.5 | Filesystem snapshots around every tool and malformed call prove no writes; scan/review/apply exist only in CLI/hooks. | Covered |
| R14 | Existing public alpha contracts | `lore init`, all eight `projectlore-tools/0.4.0` schemas/envelopes/digests, existing models, and integrations retain documented meaning. Acquisition is a separate `projectlore-acquisition-tools/0.1.0` server/config entry. | P1.5, P2.7, P5.1-P5.5, P6.1 | Frozen 0.4 runtime schemas and full response fixtures remain byte/normalized-value identical; acquisition sidecar has independent fixtures and digest. | Covered |
| R15 | Product privacy/trust boundary | ProjectLore acquisition never persists source-file bytes/excerpts, prompt or transcript content, tool inputs/responses, environment values, ignored-file metadata, or known credential-shaped proposal values. | P1.2-P1.4, P2.1, P4.1-P4.4 | Inspect every acquisition artifact in canary corpora; prove forbidden hook fields and source excerpts absent; prove known credential patterns reject/quarantine proposals. Explicitly do not claim detection of every possible secret. | Covered |

Requirement reconciliation remains 20 unique requirements; 20 Covered; 0
Excluded, Decision needed, Fact blocked, or Unverifiable.

## Replacement risks

These rows replace K02, K04, K09, and K14. All other risk rows remain
normative.

| ID | Scenario | Boundary | Prevention/detection | Recovery/rollback | Proof | Owner/status |
| --- | --- | --- | --- | --- | --- | --- |
| K02 | Acquisition duplicates sensitive source or agent-session content. | Hooks/scanner/packets/proposals | Persist metadata/hash only; never dereference transcript paths; discard hook prose/tool fields; exclude ignored paths before metadata; reject known credential patterns in agent-authored proposal strings. | Quarantine rejected local proposal; preview-first purge local state; use repository incident/rotation process if an agent itself authors a missed secret. | Byte-inspect all artifacts with source, prompt, transcript, tool, environment, ignored-file, and credential canaries; document the detector limitation. | Implementer + security reviewer / Covered |
| K04 | Concurrent hooks or applies corrupt queues or lose canonical additions. | Local signal persistence and canonical writer | Signals are immutable content-addressed files. Canonical apply acquires an atomic `mkdir` lock under `.projectlore/knowledge/apply.lock`, records a nonce/owner/time, then rechecks every digest under lock. Lock acquisition is bounded and never auto-breaks a possibly live lock. | Hook contention exits advisory. Apply contention fails without writes. Crash recovery inspects nonce, process/time evidence, root transaction, and unreferenced immutable files through an explicit `lore knowledge recover` preview/apply; it never guesses stale ownership. | Multiprocess hook/apply stress, same-base competing proposals, crash at every boundary, and lock recovery tests on Windows/Linux/macOS. | Implementer / Covered |
| K09 | Existing init/core MCP/model consumers break. | Public contracts/config | Keep `lore init` behavior; keep core MCP source, 0.4 tool map, version, digest, and responses unchanged; independently version onboarding/acquisition/proposal and sidecar MCP contracts. | Remove/disable the sidecar acquisition MCP and hooks; core server and canonical accepted model remain usable. | Golden 0.4 full-response fixtures, runtime-schema equality, separate sidecar contract tests, full regression. | Implementer / Covered |
| K14 | Accepted multi-file transaction is partially visible or a competing writer loses an update. | Canonical promotion | Under cross-process lock, write/fsync immutable fragment and versioned index to final content-addressed paths, create/validate staged root that changes index reference plus model version, recheck base root digest, then perform one same-directory atomic `os.replace` of the root. Old/new readers reference only immutable complete graphs. Never delete old indexes/fragments during apply. | Before root replace, failure leaves old root authoritative and unreferenced immutable files recoverable. After root replace, the new complete graph is authoritative; recovery only clears the lock and reports unreferenced files. Git revert atomically restores a prior root reference in its own reviewed change. | Reader/writer interleaving across every file open; two competing apply processes; Windows replacement failure; crash before/after root replace; direct loader, CLI, and MCP refresh observations; assert only old-complete or new-complete digest/version pairs. | Implementer / Covered |

Risk reconciliation remains 18 unique risks; all 18 have prevention, recovery,
proof, and owner.

## Phase 1 amendments — review contract and privacy contract

Replace Phase 1 steps 1-5 with:

1. Define independent strict contracts for acquisition session, metadata-only
   source manifest, signal, packet, proposal, candidate, conflict,
   `KnowledgeReview`, apply preview, transaction, and recovery receipt. Every
   object has an independent version, content digest, repository/base-model
   identity, trigger, explicit state, and deterministic ordering.
2. Restrict candidate status to `suggested` or `inferred`. Evidence contains
   only root-relative path, source kind, exact content hash, size, and optional
   line-number scope—never source text. Candidate prose is bounded and scanned
   for the repository's existing credential shapes plus structured token and
   high-entropy detectors; uncertain matches are quarantined with a stable
   diagnostic. Document that this reduces accidental persistence but is not a
   proof that arbitrary prose contains no undiscovered secret.
3. Define `KnowledgeReview`: it binds proposal, packet, source-manifest,
   base-model and reviewer-decision-file digests; records an actor-declared
   identity and rationale; and requires exactly one `accept`, `reject`, or
   `revise` decision for every candidate. It is a local review receipt, not
   authentication or authorization. A proposal becomes `reviewed` only when all
   candidates have decisions and none remains `revise`; apply still requires
   explicit repository task authority and normal Git review.
4. Persist disposable state beneath `.projectlore/knowledge/` as immutable
   content-addressed records with root/symlink/size/count/depth bounds. Signals
   use independent files, not an append log. Define atomic directory-lock
   protocol, completion marker, quarantine, recovery states, and cancellation.
5. Freeze compatibility/hostile fixtures and prove canonical services plus the
   core 0.4 MCP are unchanged by any local state. Package contracts do not enter
   the canonical schema unless the canonical model itself changes.

Add to the Phase 1 exit gate: the shared review state machine has transition
and replay tests; privacy tests prove all forbidden input/source fields absent
from raw emitted bytes; a review confirms claims do not exceed detector scope.

## Phase 2 amendments — explicit baseline review

Replace Phase 2 steps 1-6 with:

1. Build a Git-aware source inventory that persists metadata/hash only. It may
   read bytes transiently to classify binary/text, compute hashes, and locate
   line-number targets, but must not persist source bytes. It excludes ignored,
   VCS, generated, vendor, and local-state paths before recording metadata and
   applies deterministic bounds/cancellation.
2. `lore onboard start --name NAME` creates only a local session and metadata
   packet. Status is `not_started`, `packet_ready`, `proposal_ready`,
   `review_incomplete`, `reviewed`, `applied`, or `stale`, and reports exact
   reasons, unknown/conflict counts, and hook availability without implying
   authority.
3. The portable packet instructs the active agent to read prioritized sources
   through its already-reviewed repository access and author a proposal for
   purpose, domains, terminology, concepts, relationships, accepted Rules,
   sources, authority, anchors, contradictions, and unknowns. Evidence must
   match packet metadata hashes/ranges. ProjectLore itself calls no model.
4. `lore knowledge propose PROPOSAL.json` validates packet/base/source identity,
   metadata evidence, candidate status, bounds, credential detectors,
   duplicate/conflict classifications, and source drift. A valid proposal moves
   status only to `proposal_ready`.
5. `lore onboard review --proposal-digest DIGEST --decisions FILE --actor ID`
   validates the Phase 1 `KnowledgeReview` contract. Missing candidate
   decisions yield `review_incomplete`; any `revise` returns to proposal work;
   only a complete digest-bound receipt yields `reviewed`. Actor identity is
   explicitly self-declared and does not replace repository authorization.
6. `onboard preview --review-digest DIGEST` renders the entire initial model,
   immutable versioned acquisition index/fragments, and integration files. It
   reports every accepted/rejected item, authority, conflicts, unknowns,
   validation, and before/after digests. It refuses unresolved material
   conflicts or Rules without accepted evidence/authority.
7. `onboard apply --preview-digest DIGEST --actor ID` rechecks every byte and
   uses the same single-root activation protocol as Phase 3. Existing
   `lore init` remains skeleton-only and behavior-compatible.

Phase 2 verification additionally covers every status transition, incomplete/
revised/replayed reviews, self-declared actor messaging, and raw-artifact
privacy inspection. Its exit gate requires a complete review receipt.

## Phase 3 amendments — single-root activation

Replace Phase 3 steps 1 and 3-7 with:

1. New onboarded roots explicitly include an immutable versioned index such as
   `projectlore/knowledge/indexes/<digest>.yaml`; each index includes the full
   ordered set of immutable accepted fragment paths. Existing repositories get
   a one-time digest-bound preview that writes an empty immutable index and then
   atomically replaces only the root to add its reference. Unsupported YAML
   formatting receives a manual patch and no write.
2. Reuse the base plan's deterministic candidate comparison/classification.
3. Reuse Phase 1 `KnowledgeReview` for ongoing candidates through
   `lore knowledge review`; no second review meaning is invented.
4. Under the cross-process atomic-directory lock, preview/apply prepares a new
   immutable fragment and a new immutable full index, both content-addressed.
   It prepares a staged root whose single edit changes the prior versioned-index
   include to the new path and increments `model_version`. Preview binds all
   source, proposal, review, root, old-index, new-index, and fragment digests and
   shows the complete Git diff.
5. Apply reacquires the lock, rechecks all base bytes, writes/fsyncs fragment and
   index unreferenced, validates the staged complete model from within the same
   repository boundary, rechecks the root once more, and performs exactly one
   same-directory atomic replacement of the root. That root replacement is the
   sole activation point. No apply deletes prior immutable files.
6. All supported readers first read one root snapshot and then follow only its
   immutable index/fragments. Interleaving tests must prove readers observe
   either the complete old graph/version or complete new graph/version, never a
   mix. A second writer cannot pass the lock/base-digest recheck.
7. `lore knowledge recover` inspects abandoned locks and unreferenced immutable
   files through preview/apply; it never automatically breaks a lock. Export/
   import remains non-authoritative and content-addressed.

Replace Phase 3 rollback: before root replacement, old root remains
authoritative and new immutable files are harmless/unreferenced. After root
replacement, the complete new graph is authoritative. Recovery clears only a
proven abandoned lock and may propose cleanup separately; old indexes/fragments
are retained for reader safety and Git history. A normal reviewed Git revert
restores a previous root reference/version.

Replace the Phase 3 exit gate: direct loader, CLI, long-lived MCP, and competing
processes observe only old-complete or new-complete state across fault injection
at every boundary; no supported reader relies on a mutable stable index.

## Phase 4 amendments — metadata-only signals

In Phase 4 steps 1-4, replace any implication of excerpt/content persistence
with the following:

- The hook discards all event fields except event name, bounded `cwd`, session
  discriminator used only for in-process dedupe, and `stop_hook_active` safety;
  it does not persist the session identifier.
- Stop scans Git state directly and persists only qualifying root-relative path,
  Git status, size, content hash, qualification reason, HEAD and model identity.
- It never dereferences transcript paths or persists last assistant messages,
  prompts, tool inputs/responses, environment values, source bytes, or ignored
  path metadata.
- Hook errors/cancellation/lock contention remain advisory and cannot break a
  canonical apply lock or claim a completed scan.

Extend Phase 4 verification to inspect raw signal/packet bytes against every
forbidden hook field and to test a concurrently held canonical apply lock.

## Phase 5 replacement — separate acquisition MCP sidecar

Replace Phase 5 in full.

Objective: expose acquisition status and immutable packets/proposals through a
separate read-only MCP without altering ProjectLore's frozen core eight-tool
contract. Covers R03, R05, R08, R11-R12, R14-R15, R20.

Entry conditions: Phases 1-4 define immutable local reads and passive signals;
the sidecar contract has its own compatibility record.

Targets:

- new `src/projectlore/knowledge_tool_spec.py` with
  `projectlore-acquisition-tools/0.1.0`;
- new `src/projectlore/knowledge_mcp_server.py` and console entrypoint
  `projectlore-knowledge-mcp`;
- shared read-only acquisition query service;
- `onboarding.py`, doctor/trust/removal, client capability JSON, managed
  instructions, sidecar fixtures/tests;
- no semantic edit to `tool_spec.py`, `mcp_server.py`, or existing core query
  response construction.

Ordered steps:

1. Define sidecar tools `knowledge_status`, `knowledge_get_packet`, and
   `knowledge_get_proposal` with exact independent schemas, version, and digest.
   Status distinguishes missing, empty, pending, stale, conflict, and reviewed.
   Content reads require IDs and return bounded structured metadata/proposal
   prose with trigger/base/source/provenance digests. They do not return source
   bytes.
2. Build the sidecar from a read-only state service that opens immutable records
   without advancing cursors, creating packets, scanning, reviewing, applying,
   deleting, compacting, or recovering. Malformed/quarantined records return
   diagnostics without mutation.
3. Generate a separate project MCP entry named `projectlore_knowledge` for both
   clients, preserving the core `projectlore` entry exactly. Both entries need
   explicit client trust. Doctor reports core and acquisition readiness
   independently; core readiness never depends on the sidecar.
4. Update managed instructions: check acquisition status at task start; use
   packet metadata to read repository evidence; author portable candidate JSON;
   invoke mutation CLI only with task authority; never treat proposals as
   canonical. Keep within instruction budgets and respect nested overrides.
5. Freeze the entire core 0.4 oracle: version, tool names, schemas, contract
   digest, and representative full responses. Sidecar runtime schemas must
   exactly equal only their independent normative schemas. Filesystem snapshots
   prove all tools on both servers are read-only.

Verification: independent sidecar schema equality and transport smoke; core
0.4 byte/normalized fixtures; found/empty/missing distinctions; output/privacy
bounds; two-server configuration preservation/trust/removal; CLI-sidecar parity;
real Claude/Codex discovery of both servers; failure of sidecar leaves core MCP
healthy.

Rollback: remove/disable only `projectlore_knowledge` and its managed guidance;
core MCP and CLI acquisition remain usable. No canonical model changes.

Non-goals: write-capable MCP, same-server contract negotiation, core response
changes, MCP-triggered scanning, or candidate data in canonical tools.

Exit gate: core 0.4 fixtures remain exact; both clients read the same sidecar
packet/proposal; no MCP read mutates any byte; sidecar failure does not affect
core startup or answers.

## Phase 6 amendments — package and acceptance corrections

Replace “all five console entrypoints” with all six expected entrypoints:
`lore`, `projectlore-mcp`, `projectlore-hook`,
`projectlore-scope-hook`, `projectlore-knowledge-hook`, and
`projectlore-knowledge-mcp`.

Add the following acceptance obligations:

- cross-process reader/writer and two-writer tests certify the one-root
  activation boundary on Windows, Linux, and macOS;
- core 0.4 responses/digest remain exact while sidecar 0.1 starts separately;
- raw acquisition artifacts contain no source excerpts or forbidden hook fields,
  and known credential-shaped proposals are rejected; the report does not claim
  universal secret detection;
- onboarding cannot reach `reviewed` without a complete digest-bound
  `KnowledgeReview`, and apply requires that exact review/preview identity;
- installation/removal handles both MCP servers and both new/existing hooks,
  while canonical accepted fragments remain reviewable Git files.

The independent `author-tests` gate remains required before implementation and
must include R01-R20, K01-K18, and these corrected observable boundaries.

## Corrected final reconciliation

- Requirements: 20; all Covered.
- Risks: 18; all dispositioned with prevention, recovery, proof, and owner.
- Decisions: 10; 4 Resolved by authority, 3 Resolved by evidence, 3 Recommended
  engineering choice, 0 Genuine human decision.
- Phases: the same six dependency/proof gates, with Phases 1-6 amended above.
- Open product decisions: 0.
- Accepted limitation: local rejected/pending memory is disposable; source
  packets are metadata-only; secret-pattern validation is defense-in-depth, not
  universal secret detection; accepted knowledge is shared through Git.
- Implementation remains prohibited until this exact composed plan receives a
  detached Ready review and handoff manifest.
