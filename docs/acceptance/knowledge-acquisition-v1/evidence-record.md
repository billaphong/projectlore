# Knowledge acquisition v1 acceptance evidence record

## Package identity and independence

- Evidence package: `projectlore-knowledge-acquisition-acceptance/0.1.0`
- Supersedes: none
- Baseline source revision: `c02b1cc761014c37ccf8c6f0a12284bb7c78cf4c`
- Future candidate revision: to be populated by the separate final reviewer
- Verdict timestamp: `2026-08-01T00:00:00-05:00`
- Test author: `/root/knowledge_plan_grader_v12/knowledge_acceptance_author`, clean acceptance-only context
- Intended implementer: Codex root, per contract; no implementation context supplied
- Final reviewer: independently assigned, not this author or implementer
- Role separation: Pass for authoring; final-review identity remains unassigned
- Materials: repository instructions, pinned authority commit, governing contract, ordered plan composition and detached package
- Contamination: none; no implementation rationale, patch, transcript, private mechanism, or suggested tests supplied
- Independence authority: governing contract Header and Verification contract
- Observable boundary: Python 3.11 repository CLI and frozen core MCP specification on Windows
- Excluded production paths: `src/`, schemas, examples, runtime configuration, migrations, generated outputs
- Permitted paths: `tests/acceptance/` and `docs/acceptance/knowledge-acquisition-v1/`

## Authority registry

| ID | Rank and owner | Source | Pin | Limitation |
|---|---|---|---|---|
| A1 | 1, repository owner | `AGENTS.md` | Git blob at `c02b1cc761014c37ccf8c6f0a12284bb7c78cf4c` | Repository policy |
| A2 | 2, contract author | `docs/contracts/knowledge-acquisition-v1.md` | Git blob at `c02b1cc761014c37ccf8c6f0a12284bb7c78cf4c` | Observable contract |
| A3 | 3, plan owner | ordered `docs/plans/knowledge-acquisition-v1.md` through `v1.12.md` | Thirteen hashes in `docs/plans/knowledge-acquisition-v1.12.handoff.json` | Later amendments supersede conflicts |
| A4 | 4, independent plan grader | `docs/plans/knowledge-acquisition-v1.12.review.md` and handoff | Git blobs at pinned revision | Plan readiness, not product acceptance |
| A5 | 5, architecture owner | `docs/architecture.md` | Git blob at pinned revision | Supporting invariant authority |

## Requirement registry and matrix

All 27 unique contract rows are in scope; there are no exclusions.

| Requirements | Evidence rows | Status |
|---|---|---|
| KA-01 | E-KA01 | Handoff-ready |
| KA-02, KA-03, KA-06, KA-11, KA-12 | E-KA02, E-KA03, E-KA06, E-KA11, E-KA12 | Not ready: reachability only |
| KA-10 | E-KA10A, E-KA10B | Handoff-ready only for frozen-core/read-only subclaims |
| KA-04, KA-05, KA-07, KA-08, KA-09, KA-13, KA-14 | B-KA04, B-KA05, B-KA07, B-KA08, B-KA09, B-KA13, B-KA14 | Not ready |
| KO-01..KO-07 | B-KO01..B-KO07 | Not ready |
| KR-01..KR-06 | B-KR01..B-KR06 | Not ready |

## Evidence rows

