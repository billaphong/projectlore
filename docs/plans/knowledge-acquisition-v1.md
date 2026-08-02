# ProjectLore knowledge acquisition and continuous growth implementation plan

Plan ID: `projectlore-knowledge-acquisition`

Plan version: `1.0.0`

Status: frozen for independent review

Plan author: Codex primary agent

Decision authority: ProjectLore owner

## Requested outcome and boundary

ProjectLore must become useful at the start of a new-project onboarding and then
grow project and domain knowledge passively from normal development activity.
Initial injection must be part of onboarding; passive collection must not make
unreviewed inference authoritative or silently change enforced Rules.

Exact owner directions, encoded as UTF-8 without a trailing newline:

1. `if project or product knowledge can be grown passiively then thats exactly waht I want. However, any new project needs an injection at start. Otherwise, the time it takes for PL to get up to speed might be too long. I consider this part of onboarding`
   (`sha256:ff5d720baf7916c50ce9083826ac778a69f1f1569f2d338fa09b4ad14fe34b5c`)
2. `so right now the only way to inform projectlore with knowledge is for me or an agent to provide it with the knowledge explicitly? what triggers this though?`
   (`sha256:a082bd62d8881af1c9bcebd70e1d407ade0586b0943ad6576baf802da110b4bf`)

This plan covers deterministic source discovery, agent-neutral extraction
packets, reviewable proposals, safe promotion into canonical YAML, passive
lifecycle signals, read-only MCP visibility, onboarding integration,
compatibility, removal, tests, documentation, and pilot evidence.

It does not embed or select an AI model, call a model-provider API, silently
accept knowledge, make proposals enforceable, replace CodeGraph, add a hosted
service or UI, collect private transcripts/prompts, publish a package, or modify
Fraimed.

## Planning authority and repository identity

Precedence is: owner direction above; repository `AGENTS.md`; accepted
architecture and product invariants; current executable contracts; current
official client contracts; engineering recommendations in this plan.

Repository baseline is commit
`7354658a7e1424f18fdc5228e942371a781dc8af`. The inspected worktree also
contains the in-scope onboarding-documentation edits whose tracked diff hashes
to Git object `47168b837b2b31b6172fb2c45fe764b511ea5acc`, plus untracked
`docs/agent-onboarding.md` at
`sha256:9ade467009b462bf98680de9672a8d5ea96932c55a1e3d3f16ef300a257ae4ce`.
The unrelated untracked `docs/maintain-projectlore-model-skill.md` at
`sha256:be3621a1bb50a2f2ba4e0bcc68dfe2947756307e876d229ed677e49914a9b05f`
is explicitly excluded and must remain untouched.

Pinned governing repository sources:

| Source | SHA-256 at planning baseline | Authority |
| --- | --- | --- |
| `AGENTS.md` | `99bdec9fdc61cc16394b34a156456f89a21eb8fbde265372ea642108bce2740e` | Repository instructions and invariants |
| `README.md` including in-scope onboarding edit | `8243852ae9aba60907c81646d5060090f356db6dcd512b1b1d0a1bed240c55ba` | Current product behavior |
| `docs/architecture.md` | `932a91380c77a244b27e2e6c0463b7cd204ee69a5edcf56456fb9f0be15ce176` | Accepted architecture |
| `docs/agent-onboarding.md` | `9ade467009b462bf98680de9672a8d5ea96932c55a1e3d3f16ef300a257ae4ce` | In-scope cold-start runbook |
| `src/projectlore/onboarding.py` | `f9cb46613e32462645b8ea17364fc6d4f4a9d50a5165bcdde3a3a5a991197280` | Existing preview/apply initializer |
| `src/projectlore/models.py` | `b48acb662622aa11ad5ff1097f71eb4aca0d20a845e52b4dab44b71a5a8e4368` | Canonical structural contract |
| `src/projectlore/loader.py` | `2cac25508860873dc1331056dc651b7aa0aa7ef425221a0e73daed62c7232181` | Repository-confined model loading |
| `src/projectlore/mcp_server.py` | `cc777a8da1c9735bb5616900610404223e78635e117174e9bf5aacf2ed81ff24` | Current read-only MCP surface |
| `src/projectlore/hook.py` | `2dc49350a8b8646587ecb8ab12f7254291105e450352e9621fe19f526743b131` | Current blocking pre-action hook |
| `src/projectlore/scope_hook.py` | `b8f8ca09233488da6cf421f9afbcc21f0c47147b6a329b4f7df082bc775e3c4f` | Current advisory lifecycle hook |

Implementers must recompute raw-byte hashes before work and stop if semantic
source drift affects this plan.

Current external client evidence is pinned by URL and retrieval date
2026-08-01:

