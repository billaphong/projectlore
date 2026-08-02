# ProjectLore knowledge acquisition plan — amendment 1.12

This immutable amendment composes after versions 1.0–1.11 and resolves
KA-REV11-001 and KA-REV11-002. It replaces promotion lock retention and canonical
writer admission.

## Continuous critical section

The promoter acquires canonical then workflow, validates and activates
`commit_claimed`, and retains **both locks continuously** through canonical root
replacement and final workflow-generation activation. It never releases and
reacquires workflow after claim. The already bounded critical section contains
only staged-byte verification and two local atomic root replacements; all source
inspection, review, staging, model compilation, and user/agent work occurred
before lock acquisition.

Pre-claim acquisition uses bounded waits and may return unchanged. After claim,
there is no second wait or outward timeout: the process performs the finite local
commit sequence, then releases workflow followed by canonical. Fault injection
proves each filesystem operation is bounded/configured and failures enter the
durable old/new recovery states; no network or unbounded callback is reachable.

## Universal canonical-writer admission

Every canonical mutation entrypoint, including onboarding, ordinary promotion,
recovery, migration, and future adapters, must while holding canonical acquire
workflow second and inspect the active workflow generation before changing the
canonical root. This check lives in the sole shared `CanonicalKnowledgeTransaction`
engine; direct canonical writes outside it are unsupported and detected by tests.

If no active `commit_claimed` exists, the writer may proceed after its normal
validation. If a claim exists, the caller becomes recovery owner under both
locks: actual old yields exact retry or `claim_failed` according to immutable
validation; actual new yields final workflow disposition; neither fails closed.
Only after recovery reaches `claim_failed` or final disposition may an unrelated
canonical mutation revalidate against the then-current root and proceed as a new
transaction. Thus process death releases locks but cannot admit a writer past an
unresolved durable claim.

Competing recovery/canonical writers serialize on canonical. Workflow-only
writers serialize on workflow and cannot deadlock because they never request
canonical. Holding canonical while waiting the initial bounded workflow interval
changes no state; timeout returns retry. Once workflow is acquired, recovery is
the same finite local critical section described above.

## Verification and exit amendment

Instrument every canonical mutation entrypoint to prove shared-engine admission.
Deterministically crash promoter before/after each durable write, then race
ordinary canonical writers and multiple recoverers. Delay a workflow-only holder
before initial nested acquisition and prove bounded unchanged retry; assert no
post-claim lock acquisition exists. Model-check the lock graph and prove no
supported trace changes canonical old/new to neither while a claim is active.

Implementation remains prohibited until this exact thirteen-component
composition receives independent score ≥97, no High/Critical findings, every
hard gate, and a verified detached review/manifest. `author-tests` remains first
afterward.
