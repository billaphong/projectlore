# ProjectLore knowledge acquisition plan — amendment 1.7

This immutable amendment composes after versions 1.0–1.6 and resolves
KA-REV16-001. It replaces separate per-signal transition publication with one
immutable batch generation and one atomic activation boundary.

## Knowledge workflow state generations

All signals, packets, reviews, receipts, and causal transitions remain immutable
content-addressed objects. The sole authority for their visibility is a small
`knowledge-state-root.json` containing schema version, repository ID, generation
ID, generation digest, and prior-generation digest. A generation is an immutable
manifest that names and hashes the complete prior state plus the exact staged
object additions and resulting per-signal chain tips. Readers load root bytes
once, verify the named complete generation and every referenced object, and use
only that generation. Unreferenced staged objects have no state effect.

Under one cross-process knowledge-state lock, a writer:

1. reads and validates the active root/generation;
2. constructs the packet or disposition causal record and every affected
   per-signal transition against that generation;
3. writes all immutable objects and a new immutable generation unreferenced;
4. rechecks the active root digest and every evidence/canonical precondition;
5. atomically replaces the single root file to activate the whole batch.

Thus a packet covering N signals activates its packet plus N lease transitions
in one generation. A review covering N signals activates its durable review,
receipt, and all release/terminal transitions together. Crash before root
replacement leaves only ignorable staged objects; crash after replacement makes
the entire verified generation visible. No normal crash creates a mismatch or
quarantine condition. Competing writers serialize and must rebase if the root
digest changed.

## Canonical promotion coordination

Accepted knowledge still uses its independent single-root canonical transaction
because two filesystem roots cannot be atomically replaced together. Promotion
therefore has an explicit durable roll-forward journal:

1. stage and validate the next workflow generation, but do not activate it;
2. activate the canonical root once and durably mark the canonical transaction
   committed with old/new canonical digests and reviewed proposal digest;
3. under the workflow lock, revalidate that exact committed canonical
   transaction and active workflow base, then activate the staged-or-rebased
   workflow generation containing the disposition receipt/transitions;
4. mark the journal complete only after both active roots verify.

Before step 2, recovery discards/ignores staging. After step 2, rollback is
forbidden because canonical knowledge is already authoritative; status is
`promotion_recovery_required`, acquisition for affected signals is suppressed by
the verified committed canonical transaction journal, and recovery idempotently
rolls forward step 3. This suppression is narrow: it binds the exact proposal,
review, evidence, signals, and old/new canonical digests, and cannot acknowledge
unrelated evidence. Reads expose the recovery state and never perform recovery.
The explicit CLI recovery command previews and validates before activating the
workflow generation. Invalid or mismatched journals suppress nothing and fail
closed with diagnostics.

## Lifecycle, compaction, and repair

Per-signal causal ordering from v1.6 is now stored inside generations; the active
generation is the atomic batch authority. Generation/object compaction is
previewed and creates a new equivalent immutable generation before one root
replacement. Repair never selects a fork implicitly. Root/generation corruption
fails closed and requires previewed recovery from a fully verified prior
generation. Removal deletes the disposable workflow root/generations/objects
together only after preview, while canonical YAML remains untouched.

## Verification and exit amendments

Fault-inject before/after every object, generation, workflow-root, canonical-root,
and journal marker write for multi-signal packets and accept/reject/revise mixed
reviews. Concurrent readers must observe the complete old or complete new
workflow generation only. Test canonical committed/workflow pending recovery,
restart, competing writer rebase, invalid journal no-suppression, idempotent
roll-forward, status/doctor/sidecar behavior, compaction, repair, and removal.
The final product E2E includes multi-signal edit → one packet generation → mixed
review → canonical activation → workflow-generation activation → MCP rediscovery
→ next SessionStart with no terminal evidence requeued.

Exit requires one atomic workflow-root replacement per batch and an explicit
roll-forward boundary for the unavoidable canonical/workflow two-root sequence.
Implementation remains prohibited until this exact eight-component composition
receives an independent score ≥97, no High/Critical findings, every hard gate,
and a verified detached review/manifest. `author-tests` remains first thereafter.
