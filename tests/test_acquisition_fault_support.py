from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator

SUPPORT = Path(__file__).parents[1] / "fault-support" / "src"
sys.path.insert(0, str(SUPPORT))

from projectlore_fault_support.controller import (  # noqa: E402
    FaultController,
    FaultPlan,
)
from projectlore_fault_support.generator import generate, generate_traces  # noqa: E402
from projectlore_fault_support.model_checker import (  # noqa: E402
    check,
    coverage_receipt,
)


def test_frozen_fault_matrix_is_complete_and_safe(tmp_path: Path) -> None:
    contract = Path("docs/contracts/knowledge-acquisition-v0.6.1/fault-contract.json")
    matrix = generate(contract)
    result = check(matrix)
    frozen = json.loads(contract.read_text(encoding="utf-8"))
    assert len(matrix) == frozen["phase_failure_coverage"]["matrix_cases"] == 50
    assert result["transitions"] == 5
    traces = generate_traces(contract)
    assert [item["observation"] for item in traces] == [
        item["expected_observation"] for item in matrix
    ]
    wheel = tmp_path / "projectlore.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("projectlore/__init__.py", "__version__ = 'test'\n")
        archive.writestr("projectlore.dist-info/METADATA", "Name: projectlore\n")
    receipt = coverage_receipt(
        matrix,
        traces,
        contract_manifest_digest="sha256:" + "1" * 64,
        source_tree="a" * 40,
        production_wheel=wheel,
    )
    assert len(traces) == 50
    assert receipt["production_absence"] is True
    schema = json.loads(
        Path("docs/contracts/knowledge-acquisition-v0.6.1/schemas.json").read_text()
    )
    Draft202012Validator({**schema, "$ref": "#/$defs/test_support_receipt"}).validate(
        receipt
    )
    trace_validator = Draft202012Validator({**schema, "$ref": "#/$defs/fault_trace"})
    for trace in traces:
        trace_validator.validate(trace)


def test_fault_support_is_absent_from_production_package() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "fault-support" not in pyproject
    assert not (Path("src/projectlore") / "fault_support.py").exists()


def test_controller_injects_exactly_once() -> None:
    controller = FaultController(
        FaultPlan(7, "canonical_root.replace", "after", "terminate")
    )
    assert (
        controller.checkpoint(
            ordinal=7,
            selector="canonical_root.replace",
            phase="after",
            state_digest="sha256:" + "0" * 64,
        )
        == "terminate"
    )