| Row | Requirement | Authority | Oracle | Boundary/level | Authorship and test | Baseline/run | Sensitivity | Freeze/lifecycle |
|---|---|---|---|---|---|---|---|---|
| E-KA01 | KA-01 | A1,A2 | Asserted | installed CLI / integration | Executable; `test_core_read_does_not_create_acquisition_state` | Already satisfied | Proven: successful real read plus absent state path | Complete/Frozen |
| E-KA02 | KA-02 | A2,A3 | Asserted | installed CLI / smoke | Executable; `test_required_public_workflow_is_reachable[KA02-onboard]` | Expected red | Proven for reachability only | Complete/Frozen |
| E-KA03 | KA-03 | A2,A3 | Asserted | installed CLI / smoke | Executable; `[KA03-knowledge]` | Expected red | Proven for reachability only | Complete/Frozen |
| E-KA06 | KA-06 | A2,A3 | Asserted | installed CLI / smoke | Executable; `[KA06-knowledge]` | Expected red | Proven for reachability only | Complete/Frozen |
| E-KA10A | KA-10 | A2 | Asserted | source-distributed MCP contract / contract | Executable; `test_core_mcp_contract_remains_frozen` | Already satisfied | Proven by exact version and raw-byte discriminator | Complete/Frozen |
| E-KA10B | KA-10 | A2 | Asserted | installed CLI / integration | Executable; `test_core_read_does_not_create_acquisition_state` | Already satisfied | Proven by successful read and state absence | Complete/Frozen |
| E-KA11 | KA-11 | A2,A3 | Asserted | installed CLI / smoke | Executable; `[KA11-onboard]` | Expected red | Proven for reachability only | Complete/Frozen |
| E-KA12 | KA-12 | A2,A3 | Asserted | installed CLI / smoke | Executable; `[KA12-knowledge]` | Expected red | Proven for reachability only | Complete/Frozen |
| B-KA04..B-KA14 (listed above), B-KO01..B-KO07, B-KR01..B-KR06 | respective | A2,A3 | Asserted | concurrency/fault/client/package boundaries | Authoring blocked: the committed composition does not freeze a public output schema, fixture corpus, fault-control boundary, real-client version, or executable model-check harness sufficient to encode implementation-independent observations | Not run | Not assessed | Incomplete/Draft |

The blocked aggregate represents **20** rows: seven remaining KA rows, seven KO rows, and six KR rows. Each retains its individual ID above; aggregation does not merge requirements.

## Baseline and sensitivity evidence

- Selection: `.venv/Scripts/python.exe -m pytest --collect-only -q tests/acceptance/test_knowledge_acquisition_contract.py` selected 7 cases, no skips or retries.
- Execution: `.venv/Scripts/python.exe -m pytest -q tests/acceptance/test_knowledge_acquisition_contract.py` produced five expected-red missing-command cases and two passing core/read cases after harness correction.
- Baseline suite: 249 selected; 242 passed, 6 skipped, 1 pre-existing failure in `tests/test_product_terminology.py::test_adapter_name_occurs_only_in_reviewed_paths` caused by already-committed authority/plan documentation absent from its allowlist.
- Sensitivity discriminator: invoking a missing argparse command returns exit 2 and names the invalid choice; a registered command help must return 0. The core pin changes on any raw-byte drift. The read probe reached `model-status` successfully and would fail if `.projectlore/knowledge` were created.
- No production mutation or fault injection was performed.

## Freeze summary

- Manifest: `docs/acceptance/knowledge-acquisition-v1/freeze-manifest.json`
- Attestation: `docs/acceptance/knowledge-acquisition-v1/handoff-attestation.md`
- Runtime: CPython from `.venv`, pytest 8.x, Windows; dependency meaning pinned by `pyproject.toml` and installed environment identity recorded in the manifest.
- Unfrozen dependencies: the 19 blocked rows' missing public schemas/harnesses and final real-client/environment identities.
- Package freeze closure: Incomplete
- Authoring closure: Incomplete (20 contract rows authoring-blocked)
- Executable-baseline closure: Complete for 7 authored cases; incomplete for the contract
- External-acceptance closure: Incomplete (real Claude/Codex and installed-wheel boundaries absent)
- Capability tier: Procedural

## Reconciliation and verdict

`27 declared = 27 in scope + 0 exclusions`; `27 in scope = 2 partially handoff-ready requirements + 25 not-ready requirements`; required evidence is not yet fully authored.

- Verdict: **Not ready**
- Authorship result: **Incomplete**
- Post-implementation acceptance: not performed
