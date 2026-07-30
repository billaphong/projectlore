from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from projectlore.enforcement import (
    audit_record,
    decide_interactive,
    session_context_receipt,
)
from projectlore.hook_event import (
    UnsupportedEventError,
    normalize_hook_event,
)
from projectlore.scope import ScopeSnapshot, issue_scope_receipt


def _event(
    name: str = "PreToolUse",
    *,
    subagent: bool = False,
):
    return normalize_hook_event(
        {
            "cwd": "C:/projects/example",
            "hook_event_name": name,
            "tool_name": "Write",
            "tool_input": {"file_path": "example.txt", "content": "bounded"},
            "session_id": "session",
            "agent_id": "child" if subagent else None,
            "is_subagent": subagent,
        },
        client="claude_code",
    )


def _scope(observed_at: datetime):
    return ScopeSnapshot(
        authority="fraimed",
        frame_id="frame",
        frame_title="Frame",
        frame_status="in_progress",
        validation_open=1,
        observed_at=observed_at,
        authority_ref="fraimed://frame/frame",
        confirmed_scope_version=3,
        closure_generation=12,
    )


def test_events_are_versioned_deterministic_and_bounded() -> None:
    first = _event()
    second = _event()

    assert first.event_version == "projectlore-agent-event/0.1.0"
    assert first.event_id == second.event_id
    with pytest.raises((ValueError, ValidationError), match="16 KiB"):
        normalize_hook_event(
            {
                "cwd": "C:/project",
                "tool_input": {"content": "x" * 20_000},
            },
            client="codex_cli",
        )


@pytest.mark.parametrize(
    ("dependency", "reason"),
    [
        ("unavailable", "dependency_unavailable"),
        ("timeout", "dependency_timeout"),
    ],
)
def test_required_dependency_failures_are_indeterminate(
    dependency: str, reason: str
) -> None:
    result = decide_interactive(
        _event(),
        policy_decision=None,
        dependency_state=dependency,  # type: ignore[arg-type]
    )

    assert result.decision == "indeterminate"
    assert result.reason_code == reason


def test_stale_scope_and_bypass_attempt_are_indeterminate() -> None:
    stale = issue_scope_receipt(
        _scope(datetime.now(UTC) - timedelta(minutes=10)),
        maximum_age_seconds=300,
    )
    stale_result = decide_interactive(
        _event(), policy_decision="pass", receipt=stale
    )
    bypass_result = decide_interactive(_event(), policy_decision=None)

    assert stale_result.reason_code == "stale_scope"
    assert stale.confirmed_scope_version == 3
    assert stale.closure_generation == 12
    assert bypass_result.reason_code == "policy_not_decidable"


def test_only_pre_action_deterministic_failure_blocks() -> None:
    blocked = decide_interactive(_event(), policy_decision="fail")
    post = decide_interactive(_event("PostToolUse"), policy_decision="fail")

    assert blocked.decision == "block"
    assert post.decision == "advise"
    assert post.side_effects_undone is False


def test_unsupported_malformed_and_subagent_cases_are_explicit() -> None:
    with pytest.raises(UnsupportedEventError):
        _event("InstructionsLoaded")
    with pytest.raises(ValueError, match="cwd"):
        normalize_hook_event({}, client="codex_cli")

    event = _event(subagent=True)
    result = decide_interactive(event, policy_decision="fail")
    assert event.is_subagent is True
    assert result.decision == "block"


def test_session_receipt_claims_resolution_not_cognition() -> None:
    receipt = session_context_receipt(
        _event("SessionStart"),
        model_digest="sha256:model",
        resolution="resolved",
    )

    assert receipt.claim == "context_request_resolved"
    assert "understood" not in receipt.model_dump_json()


def test_audit_record_contains_digests_not_source_bodies_or_secrets() -> None:
    event = _event()
    result = decide_interactive(event, policy_decision="fail")
    scope = issue_scope_receipt(_scope(datetime.now(UTC)))

    record = audit_record(
        event,
        result,
        model_digest="sha256:model",
        scope_receipt=scope,
    )
    encoded = record.model_dump_json()

    assert record.scope_digest == scope.scope_digest
    assert "bounded" not in encoded
    assert "secret" not in encoded.casefold()
