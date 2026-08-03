# ProjectLore knowledge acquisition plan — amendment 1.5

This immutable amendment composes after versions 1.0–1.4 and resolves
KA-REV14-001 through KA-REV14-003. Later rules here replace conflicting earlier
rules.

## Unified review contract

Replace the Phase 1 shared `KnowledgeReview` contract and every Phase 2/3 use
with exactly three per-candidate dispositions: `accept`, `reject`, or `revise`.
`accept` and `reject` are terminal for the exact evidence; `revise` is the sole
nonterminal value and means return the candidate/evidence to proposal work.
Earlier uses of `defer` are renamed to `revise`; no fourth value or compatibility
alias is accepted because this is unreleased schema. Baseline onboarding and
ongoing acquisition use the same strict schema and receipt semantics.

## Per-signal state precedence

Eligibility is derived per signal, not by subtracting raw global unions. For
each signal, validate records and select the newest applicable transition by
the deterministic tuple `(completed_at_utc, content_id)`, where timestamps are
validated UTC informational ordering fields and the content ID breaks ties:

1. A valid terminal receipt wins permanently for that exact signal/evidence.
2. A valid revise receipt releases all packet leases named by that review. The
   signal is immediately eligible again in unchanged state unless a later
   complete packet covers it.
3. A complete evidence-current packet later than the latest release is an
   outstanding-work lease and suppresses duplicate packet creation while it is
   unreviewed. A stale/invalid packet is no lease.
4. With neither terminal receipt nor outstanding lease, the signal is pending.

Packet creation records `supersedes_packet_ids` after a revise release. A later
packet for unchanged evidence has a distinct identity because it binds the
release receipt and attempt ordinal derived from the immutable chain. Repeated
SessionStart/CLI calls observe that packet rather than create another. Mixed
reviews release a signal if any candidate derived from it is `revise`; terminal
candidates remain recorded and are excluded from later proposals. A new packet
may propose only the revised candidates. These rules are computed from immutable
records and require no mutable cursor.

## Restart-safe signal identity

Separate the content-addressed identity projection from informational fields.
`SignalStateKey` hashes repository identity, HEAD identity (including unborn or
detached state), normalized Git-status digest, model-root digest, and ordered
path/status/size/content-hash/reason tuples. `observed_at_utc` is stored but is
not part of `SignalStateKey`.

An immutable `ObservationTransition` chains `previous_state_key` to
`current_state_key` and includes a monotonic per-repository transition ordinal
derived under the existing atomic signal lock from the complete immutable chain.
Repeated Stops where current key equals the chain tip return the existing signal
and add nothing. A change A→B appends transition/signal B; a later byte-identical
revert B→A appends a new transition/signal A with a new ordinal, so it cannot
collapse into the earlier A observation. On restart, the chain tip and ordinal
are reconstructed from validated complete records. Missing, forked, or corrupt
chains are quarantined and trigger bounded full reconciliation; they never guess
an ordinal or acknowledge evidence.

The signal content ID hashes `SignalStateKey`, transition ordinal, and previous
transition ID, but excludes observation time. This makes identical Stops in one
state idempotent while preserving genuine revisits. Concurrent Stop calls are
serialized by the signal lock and recheck the tip before completion.

## Verification and exit amendments

Add explicit tests for immediate unchanged-state revise-all retry, mixed review
with only revised candidates reproposed, receipt/packet precedence ties, repeated
SessionStart idempotency, repeated Stop across process restart, concurrent Stop,
A→B→A revert, detached/unborn HEAD, corrupt/forked chain reconciliation, and
timestamp variation with identical state. Contract fixtures prove only the
three public dispositions everywhere.

The stable lifecycle exit is: terminal evidence never reappears; revised
evidence immediately becomes eligible and obtains at most one outstanding lease;
unchanged repeated observations deduplicate; every intervening state transition,
including a revert, creates a new auditable observation. Implementation remains
prohibited until this exact six-component composition scores at least 97, has no
High/Critical finding, passes all hard gates, and is bound to a verified detached
review/manifest package. `author-tests` remains first after readiness.
