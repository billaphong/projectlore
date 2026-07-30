"""Operator-authored deterministic policy bindings shared by every client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from projectlore.compiler import ProjectModel
from projectlore.query import QueryService
from projectlore.scope import ScopeReceipt, ScopeSnapshot, issue_scope_receipt
from projectlore.service import ModelService

PolicyDecision = Literal["pass", "fail", "not_applicable", "indeterminate"]

CALIBRATION_RULE = "lore:homebrew/rule/calibration-predates-forecast"
ISSUE_RULE = "lore:homebrew/rule/forecast-issued-by-snapshot"
HORIZON_RULE = "lore:homebrew/rule/demand-covers-safety-lookahead"
SIENNA_COMMAND_RULE = "lore:sienna/rule/authoritative-command-boundary"
SIENNA_REPLAY_RULE = "lore:sienna/rule/deterministic-replay"


@dataclass(frozen=True)
class PolicyBinding:
    """Trusted runtime semantics; canonical model text cannot make code executable."""

    rule_id: str
    left_fact: str
    relation: Literal["lte", "equal"]
    right_fact: str | None
    right_literal: str | None
    value_type: Literal["datetime", "string"]
    failure_outcome: str
    failure_message: str

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


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    facts: dict[str, str]
    scope: ScopeSnapshot


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
    scope_receipt: ScopeReceipt


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
            "fraimed_mcp", "provided_snapshot"
        ] = "provided_snapshot",
    ) -> dict[str, Any]:
        receipt = issue_scope_receipt(
            request.scope,
            obtained_via=scope_obtained_via,
        )
        if not receipt.fresh:
            finding = Finding(
                rule_id="projectlore:workflow/current-scope",
                decision="indeterminate",
                outcome="stale_dependency",
                message="Workflow scope is stale; policy cannot be decided.",
                source_refs=[],
            )
            return self._query.envelope(
                PolicyResult(
                    decision="indeterminate",
                    findings=[finding],
                    scope_receipt=receipt,
                ).model_dump(mode="json"),
                result_state="complete",
            )
        rules = {rule.id: rule for rule in self.project.model.rules}
        findings = _findings(request.facts, rules, self._registry)
        applicable = [finding for finding in findings if finding is not None]
        if not applicable:
            decision: PolicyDecision = "not_applicable"
        elif any(finding.decision == "fail" for finding in applicable):
            decision = "fail"
        elif any(finding.decision == "indeterminate" for finding in applicable):
            decision = "indeterminate"
        else:
            decision = "pass"
        result = PolicyResult(
            decision=decision,
            findings=applicable,
            scope_receipt=receipt,
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
    scope_obtained_via: Literal[
        "fraimed_mcp", "provided_snapshot"
    ] = "provided_snapshot",
) -> dict[str, Any]:
    return PolicyService(service.project).check(
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
