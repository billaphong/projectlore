# ProjectLore knowledge acquisition plan — passive lifecycle amendment

Plan ID: `projectlore-knowledge-acquisition`

Plan version: `1.3.0`

Status: frozen for independent review

Plan author: Codex primary agent

Decision authority: ProjectLore owner

## Exact composition and precedence

The plan is the following ordered composition; each later file supersedes every
earlier conflict:

1. `docs/plans/knowledge-acquisition-v1.md` —
   `sha256:9cd6821a0578c4b24d6748966d94942c9ad4b3e08bbbd4cae9abbe39cf09fca0`
2. `docs/plans/knowledge-acquisition-v1.1.md` —
   `sha256:742408423f501243dc8be46a1dcd6631f239d5b55bb696ce880b2e3c39846130`
3. `docs/plans/knowledge-acquisition-v1.2.md` —
   `sha256:0cd71d22946362c758737c83a63bf70a6c0c5084a8b08db3c05e98312368480c`
4. this 1.3.0 amendment, applied last

All unaffected requirements R01-R20, risks K01-K18, decisions D01-D10, facts
F01-F14, and phase details remain normative. All four plan components must be
delivered and read.

The independent 1.2 review at
`sha256:cc152188fdd143a72cac1cc48b2d109a52dd55f88c8d671a6082c31f849ce563`
scored 81/100. It confirmed the canonical, compatibility, privacy, review, and
integration transaction corrections but found the missing signal-to-packet
lifecycle, a Phase 2/3 dependency cycle, incomplete worktree classification,
and the expected current-version packaging step. All are accepted.

## Complete planning-worktree classification

Implementation baseline source is commit
`7354658a7e1424f18fdc5228e942371a781dc8af` plus the in-scope tracked diff Git
object `47168b837b2b31b6172fb2c45fe764b511ea5acc` and in-scope untracked
`docs/agent-onboarding.md` at
`sha256:9ade467009b462bf98680de9672a8d5ea96932c55a1e3d3f16ef300a257ae4ce`.
The unrelated untracked `docs/maintain-projectlore-model-skill.md` at
`sha256:be3621a1bb50a2f2ba4e0bcc68dfe2947756307e876d229ed677e49914a9b05f`
is excluded and must remain untouched.

The following historical plan-package artifacts are excluded from
implementation source behavior but included as immutable review evidence:

| Path | Raw-byte SHA-256 |
| --- | --- |
| `docs/plans/knowledge-acquisition-v1.md` | `9cd6821a0578c4b24d6748966d94942c9ad4b3e08bbbd4cae9abbe39cf09fca0` |
| `docs/plans/knowledge-acquisition-v1.review.md` | `90d7dfb74d9fcee3dcec7c8bd3f3ec8b40713747ea5fd2eac07d2d706e783baf` |
| `docs/plans/knowledge-acquisition-v1.handoff.json` | `53a77d1e7cd56318c9e15334715a6733329ed801e7ccded5278a4efa6f54b3a2` |
| `docs/plans/knowledge-acquisition-v1.1.md` | `742408423f501243dc8be46a1dcd6631f239d5b55bb696ce880b2e3c39846130` |
| `docs/plans/knowledge-acquisition-v1.1.review.md` | `dad0030561aea0b984f976fc111de4a45f3105f00ca16b4e3379d7fc9d34e4fb` |
| `docs/plans/knowledge-acquisition-v1.1.handoff.json` | `6be5abaaf3916e9821ccedcfd25e8dda448257865bba0ece5b190a875f9544a4` |
| `docs/plans/knowledge-acquisition-v1.2.md` | `0cd71d22946362c758737c83a63bf70a6c0c5084a8b08db3c05e98312368480c` |
| `docs/plans/knowledge-acquisition-v1.2.review.md` | `cc152188fdd143a72cac1cc48b2d109a52dd55f88c8d671a6082c31f849ce563` |
| `docs/plans/knowledge-acquisition-v1.2.handoff.json` | `77be88951933203a006fb6d2b5d0685b62ee9b62d67c7d487cde54e894c2057e` |

This current plan file and its eventual detached review/manifest are delivery
artifacts, not implementation source input; their exact hashes are recorded in
the 1.3 handoff manifest after review. Before implementation, a deterministic
inventory must show no unclassified path: tracked source matches the recorded
diff or accepted successor commit, the onboarding guide is included, the skill
draft remains excluded, and every `docs/plans/knowledge-acquisition-*` path is
named by a verified historical or current handoff manifest. Any other untracked
path blocks entry.

## Finding disposition ledger

