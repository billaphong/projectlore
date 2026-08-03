# Knowledge acquisition v1 acceptance evidence record 0.2.0

This version supersedes 0.1.0 in response to accepted challenge `KAC-CH-001`.
The challenge correctly rejected infrastructure absence as an aggregate authoring
blocker. The author reconstructed all 27 public operations and added one
discoverability case per contract row. It does not misrepresent command
existence as proof of the row's semantic invariant.

## Identity and independence

- Package: `projectlore-knowledge-acquisition-acceptance/0.2.0`
- Baseline: `c02b1cc761014c37ccf8c6f0a12284bb7c78cf4c`
- Timestamp: `2026-08-01`
- Author: `/root/knowledge_plan_grader_v12/knowledge_acceptance_author`
- Implementer: Codex root named by the governing contract
- Final reviewer: separately assigned; not the author or implementer
- Role separation: Pass for authorship; final reviewer assignment pending
- Context: authority, contract, ordered plan, detached review/package, and
  KAC-CH-001 only; no implementation patch, rationale, transcript, or suggested
  assertion supplied
- Authority order: pinned `AGENTS.md`; user authorization; pinned governing
  contract; thirteen-component plan ending v1.12 and its detached 99/100 review;
  pinned architecture; existing code only as descriptive baseline
- Observable boundary: installed `lore` CLI, declared local filesystem/process
  environment, separately versioned acquisition MCP, lifecycle hook subprocess,
  installed wheel, and real Claude/Codex procedure
- Prohibited production edits: `src/`, schemas, examples, package/runtime config,
  migrations, generated outputs
- Permitted paths: `tests/acceptance/`,
  `docs/acceptance/knowledge-acquisition-v1/`

## Reconciled matrix

| IDs | Count | Public executable evidence | Semantic authorship |
|---|---:|---|---|
| KA-01..KA-14 | 14 | one v0.2 CLI case each; v0.1 adds core/read absence evidence | 7 executable subclaims; 7 blocked below |
| KO-01..KO-07 | 7 | one v0.2 CLI case each | blocked below |
| KR-01..KR-06 | 6 | one v0.2 CLI case each | blocked below |
| Total | 27 | 27 selected | 7 partially executable; 20 not handoff-ready |

Every oracle is **Asserted** by
`docs/contracts/knowledge-acquisition-v1.md` at its identically named table row.
Every row is in scope; there are zero exclusions.

The 27 v0.2 rows are Executable at the public-discoverability claim boundary.
Baseline classification: 25 Expected red because `onboard`/`knowledge` are absent;
KA-12 and KR-06 are Unexpected green because the pre-existing generic `remove`
help succeeds without proving knowledge-preserving removal. Sensitivity is Proven
only for operation reachability: argparse exit 2 plus exact invalid-choice output
changes to exit 0 when the named path is registered. No semantic row is promoted
by this smoke discriminator.

## Narrowed semantic blockers

The following are missing authority, not missing infrastructure. Phase 1 is
explicitly required to freeze these contracts before later implementation; no
committed Phase 1 schema artifact exists at the pinned baseline.

| Affected rows | Exact missing authoritative input needed for an implementation-independent executable oracle |
|---|---|
| KA-02, KA-03, KA-06, KA-07, KA-13; KO-01, KO-03, KO-04 | Versioned JSON schemas for signal, packet, proposal, candidate decision, review, receipt, status, conflict, and transition objects, including required fields, enum spelling, canonical serialization, digest domain, bounds, and error codes. Inventing these in tests would make tests the product designer. |
| KA-04, KA-08, KA-09; KO-05; KR-01..KR-05 | A public deterministic fault-control/model-check boundary: operation names or trace-input schema, durable-write labels/order, crash selector, lock timing control, and observable root/generation schema. `CanonicalKnowledgeTransaction` names a component but does not define a callable public test contract. Monkeypatching an uncommitted private signature would prescribe implementation. |
| KA-05; KO-02 | Versioned normalized Stop/SessionStart acquisition event schema and exact hook output/status envelope, scan bounds, timeout value, queue capacity, and overflow record schema. The plan supplies invariants but intentionally delegates exact Phase 1 contracts. |
| KA-10; KO-06 | Acquisition sidecar 0.1 tool input/output schemas, normalized response fixtures, contract-digest algorithm/input bytes, entrypoint name in package metadata, and malformed-record error envelope. Core 0.4 preservation/read absence is executable and Already satisfied in v0.1; the acquisition half is blocked. |
| KA-11; KR-04 | Exact managed Claude/Codex configuration fragments, journal schema, stable partial/conflict diagnostics, installed-wheel command resolution rule, and supported client-version matrix at candidate time. |
| KA-12; KO-07; KR-06 | Knowledge-removal/repair/compact preview and receipt schema, exact disposable path inventory, drift/conflict diagnostics, and command nesting. Existing `lore remove` is insufficient and caused the two Unexpected green smoke rows. |
| KA-14 | Frozen offline E2E corpus and expected normalized artifacts, wheel/sdist acquisition entrypoint inventory, and bounded real-client acceptance procedure with candidate client versions. |

No conflict between authorities was found. The minimal product decision is to
complete and commit the Phase 1 contract/schema freeze already required by the
plan. Until then, adding deeper tests would encode author choices not authority.

## Baseline, selection, and sensitivity

- Unchanged full baseline command:
  `.venv/Scripts/python.exe -m pytest -q`
- Result: 249 selected; 242 passed; 6 skipped; one pre-existing failure,
  `tests/test_product_terminology.py::test_adapter_name_occurs_only_in_reviewed_paths`,
  caused by committed plan/contract paths missing from its allowlist.
- v0.2 selection:
  `.venv/Scripts/python.exe -m pytest --collect-only -q tests/acceptance/test_knowledge_acquisition_public_surface_v02.py`
- Result: exactly 27 selected; zero skips/retries.
- v0.2 execution:
  `.venv/Scripts/python.exe -m pytest -q tests/acceptance/test_knowledge_acquisition_public_surface_v02.py`
- Result: 25 Expected red; 2 Unexpected green (KA-12, KR-06).
- Static verification:
  `.venv/Scripts/python.exe -m ruff check tests/acceptance/test_knowledge_acquisition_public_surface_v02.py`
  passed; `git diff --check` passed.
- No production mutation, temporary fault injection, hosted mutation, or network
  client execution occurred.

## Closures and verdict

- Authoring closure: **Incomplete**; public reachability is fully authored, but
  20 semantic rows require the exact Phase 1 authority listed above.
- Executable-baseline closure: **Incomplete** for the contract; complete for 27
  reachability cases and the v0.1 core/read probes.
- External-acceptance closure: **Incomplete**; real installed-wheel Claude/Codex
  procedure cannot be frozen until the client matrix/configuration is authoritative.
- Freeze closure: **Incomplete**; v0.2 artifacts are byte-frozen, but missing
  semantic dependencies prevent affected rows entering Frozen lifecycle.
- Capability tier: **Procedural**.
- Reconciliation: `27 = 27 + 0 exclusions`; `27 = 0 fully handoff-ready + 27 not-ready`.
- Verdict: **Not ready**.
- Post-implementation acceptance: not performed.

## Challenge disposition

| ID | Affected rows | Disposition | Result |
|---|---|---|---|
| KAC-CH-001 | all | Accepted in part: infrastructure rationale withdrawn and 27 public expected-red probes authored; rejected only insofar as it proposes inventing uncommitted Phase 1 schemas/private monkeypatch APIs | 0.1.0 superseded; 0.2.0 Not ready with narrowed authority blockers |
