# Sienna deterministic campaign-authority pilot

Status: passed. The thresholds below were pre-registered before the retained
after-corpus run.

## Selection and boundary

The owner previously directed ProjectLore work to continue into Sienna. Sienna
was selected over Sophie because its engine-independent deterministic C# core,
typed command boundary, replay proofs, and save-oriented authority model are a
material contrast with Homebrew's timestamp trust boundary and Python/TypeScript
workflow.

The pilot is limited to two already-committed Sienna invariants at revision
`5722b2b22b769d237113044ef1e5c652e89ddb94`:

1. Authoritative campaign mutation is decided and committed through
   `GameSession.Execute`.
2. The same initial campaign state, seed, and accepted commands produce the same
   final snapshot and ordered-event digests.

It does not change Sienna. In particular, it does not touch or claim completion
for the dirty active R5.2 regional-campaign worktree or its Fraimed Frame.

## Pre-registered corpus and thresholds

The frozen corpus is
`evaluations/sienna-campaign-authority/corpus.yaml`; the canonical model is
`examples/sienna.campaign-authority.project.yaml`.

| Measure | Required result |
| --- | --- |
| Context quality / rule retrieval | 3/3 questions |
| Provenance correctness | 3/3 questions |
| Policy catch rate | 2/2 violations |
| Policy false positives | 0/2 compliant cases |
| Correction rediscovery | 2/2 rule corrections |
| Warm operation latency | p95 at or below 100 ms |
| Task context size | p95 at or below 16 KiB |
| Maintenance footprint | canonical model at or below 220 lines |

## Retained result

`evaluations/sienna-campaign-authority/result.json` passed all thresholds against
fresh Fraimed scope:

- retrieval and provenance: 3/3 each;
- policy catch rate: 2/2, with 0/2 compliant cases falsely flagged;
- correction rediscovery: 2/2;
- warm operation latency: 0.159 ms p95;
- context size: 5,957 bytes p95;
- maintenance footprint: 158 model lines.

These are local reference measurements, not universal performance guarantees.
The live evaluation receipt names the ProjectLore portability Frame; it does not
claim the separate Sienna R5.2 Frame is complete.

The pilot uses the same `ProjectKnowledgeModel`, `ModelService`, query envelope,
read-only MCP tools, `PolicyRequest`, four policy outcomes, Fraimed scope
receipt, and client-neutral contract digest as Homebrew. Only the
operator-authored deterministic policy bindings differ. They remain executable
runtime policy outside canonical model content.

## Explicit limits

- No Sienna source, content, tests, branches, saves, assets, or Fraimed scope are
  mutated by this pilot.
- Source observations are pinned to committed revision `5722b2b...`; uncommitted
  R5.2 files are not treated as accepted evidence.
- ProjectLore does not claim that a model answer proves runtime determinism. The
  cited Sienna executable tests remain authoritative for that behavior.
- No model schema extension is introduced. Rule implementation anchors use the
  already-versioned `0.1.0` contract added for both pilots.