| Finding | Disposition | Resolution |
| --- | --- | --- |
| KA-REV12-001 | Accepted | Phase 4 now owns a complete deterministic signal-to-packet state machine. SessionStart materializes the next packet automatically; CLI invokes the identical fallback. Complete packets acknowledge immutable signals by inclusion, eliminating a mutable cursor. |
| KA-REV12-002 | Accepted | Phase 2 explicitly implements and verifies the shared canonical transaction engine before onboarding invokes it; Phase 3 only reuses it. |
| KA-REV12-003 | Accepted | The complete implementation, unrelated, historical-review, and current-package worktree classes are pinned above, with an entry gate that rejects any unclassified path. |
| KA-REV12-004 | Accepted | Preserve the 1.2 review/manifest and create/verify the exact 1.3 review/manifest after grading. |

## Replacement requirements

Replace R02, R03, R10, and R20 with:

| ID | Exact authority location | Required outcome or absence | Plan phase/step | Verification obligation | Status |
| --- | --- | --- | --- | --- | --- |
| R02 | Owner direction 1 | Ordinary work automatically creates a bounded signal and, at the next trusted SessionStart, a deterministic agent-consumable packet without user action or model-provider calls. | P4.1-P4.10 | Real-client edit→Stop signal→SessionStart packet flow; CLI fallback is identical when hooks are unavailable. | Covered |
| R03 | Owner directions 1-2 | The active agent receives a portable packet, reads cited repository evidence through existing authorization, and authors a structured proposal. | P1, P2, P4.7-P4.10, P5 | Independent Claude/Codex pilots consume the same packet identity and produce schema-valid proposals. | Covered |
| R10 | Owner direction 1 | Signal/packet/proposal lifecycle deduplicates, merges, retries, detects drift/conflict/staleness, and recovers overflow without silently losing distinct current knowledge evidence. | P1, P3, P4.2-P4.9 | Repeated/concurrent/overflow/drift/crash fixtures prove exact coverage and no unacknowledged signal deletion. | Covered |
| R20 | Handoff expectation | Any agent receives the pending packet ID and exact next action from SessionStart/status, and can complete proposal/review/apply without a private prompt. | P4.7-P4.10, P5, P6 | Clean-agent E2E progresses from ordinary edit to canonical rediscovery with no user scan/capture command. | Covered |

Requirement reconciliation remains 20 total, all Covered.

## Replacement risks

Replace K06, K15, and K17 with:

| ID | Scenario | Boundary | Prevention/detection | Recovery/rollback | Proof | Owner/status |
| --- | --- | --- | --- | --- | --- | --- |
| K06 | Repeated/concurrent sessions create duplicate packets/proposals or starve old signals. | Signal→packet→proposal | Immutable content-addressed signals/packets; complete packet records sorted signal IDs; eligibility is set difference rather than mutable cursor; deterministic oldest-first bounded batch; existing non-stale packet/proposal suppresses duplicates. | Recompute eligibility from immutable records; quarantine malformed records; no signal is deleted by materialization. | Concurrent SessionStart, repeated retry, stale packet, and ordering tests. | Implementer / Covered |
| K15 | Local packet/rejection history is absent on another machine or queue overflow loses the useful current state. | Disposable team workflow | Accepted knowledge is shared in Git. Local records are content-addressed/exportable. Overflow never deletes distinct unpacketized signals; it sets a bounded overflow marker and requires a full-reconciliation packet from the last completed packet revision (or onboarding baseline) through current HEAD/worktree. | Fresh clone rescans/deduplicates against canonical model; overflow reconciliation supersedes covered signals only after a complete packet exists. | Fresh-clone, capacity, commit-between-sessions, and full-reconciliation tests. | Product owner / Accepted local-history limitation, Covered current-state recovery |
| K17 | Cancellation/crash loses signals, falsely acknowledges a packet, or leaves misleading onboarding state. | Signal, packet, review, canonical/integration apply | Immutable records; packet completion marker last; acknowledgement derives only from signal IDs in valid complete packets; no cursor mutation; source/status hashes rechecked before completion; existing transaction markers for apply. | Incomplete temp/record is ignored/quarantined; same eligible signals deterministically retry; stale packet makes signals eligible again; integration/canonical recovery remains as 1.2. | Fault/cancellation at every signal/packet/apply boundary and idempotent retry. | Implementer / Covered |

Risk reconciliation remains 18 total, all dispositioned.

## Phase 2 dependency correction

Amend Phase 2 entry and targets from 1.2:

