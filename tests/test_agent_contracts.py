from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from projectlore.compiler import compile_model
from projectlore.mcp_server import create_server
from projectlore.models import Term
from projectlore.policy import PolicyRequest, PolicyService
from projectlore.query import QueryService
from projectlore.scope import ScopeSnapshot
from projectlore.service import ModelService

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"


def test_golden_queries_distinguish_found_empty_and_not_found() -> None:
    query = QueryService(ModelService(MODEL).project)

    search = query.search("calibration look-ahead")
    context = query.context_for_task("prevent calibration look-ahead")
    empty = query.search("zzzqxv unmatchedtoken")
    missing = query.get_concept("lore:missing")

    assert search["result_state"] == "found"
    assert context["result_state"] == "found"
    assert context["provenance"]
    assert empty["result_state"] == "empty"
    assert missing["result_state"] == "not_found"
    assert search["model_digest"] == context["model_digest"]


def test_term_resolution_reports_ambiguity() -> None:
    service = ModelService(MODEL)
    concepts = list(service.model.concepts)
    alias = Term(value="shared name")
    concepts[0] = concepts[0].model_copy(update={"terms": [*concepts[0].terms, alias]})
    concepts[1] = concepts[1].model_copy(update={"terms": [*concepts[1].terms, alias]})
    model = service.model.model_copy(update={"concepts": concepts})

    result = QueryService(compile_model(model)).resolve_term("shared name")

    assert result["result_state"] == "ambiguous"
    assert len(result["matches"]) == 2


def test_relationship_traversal_is_bounded() -> None:
    query = QueryService(ModelService(MODEL).project)

    result = query.get_relationships(
        "lore:homebrew/calibration-evidence",
        direction="outgoing",
        max_depth=1,
        limit=1,
    )

    assert len(result["relationships"]) == 1
    assert result["max_depth"] == 1
    assert result["truncated"] is True


def test_policy_reports_all_four_decision_states() -> None:
    policy = PolicyService(ModelService(MODEL).project)
    fresh = _scope(datetime.now(UTC))
    stale = _scope(datetime.now(UTC) - timedelta(minutes=10))

    passed = policy.check(
        PolicyRequest(
            facts={
                "demand_issued_at": "2026-07-22T12:00:00Z",
                "snapshot_created_at": "2026-07-22T12:00:00Z",
            },
            scope=fresh,
        )
    )
    failed = policy.check(
        PolicyRequest(
            facts={
                "demand_issued_at": "2026-07-22T12:00:01Z",
                "snapshot_created_at": "2026-07-22T12:00:00Z",
            },
            scope=fresh,
        )
    )
    not_applicable = policy.check(PolicyRequest(facts={}, scope=fresh))
    indeterminate = policy.check(PolicyRequest(facts={}, scope=stale))

    assert passed["decision"] == "pass"
    assert failed["decision"] == "fail"
    assert not_applicable["decision"] == "not_applicable"
    assert indeterminate["decision"] == "indeterminate"
    assert indeterminate["findings"][0]["outcome"] == "stale_dependency"


def test_mcp_exposes_complete_read_only_contract_and_timeout_state() -> None:
    server = create_server(MODEL, TimeoutScopeAuthority())
    cases = {
        "model_search": {"query": "calibration"},
        "model_get_concept": {"concept_id": "lore:homebrew/calibration-evidence"},
        "model_resolve_term": {"term": "Calibration evidence"},
        "model_get_relationships": {"concept_id": "lore:homebrew/calibration-evidence"},
        "model_validate": {},
    }
    for tool, arguments in cases.items():
        result = asyncio.run(server.call_tool(tool, arguments))
        assert isinstance(result, tuple)
        assert result[1]["contract_version"] == "projectlore-tools/0.2.0"

    timeout = asyncio.run(
        server.call_tool(
            "policy_check",
            {"facts": {}, "frame_id": "frame", "space_id": "space"},
        )
    )
    assert isinstance(timeout, tuple)
    assert timeout[1]["decision"] == "indeterminate"
    assert timeout[1]["findings"][0]["outcome"] == "dependency_timeout"


def test_mcp_reads_start_without_fraimed_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRAIMED_API_TOKEN", raising=False)
    server = create_server(MODEL)

    status = asyncio.run(server.call_tool("model_status", {}))
    assert isinstance(status, tuple)
    assert status[1]["result_state"] == "complete"

    policy = asyncio.run(
        server.call_tool(
            "policy_check",
            {"facts": {}, "frame_id": "frame", "space_id": "space"},
        )
    )
    assert isinstance(policy, tuple)
    assert policy[1]["decision"] == "indeterminate"
    assert policy[1]["findings"][0]["outcome"] == "dependency_unavailable"


def _scope(observed_at: datetime) -> ScopeSnapshot:
    return ScopeSnapshot(
        authority="fraimed",
        frame_id="frame",
        frame_title="Frame",
        frame_status="in_progress",
        validation_open=1,
        observed_at=observed_at,
        authority_ref="fraimed://frame/frame",
    )


class TimeoutScopeAuthority:
    async def current_scope(self, frame_id: str, space_id: str) -> ScopeSnapshot:
        raise TimeoutError
