"""Operator-authored deterministic policy bindings shared by every client."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from pydantic.dataclasses import dataclass

from projectlore.compiler import ProjectModel
from projectlore.query import QueryService
from projectlore.scope import ScopeReceipt, ScopeSnapshot, issue_scope_receipt
from projectlore.service import ModelService
from projectlore.workflow import (
    DeclaredWorkflowContext,
    ObservedWorkflowContext,
    WorkflowContext,
    WorkflowObservation,
    WorkflowReceipt,
    WorkflowTarget,
    issue_workflow_receipt,
    make_local_declaration,
)
from projectlore.workflow_compat import legacy_snapshot_to_observation

PolicyDecision = Literal["pass", "fail", "not_applicable", "indeterminate"]
POLICY_REGISTRY_PATH = Path(".projectlore/policy-bindings.json")
MAX_POLICY_REGISTRY_BYTES = 64 * 1024

CALIBRATION_RULE = "lore:homebrew/rule/calibration-predates-forecast"
ISSUE_RULE = "lore:homebrew/rule/forecast-issued-by-snapshot"
HORIZON_RULE = "lore:homebrew/rule/demand-covers-safety-lookahead"
SIENNA_COMMAND_RULE = "lore:sienna/rule/authoritative-command-boundary"
SIENNA_REPLAY_RULE = "lore:sienna/rule/deterministic-replay"


@dataclass(config=ConfigDict(extra="forbid", strict=True), frozen=True)
class PolicyBinding:
    """Trusted runtime semantics; canonical model text cannot make code executable."""

    rule_id: str
    left_fact: str
    relation: Literal["lte", "equal"]
    right_fact: str | None
    right_literal: str | None
    value_type: Literal["datetime", "decimal", "string"]
    failure_outcome: str
    failure_message: str
    scope_requirement: Literal["none", "workflow", "observed_workflow"] = "none"

    def __post_init__(self) -> None:
        if (self.right_fact is None) == (self.right_literal is None):
            raise ValueError(
                "A policy binding requires exactly one right-hand operand."
            )


class PolicyRegistry:
    """Immutable operator-owned registry of deterministic rule bindings."""

    def __init__(self, bindings: tuple[PolicyBinding, ...]) -> None:
        entries = {binding.rule_id: binding for binding in bindings}
        if len(entries) != len(bindings):
            raise ValueError("Policy binding rule IDs must be unique.")
        self._bindings = tuple(bindings)

    @property
    def bindings(self) -> tuple[PolicyBinding, ...]:
        return self._bindings


DEFAULT_POLICY_REGISTRY = PolicyRegistry(
    (
        PolicyBinding(
            CALIBRATION_RULE,
            "calibration_backtest_end",
            "lte",
            "demand_issued_at",
            None,
            "datetime",
            "reject_snapshot",
            "Calibration evidence postdates forecast issue.",
        ),
        PolicyBinding(
            ISSUE_RULE,
            "demand_issued_at",
            "lte",
            "snapshot_created_at",
            None,
            "datetime",
            "reject_snapshot",
            "Demand was issued after snapshot creation.",
        ),
        PolicyBinding(
            HORIZON_RULE,
            "safety_lookahead_end",
            "lte",
            "demand_valid_through",
            None,
            "datetime",
            "input_untrusted",
            "Demand does not cover the complete safety lookahead.",
        ),
        PolicyBinding(
            SIENNA_COMMAND_RULE,
            "mutation_path",
            "equal",
            None,
            "game_session_execute",
            "string",
            "reject_unauthorized_mutation",
            "Authoritative campaign mutation bypasses GameSession.Execute.",
        ),
        PolicyBinding(
            SIENNA_REPLAY_RULE,
            "actual_replay_digest",
            "equal",
            "expected_replay_digest",
            None,
            "string",
            "nondeterministic_replay",
            "Identical campaign inputs produced a different replay digest.",
        ),
    )
)

_BINDING_ADAPTER = TypeAdapter(tuple[PolicyBinding, ...])


def load_policy_registry(root: Path) -> PolicyRegistry:
    """Load bounded operator-owned declarative bindings, if configured."""
    path = (root.resolve() / POLICY_REGISTRY_PATH).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Policy registry path escapes the project root.")
    if not path.is_file():
        return DEFAULT_POLICY_REGISTRY
    raw = path.read_bytes()
    if len(raw) > MAX_POLICY_REGISTRY_BYTES:
        raise ValueError("Policy registry exceeds 64 KiB.")
    try:
        bindings = _BINDING_ADAPTER.validate_json(raw, strict=True)
    except ValidationError as error:
        raise ValueError(f"Policy registry is invalid: {error}") from error
    return PolicyRegistry((*DEFAULT_POLICY_REGISTRY.bindings, *bindings))


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    facts: dict[str, str]
    scope: ScopeSnapshot | None = None


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    rule_id: str
    decision: PolicyDecision
    outcome: str
    message: str
    source_refs: list[str]


class PolicyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision: PolicyDecision
    findings: list[Finding]
    scope_receipt: ScopeReceipt | None


class PlannedBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    left_fact: str
    relation: Literal["lte", "equal"]
    right_fact: str | None
    right_literal: str | None
    value_type: Literal["datetime", "decimal", "string"]
    failure_outcome: str
    failure_message: str
    scope_requirement: Literal["none", "workflow", "observed_workflow"]
    rule_present: bool
    source_refs: tuple[str, ...]


class PolicyEvaluationPlan(BaseModel):
    """Immutable snapshot consumed by the pure second-stage evaluator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_version: Literal["projectlore-policy-plan/1.0.0"]
    facts: tuple[tuple[str, str], ...]
    bindings: tuple[PlannedBinding, ...]
    context_requirements: tuple[Literal["workflow", "observed_workflow"], ...]
    model_digest: str
    registry_digest: str
    target_config_digest: str | None
    plan_digest: str

    @model_validator(mode="after")
    def digest_is_valid(self) -> PolicyEvaluationPlan:
        content = self.model_dump(mode="json", exclude={"plan_digest"})
        if self.plan_digest != _policy_digest(content):
            raise ValueError("plan_digest does not match the immutable plan.")
        return self


class ValidWorkflowResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["valid_context"]
    model_digest: str
    target_config_digest: str | None
    context: WorkflowContext
    observation: WorkflowObservation
    receipt: WorkflowReceipt


class MissingWorkflowResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["missing_context"]
    model_digest: str
    target_config_digest: str | None


class FailedWorkflowResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["provider_failure"]
    model_digest: str
    target_config_digest: str | None
    failure_code: Literal[
        "workflow_unavailable",
        "workflow_timeout",
        "workflow_authentication_required",
        "workflow_response_invalid",
        "workflow_target_mismatch",
        "workflow_context_expired",
    ]


WorkflowResolution = (
    ValidWorkflowResolution
    | MissingWorkflowResolution
    | FailedWorkflowResolution
)


class PlannedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    decision: PolicyDecision
    outcome: str
    message: str
    source_refs: tuple[str, ...]
    workflow_receipt: WorkflowReceipt | None


class PlannedPolicyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: PolicyDecision
    findings: tuple[PlannedFinding, ...]
    plan_digest: str


def plan_policy(
    facts: dict[str, str],
    registry: PolicyRegistry,
    project: ProjectModel,
    target_identity: WorkflowTarget | None,
) -> PolicyEvaluationPlan:
    """Freeze applicable semantics before resolving optional context."""
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in facts.items()
    ):
        raise ValueError("Policy facts must be string keys and values.")
    normalized = tuple(sorted(facts.items()))
    fact_names = {key for key, _ in normalized}
    rules = {rule.id: rule for rule in project.model.rules}
    planned: list[PlannedBinding] = []
    for binding in registry.bindings:
        if binding.left_fact not in fact_names or (
            binding.right_fact is not None and binding.right_fact not in fact_names
        ):
            continue
        rule = rules.get(binding.rule_id)
        planned.append(
            PlannedBinding(
                rule_id=binding.rule_id,
                left_fact=binding.left_fact,
                relation=binding.relation,
                right_fact=binding.right_fact,
                right_literal=binding.right_literal,
                value_type=binding.value_type,
                failure_outcome=binding.failure_outcome,
                failure_message=binding.failure_message,
                scope_requirement=binding.scope_requirement,
                rule_present=rule is not None,
                source_refs=tuple(() if rule is None else rule.source_refs),
            )
        )
    requirements = tuple(
        dict.fromkeys(
            binding.scope_requirement
            for binding in planned
            if binding.scope_requirement != "none"
        )
    )
    registry_payload = _BINDING_ADAPTER.dump_python(
        registry.bindings, mode="json"
    )
    content: dict[str, Any] = {
        "plan_version": "projectlore-policy-plan/1.0.0",
        "facts": normalized,
        "bindings": [item.model_dump(mode="json") for item in planned],
        "context_requirements": requirements,
        "model_digest": project.digest,
        "registry_digest": _policy_digest(registry_payload),
        "target_config_digest": (
            target_identity.digest if target_identity is not None else None
        ),
    }
    return PolicyEvaluationPlan(
        **content,
        plan_digest=_policy_digest(content),
    )