- Phase 2 does not depend on Phase 3 implementation.
- Add `src/projectlore/knowledge_apply.py` as a Phase 2 target.
- Before implementing `onboard preview-knowledge` or `apply-knowledge`, Phase 2
  implements the complete shared `CanonicalKnowledgeTransaction` engine from
  the 1.1 single-root design: cross-process atomic-directory writer lock;
  immutable content-addressed fragment/full-index staging; staged-root complete
  validation; under-lock base digest recheck; exactly one same-directory atomic
  root replacement; transaction/recovery diagnostics; old artifact retention;
  direct-loader/CLI/MCP reader interleaving and competing-writer tests.
- The engine supports both absent-root initial activation and existing-root
  versioned-index replacement. Initial activation writes the root last through
  atomic rename; existing activation replaces it atomically.
- Phase 2 steps 5-6 invoke this already passing engine. Phase 2 exit evidence
  includes its complete transaction tests plus baseline onboarding.

Replace Phase 3 entry condition with: Phase 2 has delivered and proven the
shared canonical transaction engine and initial baseline/index layout. Phase 3
adds ongoing classification/review/promotion commands by reusing the engine; it
does not implement or redefine transaction semantics.

Rollback ownership: transaction-engine rollback/recovery belongs to Phase 2;
Phase 3 owns only ongoing proposal classification and CLI orchestration.

## Complete Phase 4 replacement — passive signal-to-packet lifecycle

Replace Phase 4 in all prior components with this phase.

Objective: turn ordinary repository work into an immutable agent-consumable
packet automatically and non-blockingly, while preserving a deterministic CLI
fallback. Covers R02-R03, R08-R10, R13-R16, R18-R20.

Entry conditions: Phase 1 signal/packet contracts and local state are frozen;
Phase 2 canonical transaction exists; Phase 3 proposal/review/promotion can
consume a valid packet; current official hook contracts have been revalidated.

Targets:

- `src/projectlore/knowledge_hook.py` for Stop/SessionStart dispatch;
- new `src/projectlore/knowledge_packets.py` as the sole signal-selection and
  packet-materialization service;
- CLI `lore knowledge packet next|status` using that same service;
- package entrypoint, generated hooks, doctor/trust/removal/capability metadata;
- signal/packet lifecycle, concurrency, overflow, privacy, and real-client tests.

Ordered steps:

1. The shared hook accepts only bounded JSON, confines `cwd`, sanitizes its
   environment, ignores/drops transcript, message, prompt, tool, response, and
   environment payloads, and dispatches only Stop or SessionStart. It never
   blocks either event and performs no network/model call.
2. Stop computes current Git-status/source metadata delta from the last complete
   signal state and writes one immutable content-addressed signal containing
   root identity, HEAD, model digest, qualifying root-relative path/status/size/
   hash/reason, and observed time. Identical signal content deduplicates. The
   hook writes completion last; operational failures exit advisory 0.
3. Signals are never deleted or mutated by packet creation. A complete packet
   contains an ordered non-empty `covered_signal_ids` tuple. A signal is eligible
   exactly when no valid complete, non-stale packet for the same repository has
   covered its ID. This set-derived acknowledgement replaces a mutable cursor.
4. Under a bounded atomic-directory packet lock, `materialize_next_packet`
   loads/quarantines bounded records, sorts eligible signals by normalized
   observation time then ID, and selects the oldest prefix within configured
   signal/path/byte limits. Concurrent callers either observe the created packet
   or retry from the same immutable eligibility set; lock contention is
   advisory at SessionStart and an actionable CLI diagnostic.
5. Merge selected signals by normalized path while retaining every contributing
   signal ID and old hash/status. Re-read current Git HEAD/worktree and metadata-
   only path/status/size/hash for their union. Deleted/missing paths are explicit.
   Recheck HEAD, Git status digest, model digest, and all current path hashes
   immediately before completion; any drift discards the incomplete attempt and
   leaves all signals eligible.
6. Packet identity hashes repository/model/base identities, ordered covered
   signal IDs, current source-manifest digest, trigger `passive_session`, and
   truncation/overflow state. Write immutable packet bytes and completion marker
   atomically. A packet becomes stale when its base model or any current evidence
   hash no longer matches; its signals become eligible for a new packet unless
   a later complete packet covers them with current evidence. Proposal creation
   never mutates acknowledgement state.
7. On each trusted SessionStart, the hook first returns an existing oldest
   complete non-stale packet without a proposal; otherwise it invokes the exact
   bounded `materialize_next_packet` service. It emits only packet ID, counts,
   status, and the next action to agent context. If materialization exceeds the
   hook budget/fails, it emits the exact CLI fallback
   `lore knowledge packet next`; it does not claim completion.
