# ProjectLore knowledge acquisition plan — transaction amendment

Plan ID: `projectlore-knowledge-acquisition`

Plan version: `1.2.0`

Status: frozen for independent review

Plan author: Codex primary agent

Decision authority: ProjectLore owner

## Exact plan composition and precedence

The exact implementation plan is the following ordered composition:

1. `docs/plans/knowledge-acquisition-v1.md`, raw-byte
   `sha256:9cd6821a0578c4b24d6748966d94942c9ad4b3e08bbbd4cae9abbe39cf09fca0`
2. `docs/plans/knowledge-acquisition-v1.1.md`, raw-byte
   `sha256:742408423f501243dc8be46a1dcd6631f239d5b55bb696ce880b2e3c39846130`
3. this 1.2.0 amendment, applied last and winning every conflict

All unaffected authority, requirements R01-R20, facts F01-F14, risks K01-K18,
decisions D01-D10, and six phase records remain normative. All three exact plan
components must be delivered and read. Repository baseline and worktree
identity remain those pinned in the base plan.

The independent 1.1 review at
`sha256:dad0030561aea0b984f976fc111de4a45f3105f00ca16b4e3379d7fc9d34e4fb`
scored 93/100 and found KA-REV11-001 (whole-onboarding transaction ambiguity)
plus the then-expected missing current review package. Both are accepted.

## Finding disposition ledger

| Finding | Disposition | Resolution |
| --- | --- | --- |
| KA-REV11-001 | Accepted | Replace the impossible whole-preview atomicity claim with two separately previewed and applied transactions: canonical knowledge activation is one atomic root replacement; client integration is a journaled, resumable/compensatable sequence with an honest `integration_partial` state. |
| KA-REV11-002 | Accepted | Preserve the 1.1 review and manifest; create a distinct detached review and manifest for this exact 1.2 composition after grading. |

## Replacement decision D08

Replace D08 with:

| ID | Question | Ladder evidence consulted | Alternatives and consequences | Recommendation | Classification | Authority/citation |
| --- | --- | --- | --- | --- | --- | --- |
| D08 | How does useful onboarding coexist with non-atomic user-owned integration files? | `lore init` is compatibility-frozen and writes files sequentially; canonical activation can be atomic at one root; Claude/Codex trust/reload is external. | Claiming one transaction is false; integrating before knowledge can launch a missing model; explicit sequential transactions are recoverable and honest. | Keep `lore init`; make `lore onboard` a guided two-transaction workflow: apply reviewed canonical knowledge first, then separately preview/apply integration with a durable per-file journal. Readiness requires both, but partial integration never rolls back accepted knowledge automatically. | Resolved by evidence | `onboarding.py:70-89`; KA-REV11-001 |

Decision reconciliation is now 10 total: 4 Resolved by authority, 4 Resolved by
evidence, 2 Recommended engineering choice, 0 Genuine human decision.

## Replacement requirements

Replace R01, R06, and R11 with:

| ID | Exact authority location | Required outcome or absence | Plan phase/step | Verification obligation | Status |
| --- | --- | --- | --- | --- | --- |
| R01 | Owner direction 1 | One guided onboarding workflow produces reviewed project-specific canonical knowledge and then configures supported clients; completion is not claimed between transactions. | P2.1-P2.10 | Clean-repository E2E passes through knowledge and integration states and yields retrievable project-specific domains/concepts/sources/relationships/unknowns. | Covered |
| R06 | `AGENTS.md`; existing preview patterns | Canonical mutation is one digest-bound atomic activation. Each noncanonical integration file is digest-bound, journaled, independently recoverable, never overwritten after drift, and honestly reported if partial. | P2.6-P2.10, P3.4-P3.7 | Canonical interleaving tests plus integration crash/permission/drift/resume/rollback tests after every write. | Covered |
| R11 | Onboarding product boundary | Status distinguishes acquisition, review, canonical activation, integration preview/partial/completion, client trust, and retrieval readiness. | P2.2-P2.10, P4-P6 | Status/doctor fixtures prove no partial state reports ready and give an exact next recovery action. | Covered |

Requirement reconciliation remains 20 total, all Covered.

## Replacement risks

Replace K03 and K17 with:

