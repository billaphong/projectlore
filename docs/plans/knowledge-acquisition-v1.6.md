# ProjectLore knowledge acquisition plan — amendment 1.6

This immutable amendment composes after versions 1.0–1.5 and resolves
KA-REV15-001 and KA-REV15-002. Later rules here replace conflicts.

## Causal lease chain

Replace all wall-clock precedence in v1.5 per-signal state derivation with an
immutable per-signal `LeaseTransition` chain. Timestamps are display-only and
never decide state.

Each transition binds repository ID, signal ID, previous transition ID (or
genesis), exact previous ordinal, next ordinal, kind (`lease`, `release`, or
`terminal`), causal record ID (packet or disposition receipt), evidence digest,
and completion marker. Under the existing packet lock, a writer reconstructs
and validates the chain, requires `next_ordinal = previous_ordinal + 1`, rechecks
the tip immediately before atomic completion, and loses/retries if another
writer advanced it.

- Packet completion appends `lease` referencing the exact prior `release` or
  genesis. A valid tip lease is the sole outstanding packet.
- A `revise` disposition appends `release` referencing that exact lease. It
  makes the signal immediately eligible; a replacement packet must append the
  next lease referencing that release.
- When all candidates for a signal are accepted/rejected, disposition appends
  `terminal` referencing its lease. Terminal is absorbing for that signal.
- Mixed review appends release when any candidate is revised while the receipt
  separately preserves terminal candidate IDs; later packets exclude those
  candidates.

On restart, derive state solely from the validated chain tip. A missing parent,
duplicate ordinal, fork, causal-record mismatch, evidence mismatch, or invalid
completion quarantines the affected chain and acknowledges nothing; bounded
full reconciliation is required. Recovery never chooses a branch using time or
lexical ID. An explicit previewed repair operation may select a verified branch
only after showing every competing record and its causal dependencies.

SessionStart and CLI serialize materialization under the packet lock and recheck
the chain. Thus a revised signal has at most one replacement lease across clock
jumps, restarts, crashes, and concurrent callers.

## Review integrity wording

Replace every occurrence and implication of “signed review” with “durably stored,
digest-bound `KnowledgeReview`.” No cryptographic signature, signing key, trust
root, or authenticated actor is part of this plan. Actor identity remains
self-declared audit metadata and never grants authorization.

## Verification and exit amendments

Add causal-chain tests for backward/forward clock jumps across restart, equal
timestamps, concurrent packet/review writers, every crash boundary, stale-tip
retry, missing parent, duplicate ordinal, fork, invalid causal record, and
previewed repair. Assert that state is identical under arbitrary timestamp
permutations. Static plan/contract checks reject `signed`, `signature`, signing
key, or four-value review vocabulary in implemented public contracts/docs.

The lifecycle is ready only when immutable causal order—not time—proves exactly
one outstanding lease or one absorbing terminal state per signal. Implementation
remains prohibited until this exact seven-component composition receives an
independent score of at least 97, no High/Critical findings, all hard gates, and
a verified review/manifest package. `author-tests` remains first thereafter.