8. `lore knowledge packet next` calls the identical service with a larger
   documented local timeout, returns the same packet ID for the same state, and
   never scans beyond the selected signal evidence. This is a fallback for
   disabled/untrusted hooks, not a required user step in the default flow.
9. At signal-capacity, Stop does not delete/overwrite distinct unpacketized
   signals. It atomically sets a fixed bounded overflow marker containing count,
   oldest/newest times, last completed packet repository revision (or onboarding
   baseline), current HEAD, and status digest. SessionStart/CLI materializes a
   `full_reconciliation` packet from Git changes between that base revision and
   current HEAD plus current worktree metadata, within packet bounds. If history
   is unavailable or truncated, packet status is `incomplete_history` and the
   agent receives an explicit broader rescan decision; it cannot claim coverage.
   Only a complete reconciliation packet may mark the overflow episode covered;
   original records remain until separate previewed compaction.
10. Managed instructions tell the active agent to read the packet through the
    acquisition sidecar, inspect the cited current repository paths, and author
    proposal JSON. Status distinguishes signal pending, packet ready, proposal
    ready/stale, overflow, incomplete history, and hook inactive. Doctor proves
    hook command resolution/trust but never equates passive activity with
    canonical acceptance. Removal deletes disposable records preview-first and
    preserves accepted YAML.

Verification:

- normalized native Claude/Codex Stop and SessionStart fixtures plus real current
  clients;
- ordinary Write/Edit/Bash/doc/schema/model/anchor changes, commit between
  sessions, clean worktree after commit, deleted/renamed paths, detached HEAD,
  subdirectory start, no-change session;
- concurrent Stop/SessionStart/CLI, lock contention, repeated calls, crash and
  cancellation before every completion marker, source/model/HEAD drift during
  materialization, malformed/quarantined records;
- deterministic oldest-prefix batching, overlap merge, stale packet
  re-eligibility, proposal retry without duplicate acknowledgement, queue bounds,
  overflow reconciliation, missing history, and previewed compaction;
- raw-byte privacy canaries and p95 budgets retained from the base plan;
- complete product E2E: ordinary edit → Stop signal → next SessionStart packet
  without manual scan → agent proposal → KnowledgeReview → canonical transaction
  → next core MCP request rediscovers accepted knowledge with provenance.

Rollback: disabling/removing the hooks stops passive capture only. Existing
signals/packets are disposable and can be preview-removed; CLI fallback remains.
No passive operation mutates canonical YAML, proposal review, or policy state.

Non-goals: background watcher, transcript parsing, embedded AI, blocking Stop,
network, automatic proposal acceptance, shared hosted cursor, or deletion of
distinct unpacketized evidence.

Exit gate: both real clients and deterministic fixtures complete the full E2E;
each valid signal is pending or covered by an inspectable complete packet;
failures retry without loss/duplication; no user scan/capture command is needed
on the trusted default path.

## Phase 5 and Phase 6 amendments

Phase 5 `knowledge_status` and `knowledge_get_packet` read the Phase 4 immutable
state and expose `covered_signal_ids`, stale/overflow/incomplete-history status,
source-manifest digest, and exact next action. They never materialize, acknowledge,
compact, or advance anything. Sidecar/CLI parity includes these fields.

Phase 6 adds the complete Phase 4 E2E to installed-wheel, offline, cross-platform,
real-client, removal, and independent acceptance evidence. A passing hook-only
test is insufficient. Pilot metrics include signal-to-packet latency, uncovered
signal age, packet/proposal duplicate rate, overflow/incomplete-history count,
proposal acceptance/rejection, and time to canonical rediscovery.

## Corrected reconciliation and implementation gate

- Requirements: 20 total; all Covered.
- Risks: 18 total; all dispositioned.
- Decisions: 10 total; 4 Resolved by authority, 4 Resolved by evidence, 2
  Recommended engineering choice, 0 Genuine human decision.
- Phases: 6 with acyclic ownership: Phase 1 contracts; Phase 2 canonical engine
  plus baseline onboarding; Phase 3 ongoing review/promotion; Phase 4 passive
  signal/packet lifecycle; Phase 5 sidecar; Phase 6 product proof.
- Open product decisions: 0.
- `author-tests` remains mandatory after a Ready plan package and before
  production implementation.
- Implementation is prohibited until this exact four-component plan receives a
  detached Ready review, a verified handoff manifest that names all four plan
  components plus review, and no unclassified worktree path remains.