| ID | Scenario | Boundary | Prevention/detection | Recovery/rollback | Proof | Owner/status |
| --- | --- | --- | --- | --- | --- | --- |
| K03 | Path/symlink/race escapes root or an integration recovery overwrites user drift. | Scanner, canonical apply, integration transaction | Root confinement, symlink rejection, per-file before/after digests, atomic same-file writes, canonical apply lock, durable integration journal, recheck immediately before every write/compensation. | Stop on drift without overwriting; journal names exact conflicting path and next action. Canonical root remains valid; integration resume/rollback affects only files still matching journal digests. | Hostile filesystem, race before every write, symlink swap, and compensation-drift tests. | Implementer / Covered |
| K17 | Cancellation/crash leaves misleading onboarding completion or partial client integration. | Scan, review, canonical apply, integration apply | Propagate cancellation; completion markers last; canonical and integration transactions have separate IDs/states; journal is durably updated before/after each integration write; readiness derives from verified files, not journal claim alone. | Resume remaining writes or compensate completed writes in reverse order when their bytes still match; otherwise stop at `integration_conflict`. Never automatically undo accepted canonical knowledge. | Cancellation/fault injection at every canonical and integration boundary, journal corruption, resume and rollback idempotency. | Implementer / Covered |

Risk reconciliation remains 18 total, all dispositioned.

## Phase 1 addition — integration transaction contract

Add a strict, independently versioned `IntegrationTransaction` contract to
Phase 1. It contains:

- transaction ID, onboarding session/review/canonical-model identities;
- ordered root-relative integration paths;
- for each path: existed-before flag, before digest, after digest, state
  (`pending`, `written`, `compensated`, or `conflict`), and last stable
  diagnostic code;
- transaction state (`previewed`, `applying`, `partial`, `complete`,
  `rolling_back`, `rolled_back`, or `conflict`);
- no file contents, credentials, environment, or trust assertion; and
- a digest over the complete immutable preview plus monotonically replaced
  journal generations.

The journal lives in ignored `.projectlore/onboarding/transactions/`, is written
atomically, and is evidence of attempted local work—not canonical knowledge or
client trust. Journal parsing is bounded/root-confined. Status recomputes file
digests and cannot trust `complete` without exact after bytes. A corrupt journal
never triggers compensation; it yields a diagnostic and manual file review.

Phase 1 verification adds contract/state-machine tests, corruption/bounds,
generation replay, and proof that journal presence changes no model/MCP/policy
answer.

## Complete Phase 2 replacement — two-transaction onboarding

Replace Phase 2 in the base and 1.1 amendment with this phase.

Objective: produce useful initial knowledge and install project integrations in
one guided workflow without pretending that unrelated filesystem files share an
atomic activation boundary. Covers R01, R03, R06-R09, R11, R13-R20.

Entry conditions: Phase 1 contracts, `KnowledgeReview`, canonical apply lock,
and `IntegrationTransaction` are frozen; existing `lore init` fixtures pass;
the target is a Git worktree or returns an explicit unsupported diagnostic.

Targets:

- `knowledge_scan.py`, `knowledge_onboarding.py`, acquisition CLI commands;
- shared non-mutating preview primitives from `onboarding.py`;
- a new integration transaction/recovery module rather than changing the
  historical meaning of `apply_initialization`;
- doctor/removal/status integration;
- synthetic sparse/conflicting/large/partial-failure repositories and docs.

Ordered steps:

1. `lore onboard start --name NAME` creates a metadata/hash-only local source
   packet using the bounded Git-aware inventory from 1.1. It writes no canonical
   or integration file.
2. Status begins at `not_started`, `packet_ready`, `proposal_ready`,
   `review_incomplete`, `reviewed`, or `stale`, with exact conflict/unknown and
   next-action data.
3. The active agent reads prioritized repository sources through existing
   repository authorization and submits portable candidate JSON. ProjectLore
   validates packet/base/source identity, metadata evidence, statuses, bounds,
   credential detectors, duplication/conflict, and drift.
4. `lore onboard review --proposal-digest DIGEST --decisions FILE --actor ID`
   creates the shared digest-bound `KnowledgeReview`. Every candidate must be
   accepted/rejected/revised; any revision returns to proposal work. Actor is
   self-declared and does not replace task authority or Git review.
5. `lore onboard preview-knowledge --review-digest DIGEST` renders only the
   complete canonical root, immutable versioned index/fragments, validation,
   coverage/unknown/conflict report, proposal decisions, and exact digests. It
   contains no client integration file.
6. `lore onboard apply-knowledge --preview-digest DIGEST --actor ID` uses the
   Phase 3 cross-process lock and sole root activation. Immutable files are
   written unreferenced, the staged model is validated, and one atomic root
   replacement creates the canonical model. Status becomes
   `knowledge_applied_integration_pending`. Failure before activation leaves no
   canonical model and only unreferenced recoverable files; after activation
   the complete model is authoritative.
