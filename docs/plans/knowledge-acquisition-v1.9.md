# ProjectLore knowledge acquisition plan — amendment 1.9

This immutable amendment composes after versions 1.0–1.8 and resolves
KA-REV18-001 with a durable claim transition.

## Claim-before-commit protocol

`PromotionPrepared` has immutable workflow states `reserved` then
`commit_claimed`. Before taking the canonical lock, the promoter takes the
workflow lock and atomically activates a generation changing the exact active
reservation to `commit_claimed`, preserving affected tips and all bound old/new
canonical and review/evidence identities. It then releases the workflow lock.

Only `reserved` may be preview-aborted, and abort plus claim serialize under the
same workflow lock/root compare-and-replace. Exactly one wins:

- abort first removes `reserved`; a later claim fails because its expected root
  and reservation are absent, and canonical replacement is forbidden;
- claim first activates `commit_claimed`; abort is permanently forbidden.

After claim, the promoter acquires the canonical lock, reloads the active
workflow root, verifies the exact claim still exists, and compares actual
canonical root to the bound digests. If old, it may replace old→new. If new, it
proceeds to final workflow recovery. If neither, it reports conflict. It never
relies on validation performed before claim or before acquiring the canonical
lock.

`commit_claimed` has no time expiry and every later unrelated workflow generation
must copy it and the affected tips unchanged. No operation can abort, remove,
compact, repair, lease, release, or terminalize affected state. Crash after claim
but before canonical lock/root replacement is recoverable: actual old permits an
explicit recovery command to retry the exact bound replacement. A claim can
never be demoted or aborted, even while the actual root is old; this deliberately
favors safe roll-forward over cancellation after the final authorization point.
Crash after root replacement uses actual new and rolls forward; neither remains
conflict/fail-closed.

The global rule remains that no process holds both locks. Workflow claim always
precedes canonical acquisition; canonical code never acquires workflow
lock. Final workflow activation occurs only after releasing canonical lock.
Static lock-order assertions and instrumented tests enforce this.

## Verification and exit amendment

Deterministically schedule abort-before-claim, claim-before-abort,
abort-racing-claim, crash after claim, claim missing at
canonical revalidation, root old/new/neither, crash after replacement, unrelated
workflow advancement, and repeated recovery. Assert canonical replacement is
reachable only with the exact active claim and that no trace ends with new
canonical root absent a claim or final disposition.

Implementation remains prohibited until this exact ten-component composition
receives independent score ≥97, no High/Critical findings, all hard gates, and a
verified detached review/manifest. `author-tests` remains first afterward.
