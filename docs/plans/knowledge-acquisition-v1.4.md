# ProjectLore knowledge acquisition plan — amendment 1.4

This immutable amendment composes after versions 1.0–1.3. It resolves
KA-REV13-001 by separating evidence validity from terminal disposition. Where
this amendment conflicts with an earlier component, this amendment wins.

## Terminal evidence disposition

Replace Phase 4 steps 3 and 6 and extend Phase 3 review/promotion as follows.

1. A signal is eligible only when its ID is absent from both (a) the union of
   `covered_signal_ids` in complete, evidence-current packets and (b) the union
   of `terminal_signal_ids` in valid immutable disposition receipts. Packet
   base-model advancement alone never invalidates a disposition receipt.
2. A `KnowledgeReview` resolves every candidate in the proposal as `accept`,
   `reject`, or `defer`, with a reason and the exact proposal, packet, evidence,
   and source-manifest digests. Accept/reject are terminal for that exact
   evidence; defer is nonterminal. Partial review is therefore explicit rather
   than inferred from a missing candidate.
3. The canonical transaction writes accepted YAML first. Only after its new
   root is durably activated does it atomically complete a content-addressed
   `KnowledgeDispositionReceipt`. The receipt binds old and new canonical root
   digests, review/proposal/packet IDs and digests, accepted and rejected
   candidate IDs, terminal signal IDs, deferred candidate/signal IDs, source
   evidence hashes, transaction ID, and outcome. Crash before receipt completion
   leaves evidence retryable; crash after completion is idempotently detected.
4. A review with no accepted candidates writes the same immutable receipt after
   the signed/digest-bound review is durably stored. Rejected evidence becomes
   terminal; deferred evidence remains eligible. For a mixed review, a signal
   becomes terminal only if every candidate derived from it is accepted or
   rejected. Otherwise the receipt records it as deferred and a later packet may
   cover it without recreating terminal candidates.
5. Receipt validation rehashes its review, proposal, packet, evidence manifest,
   canonical transition, and completion marker. Invalid/orphaned receipts are
   quarantined and acknowledge nothing. Receipts are disposable operational
   records but may not be compacted while their signal IDs remain locally
   present unless compaction writes an equivalent content-addressed summary.
6. Source changes create a new content-addressed signal because path status,
   size/hash, HEAD/status digest, or model-relative reason changes. A Git revert
   to byte-identical prior evidence still creates a new observation identity
   bound to the later repository/worktree state; it does not resurrect the old
   terminal signal. Identical duplicate Stop observations within the same state
   continue to deduplicate.
7. Unrelated canonical changes may stale an unreviewed proposal and require
   rebase/revalidation, but they never re-enqueue terminal signals. A canonical
   transaction that incorporates the reviewed proposal is expected advancement,
   proven by the receipt's old/new root pair. Later model changes affect only
   unresolved proposal applicability.
8. SessionStart and `lore knowledge packet next` calculate pending evidence from
   validated immutable signals, packets, and disposition receipts under the
   existing bounded lock. They return no packet when all signals are terminal,
   even immediately after promotion or unrelated canonical changes.

## Status, sidecar, recovery, and removal

`knowledge_status` and the sidecar expose terminal, rejected, deferred, pending,
and invalid-receipt counts plus exact receipt/review provenance. Reads never
write a receipt. Doctor detects orphaned transactions, invalid receipts, and
missing receipt dependencies. Recovery can idempotently finish a receipt only
from a verified completed canonical transaction and matching review; otherwise
it leaves evidence pending. Previewed removal may delete signals/packets/receipts
together, but accepted canonical YAML remains authoritative and untouched.

## Required verification additions

- Immediately after successful promotion, SessionStart and CLI return no packet
  for the consumed signals; repeat after an unrelated canonical model change.
- Accept-all, reject-all, defer-all, and mixed/partial reviews prove exact
  terminal/deferred signal semantics and no duplicate proposal churn.
- Crash/cancel before canonical activation, after activation but before receipt,
  and after receipt completion; recovery is lossless and idempotent.
- Tampered, truncated, orphaned, dependency-missing, and competing receipts
  acknowledge nothing and produce actionable diagnostics.
- A genuine source edit and a later Git revert each create new evidence while
  the prior terminal observation remains consumed.
- Concurrent SessionStart/CLI during promotion observes either the old pending
  state or the completed receipt state, never an invented acknowledgement.
- The complete E2E adds a final next-SessionStart assertion proving zero
  re-materialization after MCP rediscovers the promoted knowledge.

## Corrected exit gate

Every complete signal is in exactly one derived state: pending, covered by a
current unreviewed packet, deferred by a valid receipt, or terminally disposed
by a valid receipt. Expected canonical advancement never changes terminal state.
No accepted or rejected evidence can be proposed again unless a new signal with
new observation identity is created. Implementation remains prohibited until
the exact five-component composition receives a detached score of at least 97,
passes every hard gate with no High/Critical finding, and has a verified handoff
manifest. `author-tests` remains the first implementation activity thereafter.
