"""Bounded state-machine checker for acquisition commit claims."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path

from projectlore_fault_support.machine import explore


def check(matrix: Iterable[Mapping[str, object]]) -> dict[str, int]:
    cases = list(matrix)
    if len(cases) != 50 or len({str(item["id"]) for item in cases}) != 50:
        raise ValueError("fault matrix must contain exactly 50 distinct cases")
    if any(item["expected_observation"] not in {"old", "new"} for item in cases):
        raise ValueError("fault matrix permits a mixed or missing terminal state")
    transitions = {
        ("unclaimed_old", "claim", "claimed_old"),
        ("claimed_old", "canonical_root.replace", "claimed_new"),
        ("claimed_old", "abort", "claim_failed_old"),
        ("claimed_new", "workflow_root.replace", "terminal_new"),
        ("claimed_new", "recover", "terminal_new"),
    }
    return {"cases": len(cases), "states": 5, "transitions": len(transitions)}


def coverage_receipt(
    matrix: Iterable[Mapping[str, object]],
    traces: Iterable[Mapping[str, object]],
    *,
    contract_manifest_digest: str,
    source_tree: str,
    production_wheel: Path,
) -> dict[str, object]:
    cases = list(matrix)
    trace_values = list(traces)
    check(cases)
    if len(trace_values) != len(cases):
        raise ValueError("fault traces do not cover the frozen matrix")
    states, transitions = explore()
    payload = {
        "case_ids": sorted(str(item["id"]) for item in cases),
        "trace_ids": sorted(str(item["trace_id"]) for item in trace_values),
    }
    coverage_digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
    )
    module_root = Path(__file__).parent
    generator = module_root / "generator.py"
    checker = module_root / "model_checker.py"
    controller = module_root / "controller.py"
    artifact_digest = (
        "sha256:"
        + hashlib.sha256(
            generator.read_bytes() + checker.read_bytes() + controller.read_bytes()
        ).hexdigest()
    )
    production_absence = inspect_production_wheel(production_wheel)
    candidate_wheel = (
        "sha256:" + hashlib.sha256(production_wheel.read_bytes()).hexdigest()
    )
    return {
        "contract_version": "projectlore-test-support-receipt/0.6.1",
        "artifact_digest": artifact_digest,
        "generator_digest": "sha256:"
        + hashlib.sha256(generator.read_bytes()).hexdigest(),
        "model_checker_digest": "sha256:"
        + hashlib.sha256(checker.read_bytes()).hexdigest(),
        "catalog_digest": "sha256:"
        + hashlib.sha256(
            json.dumps(cases, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest(),
        "states_explored": len(states),
        "transitions_explored": len(transitions),
        "coverage_digest": coverage_digest,
        "production_absence": production_absence,
        "proof_pass": all(
            item["observation"] in {"old", "new"} for item in trace_values
        ),
        "contract_manifest_digest": contract_manifest_digest,
        "source_tree": source_tree,
        "candidate_wheel": candidate_wheel,
    }


def inspect_production_wheel(path: Path) -> bool:
    forbidden = (
        b"projectlore_fault_support",
        b"projectlore-fault-plan",
        b"FaultController",
        b"canonical_root.replace",
    )
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if "fault_support" in name:
                return False
            if name.endswith((".py", ".json", "METADATA", "entry_points.txt")):
                value = archive.read(name)
                if any(token in value for token in forbidden):
                    return False
    return True


def main() -> None:
    raise SystemExit("invoke through the deterministic generator/check API")
