# Knowledge acquisition implementation contract 1.0

## Header

- Authorized outcome: implement the committed ProjectLore knowledge-acquisition
  plan, including baseline injection, passive growth, explicit review/promotion,
  read-only acquisition MCP, client integration, recovery, and product proof.
- Scope: phases 1-6 of the ordered plan composition ending at
  `docs/plans/knowledge-acquisition-v1.12.md`.
- Baseline revision: `5ba7233` (full revision pinned by the implementation
  evidence package before production edits).
- Authority order: repository `AGENTS.md`; user authorization in this session;
  committed ordered plan v1-v1.12 and its 99/100 detached review; architecture;
  current code as descriptive evidence.
- Candidate identity: Git tree plus detached manifest of any uncommitted test and
  production artifacts at each gate.
- Roles: contract author Codex root; clean-context test author commissioned
  independently; implementer Codex root; final verifier independently assigned.
- Open conflicts/product decisions: none. Publication, push, hosted mutation,
  network AI, and production fault injection remain unauthorized.

## Semantic invariants

| ID | Required invariant | Observable proof | Wrong implementation rejected |
| --- | --- | --- | --- |
| KA-01 | Git-tracked YAML remains the sole canonical knowledge source. | Queries ignore proposal/workflow state until reviewed canonical activation. | Read operation or proposal silently changes truth. |
| KA-02 | Initial onboarding deterministically creates a provenance-bearing baseline proposal before readiness. | New and existing project fixtures produce bounded metadata-only proposals and honest status. | Empty bootstrap claims ready or persists source excerpts. |
| KA-03 | Accept, reject, and revise are the only review dispositions and are digest-bound. | Contract/schema fixtures reject aliases, stale digests, and incomplete candidate decisions. | Actor declaration or preview implies authorization. |
| KA-04 | Canonical activation exposes a complete old or new graph through one root replacement. | Concurrent/fault tests never observe mixed generations. | Multi-file prefix becomes visible. |
| KA-05 | Passive Stop capture is metadata/hash-only, bounded, advisory, deterministic, and provider-free. | Privacy canaries, duplicate observations, disabled hooks, and offline runs. | Transcript/prompt/source excerpt persistence or blocking hook. |
| KA-06 | SessionStart/CLI materialize one deterministic outstanding packet from pending signals. | Concurrency, retry, batching, drift, overflow, and unchanged-state fixtures. | Lost signals, duplicate leases, or mutable cursor acknowledgement. |
| KA-07 | Terminal accept/reject never requeue; revise releases exact evidence; new observations remain auditable. | Promotion/rejection/revise/A-B-A/restart lifecycle tests. | Model advancement or timestamps resurrect/erase evidence. |
| KA-08 | Workflow batches are immutable generations activated by one workflow-root replacement. | Multi-signal crash/read concurrency tests observe complete generations only. | Packet/receipt is visible without all transitions. |
| KA-09 | Promotion uses canonical-to-workflow lock order, continuous locks after claim, universal canonical-writer admission, and recoverable old/new state. | Model-check/fault schedules for claim, abort, claim_failed, commit, crash, and recovery. | Deadlock, neither-state from supported writers, or accepted evidence requeue. |
| KA-10 | Acquisition MCP is a separately versioned read-only sidecar; core MCP 0.4 remains byte/shape compatible. | Frozen core contract plus sidecar mutation snapshots and failure isolation. | Additive tools change core digest or MCP read advances state. |
| KA-11 | Client integration is project-scoped, command-resolvable, journaled, recoverable, and honest about partial state. | Claude/Codex fixtures and installed-wheel real-client acceptance. | Partial integration reports ready or overwrites drift. |
| KA-12 | Removal is preview-first and preserves accepted YAML. | Complete/partial/conflict removal fixtures and filesystem snapshots. | Cleanup deletes canonical knowledge or silently clears claims. |
| KA-13 | Every asserted/inferred item retains provenance and inference never becomes canonical silently. | Schema, validation, proposal, review, and query provenance assertions. | Uncited assertion or inferred suggestion promoted by read. |
| KA-14 | All supported behavior works without Fraimed, CodeGraph, network, or one agent vendor. | Offline installed-wheel E2E with Claude and Codex configurations. | Hidden service/provider dependency. |