def evaluate_policy(
    plan: PolicyEvaluationPlan,
    resolution: WorkflowResolution,
) -> PlannedPolicyResult:
    """Evaluate only the immutable plan and one identity-bound resolution."""
    if resolution.model_digest != plan.model_digest:
        raise ValueError("Policy model changed after planning; replan.")
    if resolution.target_config_digest != plan.target_config_digest:
        raise ValueError("Workflow target changed after planning; replan.")
    context_expired = False
    if isinstance(resolution, ValidWorkflowResolution):
        if plan.target_config_digest is None:
            raise ValueError("Valid workflow context requires a planned target.")
        context_target_digest = (
            resolution.context.target_digest
            if isinstance(resolution.context, DeclaredWorkflowContext)
            else resolution.context.observation.target_digest
        )
        context_assurance = (
            "declared"
            if isinstance(resolution.context, DeclaredWorkflowContext)
            else "observed"
        )
        if (
            resolution.receipt.model_digest != plan.model_digest
            or resolution.receipt.target_digest != plan.target_config_digest
            or context_target_digest != plan.target_config_digest
            or resolution.receipt.observation_digest
            != resolution.observation.content_digest
            or resolution.receipt.assurance != context_assurance
            or resolution.observation.assurance != context_assurance
            or resolution.receipt.project_id != resolution.observation.project_id
            or resolution.receipt.model_entrypoint
            != resolution.observation.model_entrypoint
            or resolution.receipt.provider_id != resolution.observation.provider_id
            or resolution.receipt.scope_id != resolution.observation.scope_id
            or resolution.receipt.container_id != resolution.observation.container_id
            or resolution.receipt.authority_ref
            != resolution.observation.authority_ref
            or resolution.receipt.observed_at
            != resolution.observation.observed_at
        ):
            raise ValueError("Workflow receipt or context identity drifted; replan.")
        receipt_age = (
            resolution.receipt.evaluated_at.astimezone(UTC)
            - resolution.receipt.observed_at.astimezone(UTC)
        ).total_seconds()
        if (
            receipt_age < 0
            or abs(resolution.receipt.age_seconds - receipt_age) > 1e-6
            or resolution.receipt.fresh
            != (receipt_age <= resolution.receipt.maximum_age_seconds)
        ):
            raise ValueError("Workflow receipt timing drifted; re-resolve.")
        if isinstance(resolution.context, ObservedWorkflowContext):
            if resolution.context.observation != resolution.observation or (
                resolution.context.maximum_age_seconds
                != resolution.receipt.maximum_age_seconds
            ):
                raise ValueError("Workflow context and receipt disagree; re-resolve.")
        else:
            if (
                resolution.context.project_id != resolution.observation.project_id
                or resolution.context.model_entrypoint
                != resolution.observation.model_entrypoint
                or resolution.context.provider_id
                != resolution.observation.provider_id
                or resolution.context.scope_id != resolution.observation.scope_id
                or resolution.context.container_id
                != resolution.observation.container_id
                or resolution.context.authority_ref
                != resolution.observation.authority_ref
                or resolution.context.title != resolution.observation.title
                or resolution.context.status != resolution.observation.status
                or resolution.context.validation_open
                != resolution.observation.validation_open
                or resolution.context.declared_at
                != resolution.observation.observed_at
            ):
                raise ValueError("Workflow declaration and observation disagree.")
        context_expired = (
            not resolution.context.valid_at(resolution.receipt.evaluated_at)
            or (
                isinstance(resolution.context, ObservedWorkflowContext)
                and not resolution.receipt.fresh
            )
        )
    facts = dict(plan.facts)
    findings: list[PlannedFinding] = []
    for binding in plan.bindings:
        if binding.scope_requirement != "none":
            blocked = _context_block(
                binding.scope_requirement,
                resolution,
                context_expired=context_expired,
            )
            if blocked is not None:
                findings.append(
                    PlannedFinding(
                        rule_id=binding.rule_id,
                        decision="indeterminate",
                        outcome=blocked,
                        message="Required workflow context is not usable.",
                        source_refs=binding.source_refs,
                        workflow_receipt=None,
                    )
                )
                continue
        finding = _evaluate_planned_binding(facts, binding)
        receipt = (
            resolution.receipt
            if binding.scope_requirement != "none"
            and isinstance(resolution, ValidWorkflowResolution)
            else None
        )
        findings.append(finding.model_copy(update={"workflow_receipt": receipt}))
    decisions = {finding.decision for finding in findings}
    decision: PolicyDecision
    if "fail" in decisions:
        decision = "fail"
    elif "indeterminate" in decisions:
        decision = "indeterminate"
    elif "pass" in decisions:
        decision = "pass"
    else:
        decision = "not_applicable"
    return PlannedPolicyResult(
        decision=decision,
        findings=tuple(findings),
        plan_digest=plan.plan_digest,
    )


