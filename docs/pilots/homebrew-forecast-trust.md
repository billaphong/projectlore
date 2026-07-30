# Homebrew forecast-snapshot trust pilot

Status: pre-registered before retrieval, context, MCP, or policy-check
implementation.

## Boundary

The pilot covers only the temporal trust boundary for the demand section of a
Homebrew replenishment snapshot. It answers whether calibration and demand
evidence were knowable at snapshot creation and whether demand covers the
complete safety lookahead.

This boundary is meaningful because a violation can leak future actual sales
into a plan, make a snapshot internally impossible, or plan beyond trusted
demand. It is bounded because all three decisions are deterministic comparisons
over timestamps at one existing contract seam.

The authoritative Homebrew revision observed for this pre-registration is
`b6a85e4fc0f57344b7a1c574ce179fc060a313cf`.

## Exactly three initial invariants

1. `lore:homebrew/rule/calibration-predates-forecast`
   - Rule: `calibration.backtestEnd <= demand.issuedAt`.
   - Violation outcome: structurally reject the snapshot.
   - Primary evidence:
     `lib/replenishment/forecasting-contracts.ts:125`,
     `lib/seed/v2/orchestration/prismaForecastDeliveryProvider.ts:163`, and
     `tests/unit/seed/v2/orchestration/prismaForecastDeliveryProvider.test.ts:55`.
   - Non-goal: choosing the length of a pre-window calibration warm-up.
2. `lore:homebrew/rule/forecast-issued-by-snapshot`
   - Rule: `demand.issuedAt <= snapshot.createdAt`.
   - Violation outcome: structurally reject the snapshot.
   - Primary evidence:
     `lib/replenishment/forecasting-contracts.ts:261` and
     `tests/unit/replenishment/forecasting-contracts.test.ts:44`.
   - Non-goal: generating or revising the forecast.
3. `lore:homebrew/rule/demand-covers-safety-lookahead`
   - Rule: `demand.validThrough >= snapshot.safetyLookaheadEnd`.
   - Violation outcome: classify readiness as `input_untrusted`; do not
     publish a plan.
   - Primary evidence:
     `lib/replenishment/forecasting-contracts.ts:288` and
     `tests/unit/replenishment/forecasting-contracts.test.ts:41`.
   - Non-goal: optimizer feasibility, replenishment quantities, or publication
     mechanics after a snapshot is trusted.

The canonical model is
`examples/homebrew.forecast-trust.project.yaml`. The frozen question and policy
corpus is `evaluations/homebrew-forecast-trust/corpus.yaml`.

## Comparative proof

The baseline is the current foundation-only ProjectLore CLI, which has no
retrieval, context, policy, or MCP query surface. Its measurements are recorded
in `evaluations/homebrew-forecast-trust/baseline.json`; unsupported operations
score zero rather than being treated as successful empty results.

The after-corpus must use the frozen corpus without changing expected rule IDs,
source IDs, facts, or outcomes. A new corpus version is required for any change.

Pre-registered success thresholds:

| Measure | Required result |
| --- | --- |
| Rule retrieval | 6/6 questions return every expected rule ID |
| Provenance correctness | 6/6 answers return every expected source ID and no nonexistent source |
| Policy catch rate | 3/3 violations produce the expected outcome |
| Policy false positives | 0/3 compliant cases produce a finding |
| Correction rediscovery | 3/3 rule corrections are visible on the next independent query without rebuilding client prompts |
| Warm-query latency | p95 at or below 100 ms on the local reference machine |
| Task context size | p95 at or below 16 KiB serialized JSON for this corpus |

These thresholds are pre-registered defaults under the Frame's “otherwise
pre-registered” path. They are not claims about results. Any threshold change
requires a documented reason before the after-corpus is run.

## Explicitly unauthorized and out of scope

- No Homebrew source, test, workflow, branch-protection, hosted data, database,
  or production change.
- No optimizer, forecast-generation, warm-up-period, delivery, or receipt rule.
- No automatic mutation of a project knowledge model during reads.
- No claim that ProjectLore replaces Homebrew's code graph or runtime tests.
- No after-corpus run until the walking-skeleton implementation is complete.
