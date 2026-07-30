"""Client-neutral interactive enforcement decisions and audit evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from projectlore.hook_event import ProjectLoreAgentEvent
from projectlore.models import StrictModel
from projectlore.scope import ScopeReceipt

Decision = Literal["allow", "block", "advise", "indeterminate"]


class SessionContextReceipt(StrictModel):
    receipt_version: Literal["projectlore-session-context/0.1.0"]
    event_id: str
    client: str
    session_id: str | None
    requested_at: datetime
    resolution: Literal["resolved", "unavailable", "not_required"]
    model_digest: str | None
    claim: Literal["context_request_resolved"]


class EnforcementResult(StrictModel):
    result_version: Literal["projectlore-enforcement/0.1.0"]
    event_id: str
    event: str
    decision: Decision
    policy_decision: str | None = None
    reason_code: str
    message: str
    side_effects_undone: Literal[False] = False


class AuditRecord(StrictModel):
    audit_version: Literal["projectlore-audit/0.1.0"]
    audit_id: str
    recorded_at: datetime
    event_id: str
    client: str
    event: str
    is_subagent: bool
    model_digest: str | None
    scope_digest: str | None
    decision: Decision
    reason_code: str


def decide_interactive(
    event: ProjectLoreAgentEvent,
    *,
    policy_decision: str | None,
    dependency_state: Literal["available", "unavailable", "timeout"] = "available",
    receipt: ScopeReceipt | None = None,
) -> EnforcementResult:
    if dependency_state != "available":
        return _result(
            event,
            "indeterminate",
            f"dependency_{dependency_state}",
            "Required policy dependency was not available.",
        )
    if receipt is not None and not receipt.fresh:
        return _result(
            event,
            "indeterminate",
            "stale_scope",
            "Authoritative workflow scope is stale.",
        )
    if event.event == "PreToolUse":
        if policy_decision == "fail":
            return _result(
                event,
                "block",
                "deterministic_violation",
                "A deterministic applicable policy violation blocked the action.",
                policy_decision,
            )
        if policy_decision == "pass":
            return _result(
                event,
                "allow",
                "policy_pass",
                "Applicable deterministic policy checks passed.",
                policy_decision,
            )
        return _result(
            event,
            "indeterminate",
            "policy_not_decidable",
            "The pre-action policy decision was not deterministic.",
            policy_decision,
        )
    if event.event in {"PostToolUse", "Stop"}:
        return _result(
            event,
            "advise" if policy_decision == "fail" else "allow",
            "post_action_finding" if policy_decision == "fail" else "no_finding",
            (
                "A completed action may require correction; ProjectLore did not "
                "undo or claim to undo side effects."
                if policy_decision == "fail"
                else "No post-action policy finding."
            ),
            policy_decision,
        )
    return _result(
        event,
        "allow",
        "context_event",
        "The lifecycle event does not itself authorize a blocking decision.",
        policy_decision,
    )


def session_context_receipt(
    event: ProjectLoreAgentEvent,
    *,
    model_digest: str | None,
    resolution: Literal["resolved", "unavailable", "not_required"],
) -> SessionContextReceipt:
    return SessionContextReceipt(
        receipt_version="projectlore-session-context/0.1.0",
        event_id=event.event_id,
        client=event.client,
        session_id=event.session_id,
        requested_at=datetime.now(UTC),
        resolution=resolution,
        model_digest=model_digest,
        claim="context_request_resolved",
    )


def audit_record(
    event: ProjectLoreAgentEvent,
    result: EnforcementResult,
    *,
    model_digest: str | None,
    scope_receipt: ScopeReceipt | None,
) -> AuditRecord:
    content = {
        "event_id": event.event_id,
        "client": event.client,
        "event": event.event,
        "decision": result.decision,
        "reason_code": result.reason_code,
        "model_digest": model_digest,
        "scope_digest": (
            scope_receipt.scope_digest if scope_receipt is not None else None
        ),
    }
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    return AuditRecord(
        audit_version="projectlore-audit/0.1.0",
        audit_id=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        recorded_at=datetime.now(UTC),
        event_id=event.event_id,
        client=event.client,
        event=event.event,
        is_subagent=event.is_subagent,
        model_digest=model_digest,
        scope_digest=content["scope_digest"],
        decision=result.decision,
        reason_code=result.reason_code,
    )


def _result(
    event: ProjectLoreAgentEvent,
    decision: Decision,
    reason_code: str,
    message: str,
    policy_decision: str | None = None,
) -> EnforcementResult:
    return EnforcementResult(
        result_version="projectlore-enforcement/0.1.0",
        event_id=event.event_id,
        event=event.event,
        decision=decision,
        policy_decision=policy_decision,
        reason_code=reason_code,
        message=message,
        side_effects_undone=False,
    )