async def resolve_policy_context(
    plan: PolicyEvaluationPlan,
    resolver: Callable[[], Awaitable[WorkflowResolution]],
) -> WorkflowResolution:
    """Call the composition-root resolver zero or one time from plan needs."""
    if not plan.context_requirements:
        return MissingWorkflowResolution(
            state="missing_context",
            model_digest=plan.model_digest,
            target_config_digest=plan.target_config_digest,
        )
    return await resolver()


def _context_block(
    requirement: Literal["workflow", "observed_workflow"],
    resolution: WorkflowResolution,
    *,
    context_expired: bool = False,
) -> str | None:
    if isinstance(resolution, MissingWorkflowResolution):
        return "missing_context"
    if isinstance(resolution, FailedWorkflowResolution):
        return resolution.failure_code
    if context_expired:
        return "workflow_context_expired"
    assurance = (
        "declared"
        if getattr(resolution.context, "context_kind", None) == "declared"
        else "observed"
    )
    if requirement == "observed_workflow" and assurance != "observed":
        return "observed_context_required"
    return None


def _evaluate_planned_binding(
    facts: dict[str, str], binding: PlannedBinding
) -> PlannedFinding:
    if not binding.rule_present:
        return PlannedFinding(
            rule_id=binding.rule_id,
            decision="indeterminate",
            outcome="missing_rule",
            message="Required rule is missing from the model.",
            source_refs=binding.source_refs,
            workflow_receipt=None,
        )
    right = (
        facts[binding.right_fact]
        if binding.right_fact is not None
        else binding.right_literal
    )
    assert right is not None
    left = facts[binding.left_fact]
    try:
        if binding.value_type == "datetime":
            left_value: Any = datetime.fromisoformat(left.replace("Z", "+00:00"))
            right_value: Any = datetime.fromisoformat(right.replace("Z", "+00:00"))
        elif binding.value_type == "decimal":
            left_value = Decimal(left)
            right_value = Decimal(right)
            if not left_value.is_finite() or not right_value.is_finite():
                raise InvalidOperation
        else:
            left_value = left
            right_value = right
    except (InvalidOperation, ValueError):
        return PlannedFinding(
            rule_id=binding.rule_id,
            decision="indeterminate",
            outcome="invalid_fact",
            message="Policy fact has an invalid value.",
            source_refs=binding.source_refs,
            workflow_receipt=None,
        )
    satisfied = (
        left_value <= right_value
        if binding.relation == "lte"
        else left_value == right_value
    )
    return PlannedFinding(
        rule_id=binding.rule_id,
        decision="pass" if satisfied else "fail",
        outcome="no_finding" if satisfied else binding.failure_outcome,
        message="Rule satisfied." if satisfied else binding.failure_message,
        source_refs=binding.source_refs,
        workflow_receipt=None,
    )