7. Only after validating the active model, `lore onboard preview-integration`
   renders the existing seven project integration changes plus the acquisition
   hook/sidecar additions introduced in later phases. It records every
   before/after digest and ordered path but writes nothing. The stable order is:
   instruction files first, MCP entries second, hook settings last. This avoids
   enabling hooks before their instructions/server declarations exist, though
   no ordering is described as atomic.
8. `lore onboard apply-integration --preview-digest DIGEST` creates the durable
   journal in `previewed`, rechecks all before digests, then enters `applying`.
   For each path it rechecks the expected current digest immediately before an
   atomic same-file write, verifies after digest, and atomically advances the
   journal generation to `written`. A failure stops immediately at
   `integration_partial`; already written files remain explicit and no pending
   file is touched. The command never marks client trust.
9. `lore onboard recover-integration --transaction ID --mode resume|rollback`
   is preview-first. Resume verifies every written file still equals its after
   digest and every pending file its before digest, then continues. Rollback
   visits written files in reverse order and restores prior bytes—or removes a
   newly created file—only when current bytes exactly equal the recorded after
   digest. Drift marks `integration_conflict`, preserves that file, and stops;
   it never overwrites client-owned changes. Both modes are idempotent. Accepted
   canonical knowledge is never part of integration rollback.
10. Status and doctor derive truth from current canonical validation, current
    integration file digests, journal state, executable resolution, client
    trust, MCP/hook startup, and retrieval. States include
    `knowledge_applied_integration_pending`, `integration_previewed`,
    `integration_partial`, `integration_conflict`, `integration_complete`, and
    final `ready`. Only final ready completes onboarding. `lore remove` can
    reconcile complete or partial generated integrations using the same digest
    safety while preserving accepted canonical knowledge.

Verification:

- source priority, sparse/conflicting/large/offline/cancellation and two-agent
  proposal tests retained from 1.1;
- exact review transitions and canonical one-root reader/writer tests;
- injected crash, permission denial, disk-write failure, cancellation, and
  concurrent modification before and after every integration path/journal
  generation;
- resume and reverse compensation from every partial prefix on Windows, Linux,
  and macOS; newly created versus pre-existing file behavior; corrupted journal
  produces no write;
- client launch/reload during every prefix may observe incomplete integration
  but never yields ProjectLore `ready`; hook settings are written last;
- doctor/removal provide exact reconciliation and preserve unrelated content;
- existing `lore init` behavior and fixtures remain unchanged.

Rollback/cleanup: discard local packet/proposal before canonical activation. A
reviewed Git revert removes accepted canonical knowledge. Integration rollback
is separately previewed, digest-safe, and never automatic; conflicts require
normal manual review. Unreferenced immutable files and transaction journals are
cleaned only through a separate preview after no active root/journal references
them.

Non-goals: whole-repository atomicity, automatic trust, automatic rollback of
canonical knowledge, embedded model calls, hosted coordination, or silent
repair of user-edited integration files.

Exit gate: a clean unrelated repository reaches ready through both explicit
transactions; every fault prefix is recoverable or honestly conflicting; no
partial state claims ready; canonical readers observe only complete graph
generations; another agent follows the reported next action without private
instructions.

## Phase 4, 5, and 6 consequences

Phase 4 hook generation and Phase 5 sidecar registration enter only the
integration preview described above. Their individual trust receipts remain
invalid until the entire current integration bytes are reviewed. A sidecar or
hook failure never changes canonical readiness; it changes acquisition/passive
readiness and doctor reports the missing capability.

Replace any Phase 6 phrase that says onboarding applies all files atomically or
in one apply command with the two explicit transactions above. Add acceptance
tests for every integration prefix, journal generation, resume/rollback mode,
drift conflict, doctor state, removal state, and client launch observation.
The installed-artifact E2E must execute both previews and both applies.

## Corrected final reconciliation

- Requirements: 20 total; 20 Covered.
- Risks: 18 total; all dispositioned with prevention, recovery, proof, owner.
- Decisions: 10 total; 4 Resolved by authority, 4 Resolved by evidence, 2
  Recommended engineering choice, 0 Genuine human decision.
- Phases: 6; Phase 2 now has two explicit transaction/proof boundaries.
- Open product decisions: 0.
- Accepted limitation: client integration files cannot be atomically activated
  as a set. ProjectLore exposes and recovers partial state rather than making an
  impossible guarantee; canonical knowledge has its own single activation.
- Implementation remains prohibited until this exact three-component plan has
  a detached Ready review and verified handoff manifest.
