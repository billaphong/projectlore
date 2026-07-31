from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from projectlore.cli import main
from projectlore.fraimed import ScopeAuthority
from projectlore.mcp_server import create_server
from projectlore.policy import PolicyRequest, policy_check
from projectlore.scope import ScopeSnapshot
from projectlore.service import CONTRACT_VERSION, ModelService

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"
CORPUS = ROOT / "evaluations" / "homebrew-forecast-trust" / "corpus.yaml"


def scope() -> ScopeSnapshot:
    return ScopeSnapshot(
        authority="fraimed",
        frame_id="019fb0b0-2e3d-720a-858f-10444184fe59",
        frame_title="Build the Homebrew dual-agent enforcement walking skeleton",
        frame_status="in_progress",
        validation_open=7,
        observed_at=datetime.now(UTC),
        authority_ref="fraimed://frame/019fb0b0-2e3d-720a-858f-10444184fe59",
    )


def test_status_and_context_share_contract_and_model_digests() -> None:
    service = ModelService(MODEL)

    status = service.model_status()
    context = service.context_for_task("prevent current-day calibration look-ahead")

    assert status["contract_version"] == CONTRACT_VERSION
    assert status["contract_digest"] == context["contract_digest"]
    assert status["model_digest"] == context["model_digest"]
    assert {
        "lore:homebrew/rule/calibration-predates-forecast",
    } <= {rule["id"] for rule in context["rules"]}
    assert context["sources"]


def test_frozen_policy_corpus_matches_all_expected_outcomes() -> None:
    service = ModelService(MODEL)
    corpus = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))

    for case in corpus["policy_cases"]:
        result = policy_check(
            service,
            PolicyRequest(facts=case["facts"], scope=scope()),
        )
        finding = result["findings"][0]
        assert finding["rule_id"] == case["rule_id"]
        assert finding["decision"] == (
            "fail" if case["expected"] == "violation" else "pass"
        )
        assert finding["outcome"] == case["expected_outcome"]
        receipt = result["scope_receipt"]
        assert receipt["fresh"] is True
        assert receipt["claim"] == "scope_observed"


def test_mcp_tools_return_the_same_digests_as_the_core() -> None:
    service = ModelService(MODEL)
    server = create_server(MODEL, StaticScopeAuthority())

    status_result = asyncio.run(server.call_tool("model_status", {}))
    context_result = asyncio.run(
        server.call_tool(
            "context_for_task",
            {"task": "prevent current-day calibration look-ahead"},
        )
    )

    assert isinstance(status_result, tuple)
    assert isinstance(context_result, tuple)
    status = status_result[1]
    context = context_result[1]
    assert status["contract_digest"] == service.model_status()["contract_digest"]
    assert status["model_digest"] == context["model_digest"]

    policy_result = asyncio.run(
        server.call_tool(
            "policy_check",
            {
                "facts": {
                    "demand_issued_at": "2026-07-22T12:00:00Z",
                    "snapshot_created_at": "2026-07-22T12:00:00Z",
                }
                ,
                "frame_id": "019fb0b0-2e3d-720a-858f-10444184fe59",
                "space_id": "019e67a2-d321-74b7-ba2a-90a93a26f630",
            },
        )
    )
    assert isinstance(policy_result, tuple)
    policy = policy_result[1]
    assert policy["contract_digest"] == status["contract_digest"]
    assert policy["model_digest"] == status["model_digest"]
    assert policy["scope_receipt"] is None


def test_policy_operations_do_not_modify_the_model() -> None:
    before = MODEL.read_bytes()
    service = ModelService(MODEL)
    request: dict[str, Any] = {
        "calibration_backtest_end": "2026-07-22T11:30:00Z",
        "demand_issued_at": "2026-07-22T11:00:00Z",
    }

    policy_check(service, PolicyRequest(facts=request, scope=scope()))
    service.context_for_task("calibration evidence")
    service.model_status()

    assert MODEL.read_bytes() == before


def test_policy_request_round_trips_as_hook_json() -> None:
    request = PolicyRequest(
        facts={
            "demand_issued_at": "2026-07-22T12:00:00Z",
            "snapshot_created_at": "2026-07-22T12:00:00Z",
        },
        scope=scope(),
    )

    encoded = request.model_dump_json()
    decoded = json.loads(encoded)

    assert decoded["scope"]["authority"] == "fraimed"


def test_both_client_hook_shapes_block_all_frozen_violations() -> None:
    corpus = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
    violations = [
        case for case in corpus["policy_cases"] if case["expected"] == "violation"
    ]

    for case in violations:
        request = _hook_request(case["facts"])
        claude = _run_hook(
            {
                "cwd": str(ROOT),
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(ROOT / f"{case['id']}.projectlore-policy.json"),
                    "content": request,
                },
            }
        )
        codex = _run_hook(
            {
                "cwd": str(ROOT),
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": (
                        "*** Begin Patch\n"
                        f"*** Add File: {case['id']}.projectlore-policy.json\n"
                        + "\n".join(f"+{line}" for line in request.splitlines())
                        + "\n*** End Patch\n"
                    )
                },
            }
        )

        assert claude.returncode == 2
        assert codex.returncode == 2
        assert case["rule_id"] in claude.stderr
        assert case["rule_id"] in codex.stderr


def test_both_client_hook_shapes_allow_compliant_policy_input() -> None:
    request = _hook_request(
        {
            "demand_issued_at": "2026-07-22T12:00:00Z",
            "snapshot_created_at": "2026-07-22T12:00:00Z",
        }
    )

    result = _run_hook(
        {
            "cwd": str(ROOT),
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(ROOT / "pass.projectlore-policy.json"),
                "content": request,
            },
        }
    )

    assert result.returncode == 0


def test_lore_check_blocks_violation_and_allows_compliant_fixture(
    tmp_path: Path,
) -> None:
    violation = tmp_path / "violation.json"
    violation.write_text(
        _hook_request(
            {
                "calibration_backtest_end": "2026-07-22T11:30:00Z",
                "demand_issued_at": "2026-07-22T11:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    compliant = tmp_path / "compliant.json"
    compliant.write_text(
        _hook_request(
            {
                "calibration_backtest_end": "2026-07-22T10:59:59Z",
                "demand_issued_at": "2026-07-22T11:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    assert main(["check", str(MODEL), str(violation)]) == 1
    assert main(["check", str(MODEL), str(compliant)]) == 0


def _hook_request(facts: dict[str, str]) -> str:
    request = PolicyRequest(facts=facts, scope=scope())
    return request.model_dump_json(indent=2)


def _run_hook(event: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    environment = {
        "PROJECTLORE_MODEL": str(MODEL),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
    }
    return subprocess.run(
        [sys.executable, "-I", "-m", "projectlore.hook"],
        cwd=ROOT,
        input=json.dumps(event),
        text=True,
        capture_output=True,
        env=environment,
        timeout=3,
        check=False,
    )


class StaticScopeAuthority(ScopeAuthority):
    async def current_scope(self, frame_id: str, space_id: str) -> ScopeSnapshot:
        assert frame_id
        assert space_id
        return scope()