def _policy_digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class PolicyService:
    """Pure policy evaluation over an immutable compiled model."""

    def __init__(
        self,
        project: ProjectModel,
        registry: PolicyRegistry = DEFAULT_POLICY_REGISTRY,
    ) -> None:
        self.project = project
        self._query = QueryService(project)
        self._registry = registry

    def check(
        self,
        request: PolicyRequest,
        *,
        scope_obtained_via: Literal[
            "fraimed_mcp", "local_file", "provided_snapshot"
        ] = "provided_snapshot",
    ) -> dict[str, Any]:
        target = _legacy_target(self.project, request.scope)
        plan = plan_policy(request.facts, self._registry, self.project, target)
        legacy_receipt = None
        if request.scope is None:
            resolution: WorkflowResolution = MissingWorkflowResolution(
                state="missing_context",
                model_digest=self.project.digest,
                target_config_digest=plan.target_config_digest,
            )
        else:
            assert target is not None
            observation = legacy_snapshot_to_observation(request.scope, target)
            canonical_receipt = issue_workflow_receipt(
                observation,
                target,
                model_digest=self.project.digest,
            )
            legacy_receipt = issue_scope_receipt(
                request.scope, obtained_via=scope_obtained_via
            )
            if observation.assurance == "declared":
                context: WorkflowContext = make_local_declaration(
                    target,
                    title=observation.title,
                    status=observation.status,
                    validation_open=observation.validation_open,
                    declared_at=observation.observed_at,
                )
            else:
                context = ObservedWorkflowContext(
                    context_version="projectlore-workflow-context/1.0.0",
                    context_kind="observed",
                    observation=observation,
                    maximum_age_seconds=canonical_receipt.maximum_age_seconds,
                )
            resolution = (
                ValidWorkflowResolution(
                    state="valid_context",
                    model_digest=self.project.digest,
                    target_config_digest=plan.target_config_digest,
                    context=context,
                    observation=observation,
                    receipt=canonical_receipt,
                )
                if canonical_receipt.fresh
                or isinstance(context, DeclaredWorkflowContext)
                else FailedWorkflowResolution(
                    state="provider_failure",
                    model_digest=self.project.digest,
                    target_config_digest=plan.target_config_digest,
                    failure_code="workflow_context_expired",
                )
            )
        planned_result = evaluate_policy(plan, resolution)
        applicable = [
            Finding(
                rule_id=item.rule_id,
                decision=item.decision,
                outcome={
                    "missing_context": "dependency_unavailable",
                    "workflow_context_expired": "stale_dependency",
                }.get(item.outcome, item.outcome),
                message=item.message,
                source_refs=list(item.source_refs),
            )
            for item in planned_result.findings
        ]
        result = PolicyResult(
            decision=planned_result.decision,
            findings=applicable,
            # Tool contract 0.2.0 retains its result-level receipt for any
            # supplied legacy snapshot. Canonical 1.0 findings attach receipts
            # only to bindings that consumed workflow context.
            scope_receipt=legacy_receipt,
        )
        source_refs = {
            source_ref
            for finding in applicable
            for source_ref in finding.source_refs
        }
        sources = [
            source
            for source in self.project.model.sources
            if source.id in source_refs
        ]
        return self._query.envelope(
            result.model_dump(mode="json"),
            result_state="complete",
            provenance=sources,
        )


