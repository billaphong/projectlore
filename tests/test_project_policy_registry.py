from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from projectlore.policy import (
    MAX_POLICY_REGISTRY_BYTES,
    PolicyRequest,
    load_policy_registry,
    policy_check,
)
from projectlore.scope import ScopeSnapshot
from projectlore.service import ModelService

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "examples" / "sienna.campaign-authority.project.yaml"
RULE_ID = "lore:test/rule/discount-cap"
SOURCE_RULE_ID = "lore:sienna/rule/authoritative-command-boundary"


def _scope() -> ScopeSnapshot:
    return ScopeSnapshot(
        authority="fraimed",
        frame_id="pricing-enforcement",
        frame_title="Prove project-local policy enforcement",
        frame_status="in_progress",
        validation_open=1,
        observed_at=datetime.now(UTC),
        authority_ref="fraimed://frame/pricing-enforcement",
    )


def _binding() -> dict[str, object]:
    return {
        "rule_id": RULE_ID,
        "left_fact": "discount_rate",
        "relation": "lte",
        "right_fact": None,
        "right_literal": "0.30",
        "value_type": "decimal",
        "failure_outcome": "discount_cap_exceeded",
        "failure_message": "Discount exceeds the approved cap.",
    }


def _write_model(path: Path) -> None:
    path.write_text(
        MODEL.read_text(encoding="utf-8").replace(SOURCE_RULE_ID, RULE_ID),
        encoding="utf-8",
    )


def test_project_registry_adds_strict_decimal_policy(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps([_binding()]),
        encoding="utf-8",
    )
    model = tmp_path / "projectlore.yaml"
    _write_model(model)
    registry = load_policy_registry(tmp_path)
    service = ModelService(model)

    passing = policy_check(
        service,
        PolicyRequest(facts={"discount_rate": "0.20"}, scope=_scope()),
        registry=registry,
    )
    failing = policy_check(
        service,
        PolicyRequest(facts={"discount_rate": "0.40"}, scope=_scope()),
        registry=registry,
    )

    assert passing["decision"] == "pass"
    assert failing["decision"] == "fail"
    assert failing["findings"][0]["outcome"] == "discount_cap_exceeded"


def test_policy_scope_is_required_only_when_declared(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    model = tmp_path / "projectlore.yaml"
    _write_model(model)
    service = ModelService(model)
    binding = _binding()
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps([binding]), encoding="utf-8"
    )

    offline = policy_check(
        service,
        PolicyRequest(facts={"discount_rate": "0.20"}),
        registry=load_policy_registry(tmp_path),
    )
    binding["scope_requirement"] = "workflow"
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps([binding]), encoding="utf-8"
    )
    workflow_required = policy_check(
        service,
        PolicyRequest(facts={"discount_rate": "0.20"}),
        registry=load_policy_registry(tmp_path),
    )

    assert offline["decision"] == "pass"
    assert offline["scope_receipt"] is None
    assert workflow_required["decision"] == "indeterminate"
    assert workflow_required["findings"][0]["outcome"] == (
        "dependency_unavailable"
    )


def test_hook_loads_project_registry_and_blocks_violation(
    tmp_path: Path,
) -> None:
    model = tmp_path / "projectlore.yaml"
    _write_model(model)
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps([_binding()]),
        encoding="utf-8",
    )
    request = PolicyRequest(
        facts={"discount_rate": "0.40"},
        scope=_scope(),
    )
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_path / "change.projectlore-policy.json"),
            "content": request.model_dump_json(),
        },
    }
    environment = dict(os.environ)
    environment["PROJECTLORE_MODEL"] = "projectlore.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "projectlore.hook"],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 2
    assert RULE_ID in result.stderr
    assert "discount_cap_exceeded" in result.stderr


def test_project_registry_rejects_executable_fields(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    binding = _binding()
    binding["command"] = ["python", "-c", "print('not allowed')"]
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps([binding]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Policy registry is invalid"):
        load_policy_registry(tmp_path)


def test_project_registry_rejects_oversized_input(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    (registry_dir / "policy-bindings.json").write_bytes(
        b" " * (MAX_POLICY_REGISTRY_BYTES + 1)
    )

    with pytest.raises(ValueError, match="exceeds 64 KiB"):
        load_policy_registry(tmp_path)


def test_project_registry_cannot_override_builtin_rule(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    binding = _binding()
    binding["rule_id"] = SOURCE_RULE_ID
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps([binding]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="rule IDs must be unique"):
        load_policy_registry(tmp_path)


def test_decimal_policy_rejects_non_finite_fact(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".projectlore"
    registry_dir.mkdir()
    (registry_dir / "policy-bindings.json").write_text(
        json.dumps([_binding()]),
        encoding="utf-8",
    )
    model = tmp_path / "projectlore.yaml"
    _write_model(model)

    result = policy_check(
        ModelService(model),
        PolicyRequest(facts={"discount_rate": "NaN"}, scope=_scope()),
        registry=load_policy_registry(tmp_path),
    )

    assert result["decision"] == "indeterminate"
    assert result["findings"][0]["outcome"] == "invalid_fact"
