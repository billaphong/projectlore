# ProjectLore knowledge acquisition plan — amendment 1.10

This immutable amendment composes after versions 1.0–1.9 and resolves
KA-REV19-001 and KA-REV19-002 by replacing the v1.9 post-claim lock rule.

## One proven nested lock order

There are two locks with one allowed nested order: canonical lock → workflow
lock. Workflow-only operations never acquire the canonical lock. Claim and abort
remain workflow-only and release that lock before any canonical attempt. No code
may acquire canonical while holding workflow; static call-graph checks, runtime
lock-rank assertions, and deterministic deadlock tests enforce this.

After durable `commit_claimed`, the promoter acquires and continuously holds the
canonical lock through validation, optional canonical root replacement, and
final workflow-generation activation. While holding canonical it may acquire
workflow second, revalidate the exact active claim/tips/root, perform the single
workflow-root activation, then release workflow followed by canonical. The
bounded critical section performs only local validated filesystem operations—no
agent/model/network/user interaction.

Consequences:

- No other canonical writer can advance old/new root during the committed gap.
- Workflow writers may advance unrelated state before the promoter acquires
  workflow; finalization preserves it. Affected state remains blocked by claim.
- Once final workflow root activates, receipt/transitions and claim removal are
  visible together before the canonical lock is released.

## Failed-claim recovery

If mandatory under-canonical-lock validation fails while actual canonical root
equals the bound old digest, the recovery path keeps canonical locked, acquires
workflow second, rechecks old digest and exact claim/tips, and atomically
activates a `claim_failed` generation that records structured validation errors,
removes the claim, and releases affected signals back to their prior lease state.
It then releases workflow/canonical. Because canonical replacement cannot occur
while canonical is held, no trace can release a claim after commit.

If actual root equals new, validation is limited to immutable prepared inputs and
final workflow activation must roll forward. If neither, keep the claim and fail
closed; no release or overwrite. Retry of a completed `claim_failed` outcome is
idempotent. A new promotion requires a new review/claim and fresh validation.

Crash behavior uses existing durable state: before root replacement, actual old
plus claim can retry or safely fail under both locks; after replacement, actual
new plus claim rolls forward while canonical lock excludes later writers; after
final workflow root, disposition is complete. OS lock release on process death
permits recovery; no time-based stale-lock inference is used.

## Verification and exit amendment

Model-check the allowed lock graph and deterministically schedule workflow-only
writers, competing canonical writers, claim/abort, permanent validation failure,
crash at every nested critical-section write, old/new/neither roots, and recovery.
Assert no deadlock, no canonical advancement during claimed finalization, no
claim release after commit, preservation of unrelated workflow state, and exactly
one final `claim_failed` or disposition generation.

Implementation remains prohibited until this exact eleven-component composition
receives independent score ≥97, no High/Critical findings, every hard gate, and
a verified detached review/manifest. `author-tests` remains first afterward.