def policy_check(
    service: ModelService,
    request: PolicyRequest,
    *,
    registry: PolicyRegistry = DEFAULT_POLICY_REGISTRY,
    scope_obtained_via: Literal[
        "fraimed_mcp", "local_file", "provided_snapshot"
    ] = "provided_snapshot",
) -> dict[str, Any]:
    return PolicyService(service.project, registry).check(
        request,
        scope_obtained_via=scope_obtained_via,
    )


def _findings(
    facts: dict[str, str],
    rules: dict[str, Any],
    registry: PolicyRegistry = DEFAULT_POLICY_REGISTRY,
) -> list[Finding | None]:
    return [
        _evaluate_binding(facts, rules, binding)
        for binding in registry.bindings
    ]


def _applicable_bindings(
    facts: dict[str, str],
    registry: PolicyRegistry,
) -> tuple[PolicyBinding, ...]:
    return tuple(
        binding
        for binding in registry.bindings
        if binding.left_fact in facts
        and (
            binding.right_fact is None
            or binding.right_fact in facts
        )
    )


def _legacy_target(
    project: ProjectModel,
    snapshot: ScopeSnapshot | None,
) -> WorkflowTarget | None:
    if snapshot is None:
        return None
    return WorkflowTarget(
        target_version="projectlore-workflow-target/1.0.0",
        project_id=project.model.id,
        model_entrypoint="projectlore.yaml",
        provider_id=snapshot.authority,
        scope_id=snapshot.frame_id,
        container_id=None,
    )


def _evaluate_binding(
    facts: dict[str, str],
    rules: dict[str, Any],
    binding: PolicyBinding,
) -> Finding | None:
    if binding.left_fact not in facts:
        return None
    right_name = binding.right_fact
    if right_name is not None and right_name not in facts:
        return None
    rule = rules.get(binding.rule_id)
    sources = [] if rule is None else list(rule.source_refs)
    if rule is None:
        return Finding(
            rule_id=binding.rule_id,
            decision="indeterminate",
            outcome="missing_rule",
            message="Required rule is missing from the model.",
            source_refs=sources,
        )
    right_value = (
        facts[right_name]
        if right_name is not None
        else binding.right_literal
    )
    assert right_value is not None
    left_value = facts[binding.left_fact]
    if binding.value_type == "datetime":
        try:
            left_time = datetime.fromisoformat(
                left_value.replace("Z", "+00:00")
            )
            right_time = datetime.fromisoformat(
                right_value.replace("Z", "+00:00")
            )
        except ValueError:
            return Finding(
                rule_id=binding.rule_id,
                decision="indeterminate",
                outcome="invalid_fact",
                message="Policy timestamps must be ISO 8601 values.",
                source_refs=sources,
            )
        satisfied = (
            left_time <= right_time
            if binding.relation == "lte"
            else left_time == right_time
        )
    elif binding.value_type == "decimal":
        try:
            left_decimal = Decimal(left_value)
            right_decimal = Decimal(right_value)
        except InvalidOperation:
            return Finding(
                rule_id=binding.rule_id,
                decision="indeterminate",
                outcome="invalid_fact",
                message="Policy decimal facts must be finite decimal values.",
                source_refs=sources,
            )
        if not left_decimal.is_finite() or not right_decimal.is_finite():
            return Finding(
                rule_id=binding.rule_id,
                decision="indeterminate",
                outcome="invalid_fact",
                message="Policy decimal facts must be finite decimal values.",
                source_refs=sources,
            )
        satisfied = (
            left_decimal <= right_decimal
            if binding.relation == "lte"
            else left_decimal == right_decimal
        )
    else:
        satisfied = (
            left_value <= right_value
            if binding.relation == "lte"
            else left_value == right_value
        )
    return Finding(
        rule_id=binding.rule_id,
        decision="pass" if satisfied else "fail",
        outcome="no_finding" if satisfied else binding.failure_outcome,
        message="Rule satisfied." if satisfied else binding.failure_message,
        source_refs=sources,
    )
