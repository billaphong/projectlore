from __future__ import annotations

import asyncio
import json
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
from projectlore.workflow import WorkflowAuthenticationRequired, WorkflowTarget
from projectlore.workflow_target import configure_workflow_target

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
    stale_not_applicable = policy.check(PolicyRequest(facts={}, scope=stale))

    assert passed["decision"] == "pass"
    assert failed["decision"] == "fail"
    assert not_applicable["decision"] == "not_applicable"
    assert stale_not_applicable["decision"] == "not_applicable"


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
        assert result[1]["contract_version"] == "projectlore-tools/0.3.0"

    timeout = asyncio.run(
        server.call_tool(
            "policy_check",
            {"facts": {}},
        )
    )
    assert isinstance(timeout, tuple)
    assert timeout[1]["decision"] == "not_applicable"


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
            {"facts": {}},
        )
    )
    assert isinstance(policy, tuple)
    assert policy[1]["decision"] == "not_applicable"


def test_policy_tool_schema_is_provider_neutral_and_facts_only_required() -> None:
    tools = asyncio.run(create_server(MODEL).list_tools())
    policy_tool = next(tool for tool in tools if tool.name == "policy_check")
    schema = policy_tool.inputSchema

    assert schema["required"] == ["facts"]
    assert set(schema["properties"]) == {
        "facts",
        "context_requirements",
        "target_identity",
    }
    assert "frame_id" not in json.dumps(schema)
    assert "space_id" not in json.dumps(schema)


def test_mcp_resolves_workflow_zero_or_one_time_from_the_frozen_plan(
    tmp_path: Path,
) -> None:
    model = tmp_path / "projectlore.yaml"
    scoped_rule = "lore:homebrew/rule/workflow-forecast-issued-by-snapshot"
    model.write_text(
        MODEL.read_text(encoding="utf-8").replace(
            "lore:homebrew/rule/forecast-issued-by-snapshot", scoped_rule
        ),
        encoding="utf-8",
    )
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps(
            [
                {
                    "rule_id": scoped_rule,
                    "left_fact": "demand_issued_at",
                    "relation": "lte",
                    "right_fact": "snapshot_created_at",
                    "right_literal": None,
                    "value_type": "datetime",
                    "failure_outcome": "reject_snapshot",
                    "failure_message": "Demand was issued after snapshot creation.",
                    "scope_requirement": "workflow",
                },
            ]
        ),
        encoding="utf-8",
    )
    configure_workflow_target(
        tmp_path,
        WorkflowTarget(
            target_version="projectlore-workflow-target/1.0.0",
            project_id="lore:homebrew/forecast-trust",
            model_entrypoint="projectlore.yaml",
            provider_id="fraimed",
            scope_id="frame",
            container_id="space",
        ),
    )
    authority = CountingScopeAuthority()
    server = create_server(model, authority)

    timeless = asyncio.run(
        server.call_tool(
            "policy_check",
            {
                "facts": {
                    "calibration_backtest_end": "2026-08-02T00:00:00Z",
                    "demand_issued_at": "2026-08-01T00:00:00Z",
                },
            },
        )
    )
    assert isinstance(timeless, tuple)
    assert authority.calls == 0

    scoped = asyncio.run(
        server.call_tool(
            "policy_check",
            {
                "facts": {
                    "demand_issued_at": "2026-08-01T00:00:00Z",
                    "snapshot_created_at": "2026-08-01T01:00:00Z",
                },
            },
        )
    )
    assert isinstance(scoped, tuple)
    assert authority.calls == 1
    by_rule = {item["rule_id"]: item for item in scoped[1]["findings"]}
    assert by_rule[scoped_rule]["workflow_receipt"] is not None
    assert all(
        item["workflow_receipt"] is None
        for rule_id, item in by_rule.items()
        if rule_id != scoped_rule
    )


def test_mcp_preserves_typed_provider_failure_per_binding(tmp_path: Path) -> None:
    model = tmp_path / "projectlore.yaml"
    scoped_rule = "lore:homebrew/rule/workflow-forecast-issued-by-snapshot"
    model.write_text(
        MODEL.read_text(encoding="utf-8").replace(
            "lore:homebrew/rule/forecast-issued-by-snapshot", scoped_rule
        ),
        encoding="utf-8",
    )
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps(
            [
                {
                    "rule_id": scoped_rule,
                    "left_fact": "demand_issued_at",
                    "relation": "lte",
                    "right_fact": "snapshot_created_at",
                    "right_literal": None,
                    "value_type": "datetime",
                    "failure_outcome": "reject_snapshot",
                    "failure_message": "Demand was issued after snapshot creation.",
                    "scope_requirement": "workflow",
                }
            ]
        ),
        encoding="utf-8",
    )
    configure_workflow_target(
        tmp_path,
        WorkflowTarget(
            target_version="projectlore-workflow-target/1.0.0",
            project_id="lore:homebrew/forecast-trust",
            model_entrypoint="projectlore.yaml",
            provider_id="fraimed",
            scope_id="frame",
            container_id="space",
        ),
    )
    result = asyncio.run(
        create_server(model, AuthenticationFailureAuthority()).call_tool(
            "policy_check",
            {
                "facts": {
                    "demand_issued_at": "2026-08-01T00:00:00Z",
                    "snapshot_created_at": "2026-08-01T01:00:00Z",
                },
            },
        )
    )
    assert isinstance(result, tuple)
    by_rule = {item["rule_id"]: item for item in result[1]["findings"]}
    assert by_rule[scoped_rule]["outcome"] == "workflow_authentication_required"
    mismatch = asyncio.run(
        create_server(model, MismatchedScopeAuthority()).call_tool(
            "policy_check",
            {
                "facts": {
                    "demand_issued_at": "2026-08-01T00:00:00Z",
                    "snapshot_created_at": "2026-08-01T01:00:00Z",
                },
            },
        )
    )
    assert isinstance(mismatch, tuple)
    mismatch_by_rule = {
        item["rule_id"]: item for item in mismatch[1]["findings"]
    }
    assert mismatch_by_rule[scoped_rule]["outcome"] == "workflow_target_mismatch"


class CountingScopeAuthority:
    def __init__(self) -> None:
        self.calls = 0

    async def current_scope(self, frame_id: str, space_id: str) -> ScopeSnapshot:
        self.calls += 1
        return _scope(datetime.now(UTC))


class AuthenticationFailureAuthority:
    async def current_scope(self, frame_id: str, space_id: str) -> ScopeSnapshot:
        raise WorkflowAuthenticationRequired()


class MismatchedScopeAuthority:
    async def current_scope(self, frame_id: str, space_id: str) -> ScopeSnapshot:
        return ScopeSnapshot(
            authority="fraimed",
            frame_id="different-frame",
            frame_title="Other",
            frame_status="active",
            validation_open=0,
            observed_at=datetime.now(UTC),
            authority_ref="fraimed://frame/different-frame",
        )


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
