"""Built-in deterministic policy checkers for the Homebrew pilot."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

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


def policy_check(service: ModelService, request: PolicyRequest) -> dict[str, Any]:
    receipt = issue_scope_receipt(request.scope)
    rules = {rule.id: rule for rule in service.model.rules}
    findings = [
        _compare(
            request.facts,
            rules,
            CALIBRATION_RULE,
            "calibration_backtest_end",
            "demand_issued_at",
            "reject_snapshot",
            "Calibration evidence postdates forecast issue.",
        ),
        _compare(
            request.facts,
            rules,
            ISSUE_RULE,
            "demand_issued_at",
            "snapshot_created_at",
            "reject_snapshot",
            "Demand was issued after snapshot creation.",
        ),
        _compare(
            request.facts,
            rules,
            HORIZON_RULE,
            "safety_lookahead_end",
            "demand_valid_through",
            "input_untrusted",
            "Demand does not cover the complete safety lookahead.",
        ),
    ]
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
    return service.envelope(result.model_dump(mode="json"))


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