- OpenAI Codex manual sections for
  [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md),
  [hooks](https://learn.chatgpt.com/docs/hooks.md), and
  [MCP](https://learn.chatgpt.com/docs/extend/mcp.md). The current contract
  includes project-scoped trusted hooks, `PostToolUse`, `Stop`, and
  `SessionStart`, with all matching hooks running and command-hook trust bound
  to the hook definition.
- Anthropic's [hooks reference](https://code.claude.com/docs/en/hooks),
  [hooks guide](https://code.claude.com/docs/en/hooks-guide), and
  [MCP guide](https://code.claude.com/docs/en/mcp). The current contract
  confirms `PostToolUse`, `Stop`, project `SessionStart`, project-scoped MCP,
  and explicit project trust. Anthropic recommends a Stop-time working-tree
  scan when Bash may bypass per-edit matchers.

No governing conflict remains. Official client contracts must be rechecked at
implementation time because they are external and versioned independently.

## Authority labels used below

- **Requirement**: owner direction or higher-priority repository invariant.
- **Repository fact**: behavior reconstructed from the pinned source.
- **Inference**: conclusion that still requires proof.
- **Proposal**: recommended implementation mechanism, not product authority.
- **Open question**: unresolved issue; none may remain material at Ready status.

## Decision-resolution ledger

| ID | Question | Ladder evidence consulted | Alternatives and consequences | Recommendation | Classification | Authority/citation |
| --- | --- | --- | --- | --- | --- | --- |
| D01 | May passive acquisition directly alter accepted knowledge? | Owner wants passive growth; `AGENTS.md` makes reviewed YAML canonical and MCP reads non-mutating; models already distinguish inferred/suggested from asserted. | Auto-accept is low-friction but can invent enforceable meaning; proposal-only preserves authority. | Collect and prepare automatically, but promote only through digest-bound preview/apply and normal Git review. | Resolved by authority | `AGENTS.md` architectural invariants; owner direction 1 |
| D02 | Must ProjectLore embed an LLM provider? | Vendor neutrality, deterministic defaults, and no accepted AI provider contract; both clients can reason over files and MCP. | Embedded API makes onboarding one command but creates credentials, cost, privacy, and vendor coupling. Agent-neutral packets let the active client reason but require an agent turn. | Keep core deterministic; define a portable packet/proposal JSON contract consumed by Claude, Codex, or another agent. | Recommended engineering choice | `AGENTS.md`; `docs/architecture.md` |
| D03 | What constitutes passive triggering? | Both official clients support trusted project lifecycle hooks; Stop-time scan sees Bash edits; hooks may be unavailable or untrusted. | Background watcher adds lifecycle/resource complexity; blocking Stop harms workflow; advisory hooks are reversible and honest. | Non-blocking Stop scan plus SessionStart notification, content-digest deduplication, and explicit CLI fallback. | Resolved by evidence | Official hook docs above; current request-driven architecture |
| D04 | Where do candidates and accepted additions live? | Local generated state belongs under `.projectlore/`; canonical knowledge must be Git-tracked human-readable YAML; loader supports nested includes. | Rewriting arbitrary YAML loses comments; implicit overlays hide authority; immutable include fragments preserve reviewability. | Keep signals/packets/proposals ignored under `.projectlore/knowledge/`; promote accepted items into immutable `projectlore/knowledge/accepted/<id>.yaml` fragments referenced by a Git-tracked index. | Recommended engineering choice | `loader.py:79`; `AGENTS.md` |
| D05 | How should existing repositories migrate? | Current models can be flat or include-based; reads must never silently rewrite canonical files. | Force rewrite is unsafe; no migration strands existing projects. | Preview a one-time, digest-bound root include/index change; support the known safe YAML shapes and return a manual patch with diagnostics for unsupported formatting. | Recommended engineering choice | `loader.py`; preview/apply patterns in onboarding/workflow state |
| D06 | Should proposal data appear in ordinary knowledge answers? | Missing information must differ from empty; inferred suggestions must remain distinguishable; current MCP contract is stable at 0.4.0. | Mixing candidates into model search makes unaccepted knowledge look canonical. | Add separate read-only acquisition tools under a 0.5.0 additive contract; never mix proposals into canonical query or policy results. | Resolved by authority | `AGENTS.md`; `tool_spec.py:7` |
| D07 | How much repository content may scanning capture? | Loader and checker boundaries are bounded and root-confined; agent/client inputs may contain secrets. | Full snapshots improve extraction but duplicate secrets and inflate storage. | Packets contain prioritized paths, hashes, metadata, and bounded excerpts only for explicitly public text; default ongoing signals contain paths/hashes only. Never capture prompts, transcripts, environment, tool outputs, or ignored files. | Recommended engineering choice | Security invariants and official hook payloads |
| D08 | Does onboarding replace `lore init`? | `lore init` is public alpha behavior and creates only a skeleton; owner requires useful injection at start. | Mutating init semantics breaks previews; removing it breaks compatibility. | Retain `lore init`; introduce `lore onboard` as the recommended new-project workflow and version its independent contracts. | Resolved by evidence | `onboarding.py:14,29`; owner direction 1 |
| D09 | Who may approve a proposal? | Owner allows a person or agent to supply knowledge, while normal review and explicit mutation remain required. | Human-only blocks authorized autonomous workflows; silent agent approval violates authority. | CLI cannot infer identity or permission: require an explicit apply invocation, record actor-declared identity and proposal digest, and rely on repository authorization/Git review. Agents need explicit task authority to invoke apply. | Resolved by authority | Owner direction 2; `AGENTS.md` |
| D10 | Should a dedicated UI or hosted queue be added? | UI and hosted storage have not been earned; Git/local CLI/MCP are current surfaces. | UI/service increases deployment and privacy scope. | CLI, files, hooks, and read-only MCP only for this phase. | Resolved by authority | `docs/architecture.md`; accepted UI decision |

## Requirement coverage

| ID | Exact authority location | Required outcome or absence | Plan phase/step | Verification obligation | Status |
| --- | --- | --- | --- | --- | --- |
| R01 | Owner direction 1 | A new project receives a useful knowledge injection during onboarding, not only a skeleton. | P2.1-P2.6 | Clean-repository E2E yields reviewed project-specific domains, concepts, sources, relationships, and unknowns before integration is ready. | Covered |
| R02 | Owner direction 1 | Knowledge-growth signals arise passively from ordinary work. | P4.1-P4.6 | Real and fixture Claude/Codex lifecycle runs queue a deduplicated signal without an explicit scan command. | Covered |
| R03 | Owner directions 1-2 | An agent can transform evidence into structured candidate knowledge. | P1.1-P1.5, P2.4, P5.2 | Independent Claude and Codex pilots consume the same packet and produce schema-valid proposals. | Covered |
| R04 | `AGENTS.md` | Git-tracked, human-readable ProjectLore YAML remains the sole canonical project knowledge. | P3.1-P3.7 | Canonical queries ignore local proposal state before apply and discover accepted include fragments after apply. | Covered |
| R05 | `AGENTS.md` | Unreviewed inferred/suggested candidates never become asserted or enforceable. | P1.2, P3.2, P5.1 | Negative tests prove canonical search/context/policy results are byte-equivalent with candidate state present. | Covered |
| R06 | `AGENTS.md`; existing preview patterns | Every canonical mutation is explicit, reviewable, digest-bound, and race-safe. | P3.3-P3.7 | Preview/apply drift, replay, interruption, duplicate apply, and unsupported-root tests. | Covered |
| R07 | `AGENTS.md` | Every proposed assertion and relationship retains exact provenance. | P1.2-P1.5 | Proposal validation rejects missing, changed, escaped, ambiguous, or digest-mismatched evidence. | Covered |
| R08 | Product vendor-neutrality invariant | Claude Code and Codex use one client-neutral acquisition contract. | P1, P4, P5 | Cross-client normalized event/packet/proposal equivalence and two real-client pilots. | Covered |
| R09 | Standalone architecture | Acquisition works without Fraimed, CodeGraph, network, or provider credentials. | P2.1, P4.2, P6.3 | Environment-scrubbed offline E2E with provider variables absent. | Covered |
| R10 | Owner direction 1 | Passive growth handles duplication, contradiction, staleness, and repeated signals rather than accumulating noise. | P1.4, P3.2, P4.3-P4.5 | Deterministic duplicate/conflict/stale fixtures and queue-bound tests. | Covered |
| R11 | Onboarding product boundary | Readiness states whether baseline injection is pending, reviewed, applied, and retrievable. | P2.2-P2.6, P5.1 | `lore onboarding status` and `lore doctor` distinguish each state with stable diagnostics. | Covered |
| R12 | MCP read-only invariant | MCP may expose acquisition status/data but never mutate canonical or proposal files. | P5.1-P5.4 | Filesystem snapshots around every MCP tool call prove no writes. | Covered |
| R13 | Loader/checker security posture | Discovery and hooks are bounded, root-confined, symlink-free, secret-minimizing, and fail advisory. | P1.3, P2.1, P4.1-P4.6 | Hostile path, symlink, oversized corpus, binary, ignored-secret, cancellation, timeout, and malformed-event tests. | Covered |
| R14 | Existing public alpha contracts | `lore init`, eight 0.4.0 MCP tools, existing models, and existing integrations retain documented meaning. | P1.5, P2.6, P5.1, P6.1 | Frozen fixtures and full regression; new MCP surface uses 0.5.0 while 0.4.0 tools remain shape-identical. | Covered |
| R15 | Product privacy/trust boundary | No prompts, transcripts, tool responses, credentials, environment values, or ignored files are persisted by acquisition. | P1.3, P4.2-P4.4 | Canary-secret and payload-field absence tests inspect every emitted artifact. | Covered |
| R16 | Local-state/removal invariant | Disposable acquisition state stays under `.projectlore/`; removal is preview-first and preserves accepted canonical YAML. | P1.3, P3.1, P6.2 | Removal E2E deletes hooks/local acquisition state while accepted fragments and client-owned content remain. | Covered |
| R17 | Product usability | Onboarding produces explicit unknowns and contradictions instead of manufacturing certainty. | P1.2, P2.3-P2.5 | Low-evidence and conflicting-source pilot fixtures retain open questions and block asserted promotion. | Covered |
| R18 | Deterministic/default operation | Scans, merges, ordering, IDs, digests, previews, and diagnostics are reproducible. | P1-P4 | Repeated-run and cross-platform golden tests produce equivalent normalized artifacts. | Covered |
| R19 | Operational proportionality | Passive hooks remain fast, non-blocking, deduplicated, and bounded. | P4.3-P4.6 | Measured p95 no-change hook under 100 ms and changed-tree scan under 500 ms on the frozen pilot corpus; failures exit 0 with bounded advice. | Covered |
| R20 | Handoff expectation | Any agent can determine how and when to capture, review, and apply knowledge. | P5.2, P6.4 | Clean-agent usability script completes without private prompt or product-author intervention beyond explicit approval. | Covered |

Reconciliation: 20 unique requirements; 20 Covered; 0 Excluded by authority;
0 Decision needed; 0 Fact blocked; 0 Unverifiable.

## Current-system facts

| ID | Claim | Anchor | Method | Revision | Confidence or limitation |
| --- | --- | --- | --- | --- | --- |
| F01 | `lore init` previews seven target files and writes only through an explicit apply after digest/conflict checks. | `onboarding.py:14,29-84` | Direct source and onboarding tests | Baseline | High |
| F02 | The starter model is minimal and static; it does not inspect target-project knowledge. | `onboarding.py:242` | Direct source | Baseline | High |
| F03 | The canonical model already distinguishes asserted, inferred, and suggested status and models provenance, authority, trust, and anchors. | `models.py:16-207` | Direct source/schema | Baseline | High |
| F04 | Model loading is UTF-8, bounded, root-confined, symlink-free, SafeLoader-based, and supports nested explicit includes. | `loader.py:14-174` | Direct source/hostile tests | Baseline | High |
| F05 | Semantic validation owns duplicate identity, reference, provenance, authority, and lifecycle checks. | `validation.py:78,134-319` | Direct source/tests | Baseline | High |
| F06 | MCP currently exposes eight read-only tools under `projectlore-tools/0.4.0`, with normative runtime-schema equality tests. | `tool_spec.py:7-148`; `mcp_server.py:44-144`; `tests/test_agent_contracts.py:161` | Direct source/test | Baseline | High |
| F07 | Current initialization generates only SessionStart scope refresh and PreToolUse policy hooks. | `onboarding.py:187-223` | Direct source/test | Baseline | High |
| F08 | Event normalization already recognizes SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, and Stop with bounded inputs. | `hook_event.py:18-85` | Direct source/tests | Baseline | High; not currently wired for acquisition |
| F09 | Current Stop/PostToolUse hooks do not collect knowledge signals, and no proposal/discovery module exists. | `src/projectlore`; repository search | Full symbol/text search | Baseline | High |
| F10 | Long-lived MCP refresh validates on request and retains the last valid immutable snapshot after malformed edits. | `refresh.py:15-75`; `tests/test_refresh.py` | Direct source/test | Baseline | High |
| F11 | Removal previews generated integration/local state and preserves client-owned content. | `removal.py:24-155`; `tests/test_removal.py` | Direct source/test | Baseline | High; must be expanded |
| F12 | Both current official clients support trusted project lifecycle hooks including Stop and project-scoped MCP; hook availability/trust can still be disabled or withheld. | Official sources pinned above | Primary-source retrieval | 2026-08-01 | High but externally mutable |
| F13 | The verified alpha uses in-memory operation; no watcher, database, embeddings, hosted service, or UI has been earned. | `README.md`; `docs/architecture.md` | Direct docs/pilot decision | Baseline | High |
| F14 | Existing local state is ignored by `.projectlore/*`, except two explicitly tracked policy-binding files. | `.gitignore` | Direct source | Baseline | High |

## Risk coverage

| ID | Scenario | Boundary | Prevention/detection | Recovery/rollback | Proof | Owner/status |
| --- | --- | --- | --- | --- | --- | --- |
| K01 | Inference is presented or enforced as accepted fact. | Proposal to canonical/policy | Separate contracts/stores; candidate statuses limited to inferred/suggested; no proposal reads in canonical services. | Delete local proposal; revert accepted Git fragment through normal review. | Negative canonical query/policy equivalence tests. | Implementer / Covered |
| K02 | Scan captures secrets, prompts, transcripts, environment, tool output, ignored or binary files. | Hooks/scanner/artifacts | Path/hash-only ongoing signals; Git-ignore filter; text/binary and sensitive-name filters; no transcript-path dereference; bounded public excerpts only in explicit baseline packets. | Purge local acquisition state with removal; rotate any exposed credential under repository incident process. | Canary corpus inspects every output byte. | Implementer + security reviewer / Covered |
| K03 | Path traversal, symlink, race, or include escape writes outside root. | Scanner/proposal apply | Reuse root confinement and symlink rejection; open/read/hash verification; exact before digests; atomic same-directory replace. | Abort without activation; preserve prior files; remove temp file. | Adversarial filesystem and race tests. | Implementer / Covered |
| K04 | Concurrent hooks corrupt or lose the queue. | Local signal persistence | Per-record immutable files or atomic append protocol with lock timeout; content-addressed IDs; idempotent retry; bounded queue. | Re-scan current Git state from last committed/observed cursor; quarantine malformed records. | Multiprocess stress and interruption tests. | Implementer / Covered |
| K05 | Stop hook delays or prevents agent completion. | Client lifecycle | No network/model calls; no blocking decision; strict timeout; no-change fast path; advisory exit 0 on all operational failures. | Disable/remove hook; CLI scan remains available. | Real-client stop behavior and latency budgets. | Implementer / Covered |
| K06 | Repeated sessions create proposal spam. | Signals/proposals | Digest identity over repo/model/base/changed paths; debounce; duplicate/supersession ledger; queue limits. | Compact disposable duplicates; never delete canonical knowledge. | Repetition and cross-client equivalence tests. | Implementer / Covered |
| K07 | Stale proposal applies to changed evidence/model. | Promotion | Bind base model digest, source-manifest digest, exact source hashes, target index/root digests, and proposal digest. | Rebase by generating a new proposal identity; old proposal remains rejected/stale. | Replay/model/source drift tests. | Implementer / Covered |
| K08 | Automatic YAML rewrite loses comments or user formatting. | Canonical promotion | Immutable accepted fragments; small tool-owned index; one-time root migration supports only proven shapes and otherwise emits a manual patch. | Git revert; apply must be atomic and previewed. | Comment-preservation and unsupported-shape tests. | Implementer / Covered |
| K09 | Existing init/MCP/model consumers break. | Public contracts | Keep init behavior; independently version onboard/acquisition/proposal contracts; additive MCP 0.5.0 with frozen 0.4 tool shapes. | Feature can be disabled; revert additive integration while canonical model remains valid. | Golden compatibility fixtures/full suite. | Implementer / Covered |
| K10 | Client hook schemas or trust behavior drift. | Claude/Codex integration | Capability matrix version bump; official-doc recheck; generated configs tested against installed minimums; explicit trust invalidation. | Degrade to CLI/manual triggers; do not claim passive activation. | Current-client local acceptance plus config parsers. | Implementer / Covered |
| K11 | A low-evidence baseline creates false confidence. | Onboarding readiness | Coverage/unknown/conflict report; minimum provenance thresholds; no automatic authoritative trust; readiness requires reviewed apply and retrieval probe. | Reject/revise proposal; skeleton remains usable but status says baseline pending. | Sparse/conflicting pilot corpora. | Product owner + implementer / Covered |
| K12 | Baseline scan is too slow or large. | Source inventory | Git-aware prioritization; documented caps; deterministic truncation; cancellation; incremental hashes. | Resume with narrower include/exclude config; no partial apply. | Frozen large-corpus resource test. | Implementer / Covered |
| K13 | An unauthorized agent applies knowledge. | CLI/Git boundary | Preview is default; apply requires proposal digest and actor declaration; managed instructions say explicit task authority required; no MCP mutation. | Git review/revert; local audit receipt identifies actor declaration and proposal digest. | Absence tests for read paths; CLI authority messaging. | Repository owner / Covered |
| K14 | Accepted fragment index or model version update partially commits. | Multi-file apply | Stage all bytes, fsync where supported, write fragments before index/root activation, rollback temp/staged files if activation fails; activation point is root/index digest change. | Retry idempotently or Git revert; loader never observes an index reference before fragment existence. | Fault injection at every write boundary. | Implementer / Covered |
| K15 | Local rejection/duplicate memory disappears on another machine. | Team workflow | First release treats local queue as disposable; accepted model is shared. Proposal export/import is content-addressed and explicit; no claim of shared hosted inbox. | Re-scan/dedupe against canonical model. | Fresh-clone scan does not duplicate accepted IDs/meaning. | Product owner / Accepted limitation |
| K16 | CodeGraph/Fraimed absence disables acquisition. | Optional adapters | Scanner uses Git/files only; adapters enrich evidence behind explicit availability states. | Continue with partial packet and explicit missing dependency. | Provider-free tests. | Implementer / Covered |
| K17 | Cancellation or process termination leaves misleading completion. | Scan/extraction/apply | Propagate cancellation; write completion marker last; statuses distinguish pending/partial/complete. | Resume or discard incomplete local session. | Cancellation tests at each lifecycle stage. | Implementer / Covered |
| K18 | Distribution omits protocols/docs/entrypoint. | Packaging | Update pyproject allow-list and offline smoke to exercise acquisition commands and hook entrypoint. | Block release candidate. | Wheel/sdist and no-index clean-project E2E. | Release owner / Covered |

Reconciliation: 18 unique risks; 18 have prevention, recovery, proof, and owner;
0 undispositioned. Identity/authorization, isolation, integrity, migration,
external side effects, partial failure, retry/idempotency, concurrency,
compatibility, resources, observability, deployment, and rollback are covered.
No network database or hosted migration applies.

## Phase 1 — Freeze acquisition contracts and local state boundary

Objective: define the portable data and state contracts before client or model
behavior changes. Covers R03-R10, R12-R18.

Entry conditions: baseline and worktree identities above still match, or drift
has been reconciled into a new plan; official hook contracts have been
rechecked; no implementation begins from the unrelated skill draft.

Targets:

- new `src/projectlore/knowledge_contracts.py` for versioned strict types;
- new `src/projectlore/knowledge_state.py` for confined local persistence;
- generated definitions in `schemas/projectlore.schema.json` without changing
  canonical model version merely for local acquisition contracts;
- new frozen fixtures under `tests/fixtures/knowledge/`;
- `.gitignore`, public compatibility documentation, and schema tests.

Ordered steps:

1. Define independent literals for acquisition session, source manifest,
   signal, packet, proposal, candidate, conflict, review receipt, and apply
   preview. Every object carries its own version, content digest, repository
   identity, trigger, timestamps where semantically needed, and explicit
   completion state.
2. Restrict candidate knowledge status to `suggested` or `inferred`. Require
   evidence records with root-relative path, source kind, exact content hash,
   and line/range or whole-file scope. Require confidence rationale, proposed
   domain, and detected conflicts/unknowns; Rules additionally require an
   explicit authority candidate and cannot enter any policy registry.
3. Store disposable state only beneath `.projectlore/knowledge/` using
   root-confined, symlink-free, size/file/count/depth limits no weaker than the
   model loader. Define immutable content-addressed records, atomic writes,
   bounded locks, completion markers, quarantine, and deterministic ordering.
4. Define identity and reconciliation: repeated identical signals collapse;
   proposals bind source and base-model digests; exact canonical duplicates are
   suppressed; semantic/name collisions become review conflicts; accepted,
   rejected, superseded, and stale records are never confused.
5. Freeze valid, hostile, legacy-absence, unknown-version, and cross-client
   fixtures. Record additive contract compatibility separately from canonical
   schema and current MCP contracts.

Verification: strict Pydantic/schema equality; round-trip and unknown-version
tests; property/differential digest tests; symlink/path/size/node/file attacks;
multiprocess writer/fault injection; secret-canary absence; canonical service
snapshots proving local state has no effect.

Rollback: contracts are additive and unused until later phases. Remove the new
modules/schema definitions/local state; no canonical file has changed.

Non-goals: scanning, LLM extraction, hooks, proposal promotion, and MCP tools.

Exit gate: all contract fixtures and boundary tests pass; requirement/risk IDs
map to executable obligations; a security review confirms candidate data cannot
reach canonical query or enforcement paths.

## Phase 2 — Build baseline discovery and useful onboarding injection

Objective: make a new project produce a substantial, evidence-bound baseline
proposal before ProjectLore integration claims readiness. Covers R01, R03,
R07-R09, R11, R13-R15, R17-R20.

Entry conditions: Phase 1 contracts frozen; target repository is a Git worktree
or explicitly reported non-Git unsupported state; `lore init` fixtures remain
frozen.

Targets:

- new `src/projectlore/knowledge_scan.py` and
  `src/projectlore/knowledge_onboarding.py`;
- `src/projectlore/cli.py` for `lore onboard start|status|packet|preview|apply`;
- `src/projectlore/onboarding.py` only for shared preview primitives, not a
  silent semantic change to `lore init`;
- new onboarding/discovery tests and synthetic sparse/conflicting/large repos;
- `docs/agent-onboarding.md` and getting-started documentation.

Ordered steps:

1. Implement a Git-aware deterministic source inventory. Prioritize repository
   instructions, README, architecture/product/spec/ADR docs, schemas/public
   interfaces, domain-named source, invariant-bearing tests, and existing model
   files. Exclude ignored, secret-shaped, binary, generated, vendor, VCS, and
   local-state paths. Record dirty status and hashes. Apply explicit byte/file/
   excerpt/time limits and deterministic truncation; cancellation writes no
   completed packet.
2. `lore onboard start --name NAME` creates only a local acquisition session
   and source packet. It does not create MCP/hooks/canonical YAML. `status`
   reports `not_started`, `packet_ready`, `proposal_ready`, `reviewed`,
   `applied`, or `stale`, with reasons and unknown/conflict counts.
3. The packet specifies the agent task without provider-specific prompting:
   identify project purpose, domains, terms, concepts, relationships, accepted
   Rules, sources, authority, anchors, contradictions, and unknowns; cite only
   packet-manifest evidence; never promote repository behavior into desired
   behavior without authority.
4. Add `lore knowledge propose PROPOSAL.json` as a non-canonical boundary. It
   validates exact packet/base identities, evidence, candidate statuses,
   duplicate/conflict analysis, bounds, and source drift. The active Claude,
   Codex, or other agent authors the same portable JSON; ProjectLore performs no
   model-provider call.
5. `onboard preview` renders the complete initial canonical model and accepted
   fragment/index layout plus existing seven integration files. It reports
   coverage, conflicts, unknowns, every proposed assertion, before/after
   digests, and the exact proposal digest. It refuses asserted Rules with
   unresolved authority/evidence and refuses readiness while material conflicts
   are unresolved.
6. `onboard apply --proposal-digest ... --actor ...` rechecks all bytes and
   atomically applies exactly the reviewed preview. Existing `lore init`
   remains behavior-compatible and is documented as skeleton-only; onboarding
   becomes the recommended new-project path.

Verification: clean Git repository end-to-end; dirty and non-Git diagnostics;
source-priority goldens; sparse/conflicting repos; ignored secret and transcript
canaries; large corpus/cancellation; two independent agent-produced proposals
against one frozen packet; preview/apply drift/interruption; exact existing init
fixtures; offline operation with all provider variables removed.

Rollback: before apply, delete disposable session. After apply, use existing
preview-first removal for integration and Git revert for canonical files. No
partial apply may be observable.

Non-goals: automatic model calls, passive hooks, ongoing promotion, or hosted
source ingestion.

Exit gate: a clean unrelated repository reaches `applied`, validates, and
answers a real task with project-specific provenance; a sparse repository
remains honestly `proposal_ready` or blocked with unknowns rather than being
declared ready.

## Phase 3 — Add review, conflict resolution, and safe canonical promotion

Objective: turn ongoing agent suggestions into explicit, replay-safe canonical
Git changes without rewriting arbitrary YAML. Covers R04-R07, R10, R14-R18.

Entry conditions: Phase 2 establishes baseline/index layout and Phase 1
proposal identities.

Targets:

- new `src/projectlore/knowledge_review.py` and
  `src/projectlore/knowledge_apply.py`;
- CLI `lore knowledge list|show|review|preview|apply|reject|export|import`;
- Git-tracked `projectlore/knowledge/index.yaml` and immutable
  `projectlore/knowledge/accepted/*.yaml` convention;
- `loader.py` only if diagnostics/location handling for the explicit nested
  index needs correction, never for an implicit overlay;
- model/semantic validation and promotion tests.

Ordered steps:

1. For newly onboarded projects, root YAML explicitly includes
   `projectlore/knowledge/index.yaml`; the index explicitly includes immutable
   accepted fragments. For existing repositories, generate a one-time root
   migration preview. Only known block/no-include shapes are auto-applicable;
   complex/aliased/flow formatting gets a deterministic manual patch and no
   write.
2. Compare candidates with the current immutable model by stable ID, normalized
   preferred term/name, subject-predicate-object identity, Rule meaning, source
   digest, and supersession fields. Classify exact duplicate, compatible
   addition, update/supersession, conflict, stale evidence, or insufficient
   authority. Never use fuzzy similarity to auto-accept.
3. `review` records per-candidate accept/reject/revise decisions locally with
   actor declaration and rationale. Accept means eligible for preview, not yet
   canonical or asserted. Reject/supersede prevents local re-prompting for the
   same evidence digest but remains disposable.
4. `preview` renders an immutable accepted fragment, index/root/model-version
   changes, semantic validation result, and complete Git-visible diff. It binds
   proposal, review, model, source, root, and index digests. Canonical accepted
   items receive `asserted` only at this explicit promotion boundary; proposed
   authority/trust is copied only when the review explicitly accepts it.
5. `apply` requires the exact preview/proposal digest and actor declaration,
   verifies authorization messaging, stages all files, validates the staged
   complete model, writes fragment first, and atomically activates index then
   root/model version. Define the interruption recovery marker and idempotent
   retry. Any drift produces a new preview identity.
6. Existing long-lived MCP activates a valid accepted fragment on its next
   request; malformed/manual changes remain last-valid with diagnostics. Local
   proposals never appear in that refresh path.
7. Export/import transfers one content-addressed proposal without granting
   acceptance. Fresh clones deduplicate new scans against canonical accepted
   IDs and evidence.

Verification: all classification fixtures; preview/apply/replay/race tests;
fault injection before/after every multi-file write; comment preservation;
manual migration fallback; duplicate IDs/references/provenance; model-version
bump; long-lived refresh; Git diff inspection; canonical query/policy absence
before and presence after apply.

Rollback: accepted fragments are immutable and reverted through Git. Apply
failure removes unreferenced staged/temp fragments and restores prior index/root
bytes. Rejected/local records may be discarded without changing canonical
knowledge.

Non-goals: automatic acceptance, semantic vector deduplication, shared hosted
review, or rewriting user-owned model files wholesale.

Exit gate: every accepted candidate has a reproducible evidence-to-review-to-
fragment chain, every failure leaves the old model valid, and a Git revert fully
removes the accepted meaning.

## Phase 4 — Wire passive, non-blocking development triggers

Objective: create useful acquisition signals from ordinary work without asking
the user to remember a command and without delaying or controlling the agent.
Covers R02, R08-R10, R13-R16, R18-R19.

Entry conditions: Phase 1 state can tolerate concurrent/repeated events; Phase
3 can reconcile signals/proposals; current official hook contracts have been
revalidated and capability minimums updated.

Targets:

- new `src/projectlore/knowledge_hook.py` entrypoint;
- `pyproject.toml` console scripts and package verification;
- `onboarding.py` generated Claude/Codex `Stop` and `SessionStart` entries;
- `hook_event.py` only for normalized fields proven common across clients;
- `removal.py`, `trust.py`, `doctor.py`, client capability JSON, and hook tests.

Ordered steps:

1. Define a shared command hook that accepts bounded JSON and dispatches only
   `Stop` and `SessionStart`. It ignores transcript paths, last messages,
   prompts, tool inputs/responses, and environment content. It confines `cwd`
   to the Git root and sanitizes inherited environment before file inspection.
2. On Stop, compute a Git-status/source-manifest delta from the last completed
   cursor, including changes made through Bash. Store only path/status/hash and
   model/HEAD identity. If nothing relevant changed or an identical signal
   exists, perform no write. Never block Stop; malformed input, timeout, lock
   contention, cancellation, or scan failure exits advisory 0 with bounded
   diagnostics and no completed marker.
3. Apply deterministic relevance rules: always signal changes to project
   instructions, specs/ADRs/docs, schemas/public contracts, canonical model,
   accepted implementation-anchor paths, policy bindings, and tests linked by
   existing sources/anchors; summarize other changed paths in a bounded catchall
   so domain knowledge is not silently missed. Record why each path qualified.
4. Enforce queue count/byte/age bounds, content-addressed dedupe, cooldown, and
   safe compaction of disposable duplicates. Never compact an unprocessed
   distinct signal without an explicit overflow diagnostic.
5. On SessionStart, do no extraction. Return bounded context stating pending
   count, oldest age, and the exact `lore knowledge packet next` command. If
   hooks are untrusted/disabled, doctor reports passive acquisition inactive
   and the CLI `lore knowledge scan --since REF` remains equivalent.
6. Generate both clients' entries preview-first, preserve unrelated hooks, bump
   integration/capability versions, invalidate trust receipts on config drift,
   and make removal delete the acquisition hook plus disposable state while
   retaining canonical accepted fragments.

Verification: official native event fixtures; Bash-created, Write/Edit-created,
no-change, subdirectory, detached HEAD, dirty baseline, malformed Git, lock,
parallel hook, repeated Stop, and SessionStart cases; payload canaries; command
resolution/offline installed-wheel smoke; real current Claude/Codex trust and
hook runs. Benchmark on the frozen corpus: p95 under 100 ms no-change and under
500 ms changed-tree, with recorded machine/corpus/methodology.

Rollback: preview-first `lore remove` removes generated acquisition hooks and
local state. Disabling hooks loses passive collection only; explicit scan and
all canonical ProjectLore behavior continue.

Non-goals: blocking Stop, background watchers, transcript parsing, model calls,
network, or claims of unbypassable enforcement.

Exit gate: ordinary edits in each real client create one equivalent pending
signal without a manual scan; no-change sessions create none; failures do not
delay or block the client; doctor reports exact activation/trust state.

## Phase 5 — Expose acquisition to agents without weakening MCP

Objective: let any agent notice and process acquisition work through the same
read-only contract and durable repository instructions. Covers R03, R05, R08,
R11-R12, R14-R15, R20.

Entry conditions: Phases 1-4 define immutable local reads and passive signals;
MCP compatibility policy has approved an additive 0.5.0 surface.

Targets:

- `tool_spec.py`, `mcp_server.py`, and service composition;
- new read-only tools `knowledge_status`, `knowledge_get_packet`, and
  `knowledge_get_proposal`;
- managed `AGENTS.md`/`CLAUDE.md` blocks in `integration.py`;
- MCP contract fixtures and agent-contract tests;
- CLI/MCP parity documentation.

Ordered steps:

1. Publish `projectlore-tools/0.5.0` with exact normative schemas for three
   read-only tools. Status returns acquisition phase, counts, activation/trust,
   missing dependencies, and distinct missing-versus-empty states. Packet and
   proposal reads require content IDs, enforce output bounds/redaction, and
   return provenance/trigger/base digests. No MCP tool submits, reviews,
   rejects, applies, deletes, scans, or advances a cursor.
2. Update managed agent instructions with the acquisition protocol: inspect
   pending status at task start; use the packet and repository evidence;
   author portable candidate JSON; use CLI mutation only with task authority;
   never claim inferred knowledge as asserted; validate/review canonical diffs.
   Keep the block concise enough for Codex's instruction budget and compatible
   with nested overrides.
3. Ensure CLI and MCP read the same immutable state/parser and return matching
   IDs/digests. Provider adapters remain optional and cannot promote evidence.
4. Preserve exact normalized schemas and responses for the eight existing
   0.4.0 tools. Verify all MCP reads, including malformed requests, leave model,
   local state, cursors, and proposal bytes unchanged.

Verification: normative schema/runtime equality; frozen 0.4 fixtures; MCP/CLI
parity; found/empty/missing/stale distinctions; traversal/output limits;
filesystem before/after snapshots; prompt-like and secret-bearing candidate
redaction; Codex instruction-chain and Claude managed-block acceptance.

Rollback: disable/remove new tools and managed text in a contract-major-aware
revert; CLI acquisition remains available and canonical data remains valid.

Non-goals: write-capable MCP, MCP-triggered scanning, agent-vendor prompts, or
serving candidate knowledge through canonical search/context/policy tools.

Exit gate: both clients discover the same pending packet and proposal through
MCP, existing tools are unchanged, and no read mutates any file.

## Phase 6 — Prove product behavior, package, and document the handoff

Objective: demonstrate that initial injection is fast enough to be onboarding
and passive growth remains useful, safe, and portable in real projects. Covers
all requirements, with emphasis on R01-R03, R08-R11, R18-R20.

Entry conditions: all prior phase gates pass independently; no unresolved
Critical/High security or data-loss finding; test authorship has frozen the
cross-layer acceptance suite before production implementation begins.

Targets:

- independent acceptance tests and frozen synthetic corpora;
- retained Homebrew and Sienna pilots plus one clean unrelated repository;
- `scripts/offline_smoke.py`, distribution allow-list, CI matrix, security and
  license reports;
- README, architecture, onboarding, compatibility, migration, security,
  removal, and acquisition protocol documentation;
- versioned release manifest only if later authorized.

Ordered steps:

1. Run the complete regression, lint, strict typing, schema drift, valid/hostile
   examples, and frozen 0.4 compatibility suites on every supported Python/OS
   matrix entry.
2. Build wheel/sdist from the exact clean candidate, verify allow-lists, install
   with `--no-index`, resolve all five console entrypoints, and execute clean
   onboarding, MCP transport, passive hook, proposal, promotion, refresh, and
   removal flows from the installed artifact.
3. Run a provider-free baseline and passive-growth pilot in Homebrew and Sienna;
   then run one independently selected unrelated repository. Record source
   coverage, unknown/conflict rate, time to first useful context, proposal
   acceptance/rejection, duplicate rate, false-positive signal rate, hook
   latency, and whether another agent answers frozen domain questions using
   accepted provenance. Do not tune on held-out questions after retrieval.
4. Exercise current Claude Code and Codex locally with reviewed project hooks:
   baseline packet consumption, proposal creation, real MCP reads, ordinary
   code/doc edit, passive signal, next-session notice, review/apply, and
   canonical rediscovery. Record client versions and distinguish real-client
   evidence from fixture tests.
5. Update onboarding so a new agent follows one primary path, knows installation
   versus project scope, understands the review boundary, can diagnose disabled
   passive hooks, and can remove the feature without deleting canonical
   knowledge.
6. Require independent security review of data capture and independent product
   review of false knowledge/confidence. Publication, tags, hosted mutation, or
   a release designation remain separate owner decisions.

Verification thresholds:

- all matrix and offline-artifact gates pass;
- initial injection reaches validated project-specific context in one
  onboarding workflow, with every assertion sourced and material unknowns
  visible;
- both real clients produce contract-valid proposals from the same packet and
  rediscover an accepted correction on the next MCP request;
- 0 secret/transcript/prompt/tool-output canaries appear in any acquisition
  artifact;
- 0 candidate Rules affect policy before explicit promotion;
- 0 lost/corrupt canonical states across injected write failures;
- duplicate passive signals are 0 after content-addressed reconciliation;
- measured hook budgets from R19 pass;
- false-positive/false-negative trigger observations are reported, not hidden;
  the owner explicitly accepts pilot quality before release designation.

Rollback: acquisition is additive. Remove generated hooks and disposable state,
retain or Git-revert accepted fragments, and revert the package version if the
pilot fails. No hosted data requires cleanup.

Non-goals: PyPI/GitHub publication, hosted service, UI, database, embeddings,
automatic acceptance, or replacement of the established canonical model.

Exit gate: independently authored acceptance evidence and independent final
verification establish every requirement; owner accepts the measured
acquisition quality; exact artifacts remain unpublished unless separately
authorized.

## Deployment, compatibility, and observability sequence

The feature remains unreleasable until Phase 6 because intermediate phases may
introduce unused contracts or local commands without complete lifecycle
integration. Each phase must be a coherent reviewable commit and keep the old
product fully working. Enable passive hooks only after contracts, recovery, and
removal are present. Existing repositories opt into `lore onboard` or the
one-time acquisition-index migration; no read operation performs migration.

Operational status is local and honest: onboarding state, last completed scan,
pending counts/bytes/oldest age, duplicate/overflow counts, hook activation and
trust, last advisory failure code, proposal conflict/stale counts, and accepted
model digest. It contains no source contents or private agent data. Diagnostics
use stable machine codes and bounded prose. Ordinary hooks and local scans do
not claim repository certification.

## Implementation handoff and independent evidence

This change is contract-sensitive, cross-layer, authorization-related,
migration/recovery-heavy, and client-integrated. After this plan package is
Ready, invoke the separate `author-tests` workflow before production
implementation. Give that author R01-R20, K01-K18, observable boundaries,
pinned authority, and pilot thresholds—but not this plan's private mechanism or
file-by-file steps. The test author must be distinct from planner, implementer,
and final verifier.

Implementation must stop and return to planning if official client hooks no
longer provide a non-blocking Stop plus SessionStart path, if safe root-index
migration cannot preserve user YAML, or if a useful baseline requires choosing
an embedded model/provider. Those are material behavior/scope changes, not
implementation details.

## Final reconciliation

- Requirements: 20 total; 20 Covered; 0 excluded; 0 decision-needed; 0
  fact-blocked; 0 unverifiable.
- Risks: 18 total; 18 dispositioned with owner and proof.
- Decisions: 10 total; 4 Resolved by authority, 2 Resolved by evidence, 4
  Recommended engineering choice, 0 Genuine human decision.
- Phases: 6 dependency/proof gates.
- Open product decisions: 0.
- Known accepted limitation: pending/rejected proposal memory is local in this
  release; accepted canonical knowledge is shared through Git, and explicit
  content-addressed proposal export/import is available.
