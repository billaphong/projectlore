# ProjectLore knowledge acquisition plan — amendment 1.8

This immutable amendment composes after versions 1.0–1.7 and replaces the v1.7
canonical-promotion coordination protocol, resolving KA-REV17-001 and
KA-REV17-002.

## Prepared reservation is the precondition

Promotion uses three observable states: `reserved`, `canonical_committed`, and
`complete`. Under the workflow lock it first atomically activates a workflow
generation containing:

- a `PromotionPrepared` journal binding proposal/review/evidence IDs and digests,
  affected signal IDs and their exact lease tips, old canonical root digest,
  fully staged new canonical root digest/transaction ID, and intended terminal/
  release transitions;
- a reservation on every affected lease tip; and
- no terminal acknowledgement yet.

The active reserved generation is the durable prepared record. Any operation on
an affected signal must load it and return `promotion_reserved`; it cannot lease,
release, terminalize, compact, remove, or repair that signal. Unrelated signals
may advance through new workflow generations only by copying the verified
reservation and its exact affected tips unchanged. Workflow writers use one lock
and one root, so no affected transition can race the reservation.

## Canonical root is the commit point

After reservation activation, the canonical transaction lock is acquired in the
global order `workflow reservation → release workflow lock → canonical lock`;
no code holds both locks and no reverse acquisition is permitted. The canonical
writer revalidates the active reservation, affected tips, old canonical digest,
review, staged new root, and source evidence, then atomically replaces the
canonical root. That replacement—not a later marker—is the commit point.

Recovery reads the active prepared reservation and actual canonical root:

- actual equals old digest: pre-commit. It may retry canonical activation, or an
  explicit previewed abort atomically activates a workflow generation removing
  the reservation; no knowledge was accepted.
- actual equals staged new digest: committed. The exact bound affected signals
  remain suppressed by the reservation and recovery must roll forward.
- actual equals neither: conflict. Reservation remains, no acknowledgement is
  inferred, and status requires explicit diagnosis; automatic overwrite/abort is
  forbidden.

A post-root marker may record observation but is never evidence of commitment.
Faults immediately after root replacement are therefore distinguishable.

## Final workflow activation

For the committed case, recovery reacquires the workflow lock, reloads the
latest generation, verifies the unchanged reservation/tips and actual new
canonical digest, and atomically activates one final generation that adds the
receipt plus every terminal/release transition and removes the reservation.
Unrelated intervening generations are preserved mechanically; affected tips may
not differ. There is no semantic rebase of affected state. Crash before final
root replacement leaves reservation suppression active; crash after it exposes
the entire final disposition. Repeated recovery observes `complete` and is a
no-op.

Reject/revise-only reviews need no canonical root and continue to activate as
one ordinary workflow generation without reservation. Mixed reviews containing
any accept use the protocol above for every signal in that review so candidate
terminality/revision becomes visible in one final batch.

Reservations have no time-based expiry. Doctor reports age for humans but cannot
clear them. Previewed abort is allowed only while actual canonical digest equals
the bound old digest. Removal refuses an active committed/conflict reservation;
pre-commit removal requires the same verified abort first.

## Verification and exit amendments

Fault-inject around reservation-root activation, every canonical staging write,
canonical-root replacement, optional marker, and final workflow-root activation.
Prove old/new/neither digest recovery, competing affected writer rejection,
unrelated writer preservation, lock-order static/runtime assertions, retry,
previewed pre-commit abort, committed no-abort, mixed review, status/doctor,
removal refusal, and next-session suppression throughout the committed gap.

Exit requires that the active prepared reservation plus actual canonical digest
alone determine recovery, and that affected tips cannot advance until one final
workflow generation disposes them. Implementation remains prohibited until this
exact nine-component composition receives independent score ≥97, no High/
Critical findings, all hard gates, and verified detached review/manifest.
`author-tests` remains first afterward.