## Identifier ledger

| ID | Domain concept | Source of truth | Boundary/stored form | Allowed conversions | Forbidden equivalence |
| --- | --- | --- | --- | --- | --- |
| KI-01 | Canonical root/model digest | Canonical YAML bytes | SHA-256 string in roots/transactions | Recompute from exact bytes | Proposal/workflow digest |
| KI-02 | Signal identity | State key plus transition chain | Content ID in immutable workflow object | Validated state to content ID | Observation timestamp |
| KI-03 | Packet/lease identity | Active workflow generation | Content ID and causal transition | Signal set to one packet batch | Mutable cursor/ack |
| KI-04 | Review/receipt identity | Exact proposal/evidence/review bytes | Digest-bound immutable objects | Review to receipt after valid disposition | Self-declared actor as authorization |
| KI-05 | Repository identity | Confined project root | Stable root identity | Trusted cwd to confined root | Arbitrary hook cwd/path |

## Authority ledger

| ID | Entry point | Permitted authority | Prohibited elevation |
| --- | --- | --- | --- |
| KA-A1 | Core/acquisition MCP reads | Read validated canonical/workflow snapshots | Scan, review, acknowledge, write, or migrate |
| KA-A2 | Stop/SessionStart hooks | Advisory local signal/packet operations | Block client, call network/model, mutate canonical YAML |
| KA-A3 | Review command | Store explicit digest-bound decision | Infer authentication or apply canonical mutation |
| KA-A4 | Apply/recovery command | Activate exact reviewed transaction under locks | Rebase affected state silently or overwrite conflict |
| KA-A5 | Remove command | Preview/delete disposable state/integration | Delete accepted canonical YAML |

## Operation and effect envelope

| ID | Entry point/path | Success effects | Failure/retry/denial requirements |
| --- | --- | --- | --- |
| KO-01 | `lore init` knowledge bootstrap | Immutable proposal/status; optional reviewed canonical activation; journaled integration | Preview is no-write; partial integration explicit/resumable; canonical success preserved |
| KO-02 | Stop hook -> signal chain | At most one new bounded immutable observation transition | Advisory zero exit; corruption quarantined; no source prose |
| KO-03 | SessionStart/packet CLI -> workflow generation | One outstanding deterministic packet lease | Drift retries without loss; contention honest; overflow cannot claim complete history |
| KO-04 | Review -> receipt/transition proposal | Exact accept/reject/revise record | Stale/malformed review has zero canonical effect |
| KO-05 | Promotion -> canonical/workflow roots | Complete canonical graph and terminal/revise workflow generation | Old/new recovery, `claim_failed`, no supported neither-state, idempotent recovery |
| KO-06 | Acquisition sidecar/status/doctor | Provenance-rich read-only state and exact next action | Missing differs from empty; failure does not alter core MCP/state |
| KO-07 | Remove/repair/compact | Previewed equivalent disposable-state transition | Claims/conflicts fail closed; canonical YAML preserved |

## Rollback and recovery ledger

| ID | Failure point | Required recovery/equivalence |
| --- | --- | --- |
| KR-01 | Before canonical/workflow root activation | Unreferenced staging has no visible effect; exact prior root remains authoritative. |
| KR-02 | Canonical old with active claim | Under universal admission, exact retry or atomic `claim_failed`; affected prior lease restored. |
| KR-03 | Canonical new with active claim | Mandatory idempotent roll-forward to final workflow disposition before another canonical mutation. |
| KR-04 | Integration prefix failure/drift | Journal reports partial/conflict; resume or reverse compensation only against matching hashes. |
| KR-05 | Corrupt/forked workflow generation | Fail closed, acknowledge nothing, previewed verified repair only. |
| KR-06 | Removal after accepted promotion | Disposable state/integration may be removed; accepted Git YAML and query result remain equivalent. |

## Verification contract

The independent evidence author maps every KA/KO/KR row to executable public-
boundary evidence, records baseline selection and sensitivity, and freezes tests
before production edits. The implementer may not edit frozen evidence. The final
verifier must reconcile every unique row against the exact candidate and run the
frozen evidence plus complete regression, packaging, offline, and real-client
checks. Empty selections, unexplained skips, changed test bytes, or unresolved
rows are Not ready.
