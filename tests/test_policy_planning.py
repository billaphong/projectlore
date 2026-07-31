from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from projectlore.policy import (
    CALIBRATION_RULE,
    DEFAULT_POLICY_REGISTRY,
    HORIZON_RULE,
    ISSUE_RULE,
    FailedWorkflowResolution,
    MissingWorkflowResolution,
    PolicyEvaluationPlan,
    PolicyRegistry,
    ValidWorkflowResolution,
    evaluate_policy,
    plan_policy,
    resolve_policy_context,
)
from projectlore.service import ModelService
from projectlore.workflow import (
    LocalScopeProvider,
    ObservedWorkflowContext,
    WorkflowTarget,
    issue_workflow_receipt,
    make_local_declaration,
    make_observation,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"
FailureCode = Literal[
    "workflow_unavailable",
    "workflow_timeout",
    "workflow_authentication_required",
    "workflow_response_invalid",
    "workflow_target_mismatch",
    "workflow_context_expired",
]


def _service() -> ModelService:
    return ModelService(MODEL)


def _target(service: ModelService) -> WorkflowTarget:
    return WorkflowTarget(
        target_version="projectlore-workflow-target/1.0.0",
        project_id=service.model.id,
        model_entrypoint="examples/homebrew.forecast-trust.project.yaml",
        provider_id="local",
        scope_id="policy-work",
        container_id=None,
    )


def _registry() -> PolicyRegistry:
    by_id = {
        binding.rule_id: binding
        for binding in DEFAULT_POLICY_REGISTRY.bindings
    }
    return PolicyRegistry(
        (
            by_id[CALIBRATION_RULE],
            replace(by_id[ISSUE_RULE], scope_requirement="workflow"),
            replace(
                by_id[HORIZON_RULE],
                scope_requirement="observed_workflow",
            ),
        )
    )


def _facts() -> dict[str, str]:
    return {
        "calibration_backtest_end": "2026-08-02T00:00:00Z",
        "demand_issued_at": "2026-08-01T00:00:00Z",
        "snapshot_created_at": "2026-08-01T01:00:00Z",
        "safety_lookahead_end": "2026-08-03T00:00:00Z",
        "demand_valid_through": "2026-08-04T00:00:00Z",
    }


def _missing(plan: PolicyEvaluationPlan) -> MissingWorkflowResolution:
    return MissingWorkflowResolution(
        state="missing_context",
        model_digest=plan.model_digest,
        target_config_digest=plan.target_config_digest,
    )


def _valid_local(
    plan: PolicyEvaluationPlan,
    service: ModelService,
    target: WorkflowTarget,
) -> ValidWorkflowResolution:
    declared = make_local_declaration(
        target,
        title="Policy work",
        status="active",
        declared_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    observation = asyncio.run(LocalScopeProvider(declared).observe(target))
    receipt = issue_workflow_receipt(
        observation,
        target,
        model_digest=service.project.digest,
        now=observation.observed_at,
    )
    return ValidWorkflowResolution(
        state="valid_context",
        model_digest=plan.model_digest,
        target_config_digest=plan.target_config_digest,
        context=declared,
        observation=observation,
        receipt=receipt,
    )


def test_plan_is_deterministic_and_immune_to_fact_mutation() -> None:
    service = _service()
    target = _target(service)
    facts = _facts()
    first = plan_policy(facts, _registry(), service.project, target)
    second = plan_policy(
        dict(reversed(tuple(facts.items()))),
        _registry(),
        service.project,
        target,
    )
    facts["calibration_backtest_end"] = "1900-01-01T00:00:00Z"

    assert first.model_dump_json() == second.model_dump_json()
    assert dict(first.facts)["calibration_backtest_end"].startswith("2026")


def test_plan_rejects_non_string_fact_boundaries() -> None:
    service = _service()
    with pytest.raises(ValueError, match="string keys and values"):
        plan_policy(
            cast(dict[str, str], {"snapshot_created_at": cast(Any, 1)}),
            _registry(),
            service.project,
            _target(service),
        )


def test_mixed_missing_context_keeps_timeless_failure_and_binding_order() -> None:
    service = _service()
    plan = plan_policy(_facts(), _registry(), service.project, _target(service))

    result = evaluate_policy(plan, _missing(plan))

    assert result.decision == "fail"
    assert [item.rule_id for item in result.findings] == [
        CALIBRATION_RULE,
        ISSUE_RULE,
        HORIZON_RULE,
    ]
    assert [item.decision for item in result.findings] == [
        "fail",
        "indeterminate",
        "indeterminate",
    ]
    assert all(item.workflow_receipt is None for item in result.findings)


def test_declared_context_satisfies_workflow_but_not_observed_workflow() -> None:
    service = _service()
    target = _target(service)
    plan = plan_policy(_facts(), _registry(), service.project, target)

    result = evaluate_policy(plan, _valid_local(plan, service, target))

    by_rule = {item.rule_id: item for item in result.findings}
    assert by_rule[ISSUE_RULE].decision == "pass"
    assert by_rule[ISSUE_RULE].workflow_receipt is not None
    assert by_rule[HORIZON_RULE].decision == "indeterminate"
    assert by_rule[HORIZON_RULE].outcome == "observed_context_required"
    assert by_rule[CALIBRATION_RULE].workflow_receipt is None


def test_observed_context_satisfies_both_context_requirements() -> None:
    service = _service()
    target = _target(service).model_copy(
        update={"provider_id": "fake", "container_id": "workspace"}
    )
    plan = plan_policy(_facts(), _registry(), service.project, target)
    observed_at = datetime(2026, 8, 1, tzinfo=UTC)
    observation = make_observation(
        target,
        assurance="observed",
        title="External work",
        status="active",
        validation_open=0,
        observed_at=observed_at,
        authority_ref="fake://scope/policy-work",
    )
    receipt = issue_workflow_receipt(
        observation,
        target,
        model_digest=service.project.digest,
        now=observed_at,
    )
    resolution = ValidWorkflowResolution(
        state="valid_context",
        model_digest=plan.model_digest,
        target_config_digest=plan.target_config_digest,
        context=ObservedWorkflowContext(
            context_version="projectlore-workflow-context/1.0.0",
            context_kind="observed",
            observation=observation,
            maximum_age_seconds=300,
        ),
        observation=observation,
        receipt=receipt,
    )

    result = evaluate_policy(plan, resolution)

    by_rule = {item.rule_id: item for item in result.findings}
    assert by_rule[ISSUE_RULE].decision == "pass"
    assert by_rule[HORIZON_RULE].decision == "pass"


@pytest.mark.parametrize(
    "code",
    (
        "workflow_unavailable",
        "workflow_timeout",
        "workflow_authentication_required",
        "workflow_response_invalid",
        "workflow_target_mismatch",
        "workflow_context_expired",
    ),
)
def test_provider_failures_localize_to_workflow_bindings(code: FailureCode) -> None:
    service = _service()
    plan = plan_policy(_facts(), _registry(), service.project, _target(service))
    resolution = FailedWorkflowResolution(
        state="provider_failure",
        model_digest=plan.model_digest,
        target_config_digest=plan.target_config_digest,
        failure_code=code,
    )

    result = evaluate_policy(plan, resolution)

    assert result.decision == "fail"
    assert result.findings[0].decision == "fail"
    assert [item.outcome for item in result.findings[1:]] == [code, code]


def test_evaluation_rejects_model_and_target_drift() -> None:
    service = _service()
    plan = plan_policy(_facts(), _registry(), service.project, _target(service))
    missing = _missing(plan)
    with pytest.raises(ValueError, match="model changed"):
        evaluate_policy(
            plan,
            missing.model_copy(update={"model_digest": "sha256:" + "f" * 64}),
        )
    with pytest.raises(ValueError, match="target changed"):
        evaluate_policy(
            plan,
            missing.model_copy(update={"target_config_digest": "sha256:" + "e" * 64}),
        )


def test_resolution_call_count_is_zero_or_exactly_one() -> None:
    service = _service()
    timeless = PolicyRegistry((_registry().bindings[0],))
    timeless_plan = plan_policy(_facts(), timeless, service.project, None)
    scoped_plan = plan_policy(_facts(), _registry(), service.project, _target(service))
    calls = 0

    async def resolve() -> MissingWorkflowResolution:
        nonlocal calls
        calls += 1
        return _missing(scoped_plan)

    asyncio.run(resolve_policy_context(timeless_plan, resolve))
    assert calls == 0
    asyncio.run(resolve_policy_context(scoped_plan, resolve))
    assert calls == 1


def test_expired_declaration_only_blocks_context_bindings() -> None:
    service = _service()
    target = _target(service)
    plan = plan_policy(_facts(), _registry(), service.project, target)
    declared_at = datetime(2026, 8, 1, tzinfo=UTC)
    declared = make_local_declaration(
        target,
        title="Policy work",
        status="active",
        declared_at=declared_at,
        expires_at=declared_at + timedelta(seconds=30),
    )
    observation = asyncio.run(LocalScopeProvider(declared).observe(target))
    receipt = issue_workflow_receipt(
        observation,
        target,
        model_digest=plan.model_digest,
        now=declared_at + timedelta(seconds=31),
    )
    resolution = ValidWorkflowResolution(
        state="valid_context",
        model_digest=plan.model_digest,
        target_config_digest=plan.target_config_digest,
        context=declared,
        observation=observation,
        receipt=receipt,
    )

    result = evaluate_policy(plan, resolution)

    assert result.findings[0].decision == "fail"
    assert [item.outcome for item in result.findings[1:]] == [
        "workflow_context_expired",
        "workflow_context_expired",
    ]


def test_observed_context_rejects_receipt_tampering_and_max_age_drift() -> None:
    service = _service()
    target = _target(service).model_copy(update={"provider_id": "fake"})
    plan = plan_policy(_facts(), _registry(), service.project, target)
    observed_at = datetime(2026, 8, 1, tzinfo=UTC)
    observation = make_observation(
        target,
        assurance="observed",
        title="External work",
        status="active",
        validation_open=0,
        observed_at=observed_at,
        authority_ref="fake://scope/policy-work",
    )
    receipt = issue_workflow_receipt(
        observation,
        target,
        model_digest=plan.model_digest,
        now=observed_at,
    )
    context = ObservedWorkflowContext(
        context_version="projectlore-workflow-context/1.0.0",
        context_kind="observed",
        observation=observation,
        maximum_age_seconds=receipt.maximum_age_seconds,
    )
    resolution = ValidWorkflowResolution(
        state="valid_context",
        model_digest=plan.model_digest,
        target_config_digest=plan.target_config_digest,
        context=context,
        observation=observation,
        receipt=receipt,
    )
    with pytest.raises(ValueError, match="identity drifted"):
        evaluate_policy(
            plan,
            resolution.model_copy(
                update={"receipt": receipt.model_copy(update={"scope_id": "other"})}
            ),
        )
    with pytest.raises(ValueError, match="context and receipt disagree"):
        evaluate_policy(
            plan,
            resolution.model_copy(
                update={
                    "context": context.model_copy(
                        update={"maximum_age_seconds": 1}
                    )
                }
            ),
        )
    with pytest.raises(ValueError, match="receipt timing drifted"):
        evaluate_policy(
            plan,
            resolution.model_copy(
                update={
                    "receipt": receipt.model_copy(update={"age_seconds": 1.0})
                }
            ),
        )


def test_declared_context_rejects_semantically_different_observation() -> None:
    service = _service()
    target = _target(service)
    plan = plan_policy(_facts(), _registry(), service.project, target)
    resolution = _valid_local(plan, service, target)
    mismatched = make_observation(
        target,
        assurance="declared",
        title="Different title",
        status=resolution.observation.status,
        validation_open=resolution.observation.validation_open,
        observed_at=resolution.observation.observed_at,
        authority_ref=resolution.observation.authority_ref,
    )
    receipt = issue_workflow_receipt(
        mismatched,
        target,
        model_digest=plan.model_digest,
        now=mismatched.observed_at,
    )
    with pytest.raises(ValueError, match="declaration and observation disagree"):
        evaluate_policy(
            plan,
            resolution.model_copy(
                update={"observation": mismatched, "receipt": receipt}
            ),
        )
