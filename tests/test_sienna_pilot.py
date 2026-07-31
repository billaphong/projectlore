from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import yaml

from projectlore.evaluation import evaluate_once
from projectlore.mcp_server import create_server
from projectlore.policy import PolicyRequest, policy_check
from projectlore.scope import ScopeSnapshot
from projectlore.scope_cache import LegacyScopeAuthority
from projectlore.service import ModelService
from projectlore.validation import validate_path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "sienna.campaign-authority.project.yaml"
CORPUS = ROOT / "evaluations" / "sienna-campaign-authority" / "corpus.yaml"
FRAME_ID = "019fb0b0-4f6a-7f27-8625-44f8fb5ccdc0"
SPACE_ID = "019e67a2-d321-74b7-ba2a-90a93a26f630"


class StaticScopeAuthority(LegacyScopeAuthority):
    async def current_scope(
        self, frame_id: str, space_id: str | None = None
    ) -> ScopeSnapshot:
        assert frame_id == FRAME_ID
        assert space_id == SPACE_ID
        return _scope()


def _scope() -> ScopeSnapshot:
    return ScopeSnapshot(
        authority="fraimed",
        frame_id=FRAME_ID,
        frame_title="Prove portability in a contrasting Sophie or Sienna domain",
        frame_status="in_progress",
        validation_open=6,
        observed_at=datetime.now(UTC),
        authority_ref=f"fraimed://frame/{FRAME_ID}",
    )


def test_sienna_model_has_two_valid_provenance_backed_rules() -> None:
    model, report = validate_path(MODEL)

    assert report.valid
    assert model is not None
    assert [rule.id for rule in model.rules] == [
        "lore:sienna/rule/authoritative-command-boundary",
        "lore:sienna/rule/deterministic-replay",
    ]
    assert all(rule.source_refs and rule.implementation_anchors for rule in model.rules)


def test_sienna_frozen_questions_and_policy_cases_use_shared_contracts() -> None:
    corpus = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
    service = ModelService(MODEL)

    assert len(corpus["questions"]) == 3
    for question in corpus["questions"]:
        context = service.context_for_task(question["prompt"])
        assert set(question["expected_rule_ids"]) <= {
            rule["id"] for rule in context["rules"]
        }
        assert set(question["expected_source_ids"]) <= {
            source["id"] for source in context["sources"]
        }

    for case in corpus["policy_cases"]:
        result = policy_check(
            service,
            PolicyRequest(facts=case["facts"], scope=_scope()),
        )
        finding = result["findings"][0]
        assert finding["rule_id"] == case["rule_id"]
        assert finding["decision"] == (
            "fail" if case["expected"] == "violation" else "pass"
        )
        assert finding["outcome"] == case["expected_outcome"]
        assert result["scope_receipt"]["claim"] == "scope_observed"


def test_sienna_mcp_and_core_share_contract_model_and_policy_outcomes() -> None:
    service = ModelService(MODEL)
    server = create_server(MODEL, StaticScopeAuthority())

    status_result = asyncio.run(server.call_tool("model_status", {}))
    context_result = asyncio.run(
        server.call_tool(
            "context_for_task",
            {"task": "deterministic campaign replay digest"},
        )
    )
    policy_result = asyncio.run(
        server.call_tool(
            "policy_check",
            {
                "facts": {"mutation_path": "client_direct_state_write"},
                "frame_id": FRAME_ID,
                "space_id": SPACE_ID,
            },
        )
    )

    assert isinstance(status_result, tuple)
    assert isinstance(context_result, tuple)
    assert isinstance(policy_result, tuple)
    status = status_result[1]
    context = context_result[1]
    policy = policy_result[1]
    assert status["contract_digest"] == service.model_status()["contract_digest"]
    assert status["contract_digest"] == context["contract_digest"]
    assert status["model_digest"] == context["model_digest"]
    assert policy["decision"] == "fail"
    assert policy["scope_receipt"] is None


def test_sienna_pre_registered_evaluation_passes(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    result = asyncio.run(
        evaluate_once(
            CORPUS,
            FRAME_ID,
            SPACE_ID,
            output,
            StaticScopeAuthority(),
        )
    )

    assert result["passed"] is True
    assert result["measurements"]["retrieval_success"] == {
        "successful": 3,
        "total": 3,
    }
    assert result["measurements"]["policy_catch_rate"] == {
        "caught": 2,
        "violations": 2,
    }
    assert result["measurements"]["policy_false_positive_rate"] == {
        "false_positives": 0,
        "compliant_cases": 2,
    }
    assert result["measurements"]["correction_rediscovery"] == {
        "rediscovered": 2,
        "total": 2,
    }
