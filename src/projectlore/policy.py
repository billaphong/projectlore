"""Built-in deterministic policy checkers for the Homebrew pilot."""

from __future__ import annotations

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

    def __init__(self, project: ProjectModel) -> None:
        self.project = project
        self._query = QueryService(project)

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
        findings = _findings(request.facts, rules)
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
    facts: dict[str, str], rules: dict[str, Any]
) -> list[Finding | None]:
    return [
        _compare(
            facts,
            rules,
            CALIBRATION_RULE,
            "calibration_backtest_end",
            "demand_issued_at",
            "reject_snapshot",
            "Calibration evidence postdates forecast issue.",
        ),
        _compare(
            facts,
            rules,
            ISSUE_RULE,
            "demand_issued_at",
            "snapshot_created_at",
            "reject_snapshot",
            "Demand was issued after snapshot creation.",
        ),
        _compare(
            facts,
            rules,
            HORIZON_RULE,
            "safety_lookahead_end",
            "demand_valid_through",
            "input_untrusted",
            "Demand does not cover the complete safety lookahead.",
        ),
    ]


def _compare(
    facts: dict[str, str],
    rules: dict[str, Any],
    rule_id: str,
    left_name: str,
    right_name: str,
    outcome: str,
    failure_message: str,
) -> Finding | None:
    if left_name not in facts or right_name not in facts:
        return None
    rule = rules.get(rule_id)
    sources = [] if rule is None else list(rule.source_refs)
    if rule is None:
        return Finding(
            rule_id=rule_id,
            decision="indeterminate",
            outcome="missing_rule",
            message="Required rule is missing from the model.",
            source_refs=sources,
        )
    try:
        left = datetime.fromisoformat(facts[left_name].replace("Z", "+00:00"))
        right = datetime.fromisoformat(facts[right_name].replace("Z", "+00:00"))
    except ValueError:
        return Finding(
            rule_id=rule_id,
            decision="indeterminate",
            outcome="invalid_fact",
            message="Policy timestamps must be ISO 8601 values.",
            source_refs=sources,
        )
    failed = left > right
    return Finding(
        rule_id=rule_id,
        decision="fail" if failed else "pass",
        outcome=outcome if failed else "no_finding",
        message=failure_message if failed else "Rule satisfied.",
        source_refs=sources,
    )
