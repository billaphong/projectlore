from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from projectlore.policy import PolicyRequest, PolicyResult
from projectlore.scope import ScopeReceipt, ScopeSnapshot
from projectlore.scope_cache import ScopeTarget
from projectlore.source_gate import SourceGateEvidence

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


@pytest.mark.parametrize(
    ("filename", "model"),
    (
        ("scope-snapshot-legacy-fraimed.json", ScopeSnapshot),
        ("scope-receipt-0.1.0-fraimed.json", ScopeReceipt),
        ("scope-target-0.1.0-fraimed.json", ScopeTarget),
        ("policy-request-tools-0.2.0.json", PolicyRequest),
        ("policy-result-tools-0.2.0.json", PolicyResult),
        ("source-gate-0.1.0.json", SourceGateEvidence),
    ),
)
def test_frozen_workflow_payloads_load_without_value_loss(
    filename: str,
    model: type[BaseModel],
) -> None:
    raw = (FIXTURES / filename).read_text(encoding="utf-8")
    payload = json.loads(raw)

    parsed = model.model_validate_json(raw)

    assert parsed.model_dump(mode="json") == payload


def test_unknown_scope_target_version_has_explicit_diagnostic() -> None:
    payload = json.loads(
        (FIXTURES / "scope-target-0.1.0-fraimed.json").read_text(
            encoding="utf-8"
        )
    )
    payload["target_version"] = "scope-target/9.0.0"

    with pytest.raises(ValidationError, match="target_version"):
        ScopeTarget.model_validate(payload)
