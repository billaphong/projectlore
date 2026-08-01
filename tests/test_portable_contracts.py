from __future__ import annotations

import json
from pathlib import Path

from projectlore.schema import render_json_schema
from projectlore.validation import validate_path

ROOT = Path(__file__).resolve().parents[1]


def test_valid_portable_fixture_covers_public_contracts() -> None:
    model, report = validate_path(
        ROOT / "examples" / "contracts" / "portable.valid.yaml"
    )

    assert report.valid, report.diagnostics
    assert model is not None
    assert model.integration_manifest is not None
    assert len(model.integration_manifest.checker_bindings) == 1
    assert len(model.integration_manifest.context_profiles) == 1


def test_invalid_portable_fixture_has_stable_semantic_diagnostics() -> None:
    _, report = validate_path(ROOT / "examples" / "contracts" / "portable.invalid.yaml")

    assert not report.valid
    assert {item.code for item in report.diagnostics} == {"PL2002", "PL2201"}


def test_portable_schema_names_every_public_contract() -> None:
    schema = json.loads(render_json_schema())

    assert set(schema["x-projectlore-public-contracts"]) == {
        "ProjectKnowledgeModel",
        "Domain",
        "Concept",
        "Term",
        "Relationship",
        "Rule",
        "Source",
        "ImplementationAnchor",
        "CheckerBinding",
        "ContextProfile",
        "IntegrationManifest",
        "ScopeReceipt",
        "WorkflowTarget",
        "WorkflowObservation",
        "WorkflowReceipt",
        "DeclaredWorkflowContext",
        "ObservedWorkflowContext",
        "PolicyEvaluationPlan",
        "PlannedPolicyResult",
        "GateEvidenceV0",
        "GateEvidenceV1",
    }
    assert (
        set(schema["x-projectlore-public-contracts"]) - {"ProjectKnowledgeModel"}
        <= schema["$defs"].keys()
    )
    assert "Constraint" not in schema["$defs"]
