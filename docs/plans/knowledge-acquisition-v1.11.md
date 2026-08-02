# ProjectLore knowledge acquisition plan — amendment 1.11

This immutable amendment composes after versions 1.0–1.10 and resolves
KA-REV10-001. It replaces the claim acquisition sequence only.

The promoter acquires canonical lock first, then workflow lock in the established
canonical→workflow order. While holding both it validates current canonical root,
prepared reservation/review/evidence, staged new root, and exact affected tips,
then atomically activates `commit_claimed`. If any validation fails, it creates
no claim and releases both locks; the earlier abort/revise workflow remains
available. If valid, it releases workflow but retains canonical continuously.

While still holding canonical, it rechecks immutable staged bytes, replaces the
canonical root old→new, then reacquires workflow second and atomically activates
the final disposition generation (or, if pre-replacement validation fails,
`claim_failed`). It releases workflow then canonical. Because canonical was held
before claim activation and through final disposition, no canonical writer can
produce an intervening root. Abort remains workflow-only and may win before the
promoter obtains workflow; after claim it is forbidden. Unrelated workflow work
may precede either workflow acquisition and is preserved from the freshly loaded
generation; affected tips must remain reserved/claimed.

Acquisition uses bounded lock waits and returns actionable retry without state
change. A process crash releases OS locks; recovery acquires canonical then
workflow, derives old/new/neither from the durable claim and actual root, and
uses the v1.10 failure/finalization rules. `neither` now denotes external
corruption or a nonconforming writer, not a normal supported concurrency trace.

Verification deterministically schedules a canonical writer that starts first,
promoter first, abort before/during nested acquisition, unrelated workflow work,
validation failure, all crash points, and lock timeout. Model checking must show
no supported trace reaches `commit_claimed` unless canonical equaled bound old
under canonical exclusion, and no canonical lock release occurs before either
`claim_failed` or final disposition after claim.

Implementation remains prohibited until this exact twelve-component composition
receives independent score ≥97, no High/Critical findings, every hard gate, and
a verified detached review/manifest. `author-tests` remains first afterward.
