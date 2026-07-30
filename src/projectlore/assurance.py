"""Deterministic repository impact selection and gate evidence contracts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field

from projectlore.checker import (
    CheckerExecution,
    CheckerRegistry,
    NetworkSandbox,
    run_checker,
)
from projectlore.compiler import ProjectModel
from projectlore.models import StrictModel

MAX_CHANGED_FILES = 4096
MAX_EVIDENCE_EXECUTIONS = 1024
MODEL_PATHS = frozenset({".projectlore/model.yaml", "projectlore.yaml"})

AdapterKind = Literal["semgrep", "architecture_test", "project_test"]


class ImpactSelection(StrictModel):
    selection_version: Literal["projectlore-impact/0.1.0"]
    model_digest: str
    changed_files: tuple[str, ...]
    applicable_rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    conservative_fallback: bool


class AuthoritativeCheckAdapter(StrictModel):
    """Local adapter metadata; command authority remains in CheckerRegistry."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    kind: AdapterKind
    trusted_checker: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    source_refs: tuple[str, ...] = ()


class PlannedCheck(StrictModel):
    adapter: str
    kind: AdapterKind
    trusted_checker: str
    rule_ids: tuple[str, ...]
    source_refs: tuple[str, ...]


class GateEvidence(StrictModel):
    evidence_version: Literal["projectlore-gate-evidence/0.1.0"]
    evidence_id: str
    model_digest: str
    changed_files_digest: str
    assurance_scope: Literal["local_advisory", "ci_job_result"]
    repository_certified: Literal[False] = False
    selected_rule_ids: tuple[str, ...]
    planned_checks: tuple[PlannedCheck, ...]
    executions: tuple[CheckerExecution, ...]
    decision: Literal["pass", "fail", "indeterminate"]


def resolve_changed_file_impact(
    project: ProjectModel,
    changed_files: Sequence[str],
) -> ImpactSelection:
    """Select impacted rules, falling back to every rule for unknown changes."""

    normalized = tuple(sorted({_normalize_path(path) for path in changed_files}))
    if len(normalized) > MAX_CHANGED_FILES:
        raise ValueError(f"Changed file count exceeds {MAX_CHANGED_FILES}.")
    all_rules = tuple(sorted(rule.id for rule in project.model.rules))
    if not normalized:
        return ImpactSelection(
            selection_version="projectlore-impact/0.1.0",
            model_digest=project.digest,
            changed_files=(),
            applicable_rule_ids=(),
            reasons=("no_changes",),
            conservative_fallback=False,
        )
    if any(path in MODEL_PATHS for path in normalized):
        return _selection(
            project, normalized, all_rules, ("canonical_model_changed",), True
        )

    anchors: dict[str, set[str]] = {}
    for concept in project.model.concepts:
        for anchor in concept.implementation_anchors:
            path = _normalize_path(anchor.path)
            anchors.setdefault(path, set()).update(concept.rule_refs)

    selected: set[str] = set()
    unknown: list[str] = []
    for changed in normalized:
        matched = {
            rule_id
            for anchor, rule_ids in anchors.items()
            if _paths_overlap(changed, anchor)
            for rule_id in rule_ids
        }
        if matched:
            selected.update(matched)
        else:
            unknown.append(changed)
    if unknown:
        return _selection(
            project,
            normalized,
            all_rules,
            ("unmapped_change_requires_all_rules", *unknown),
            True,
        )
    return _selection(
        project,
        normalized,
        tuple(sorted(selected)),
        ("implementation_anchor_match",),
        False,
    )


def plan_authoritative_checks(
    project: ProjectModel,
    selection: ImpactSelection,
    adapters: Mapping[str, AuthoritativeCheckAdapter],
) -> tuple[PlannedCheck, ...]:
    """Bind selected rules to local adapters without reproducing check semantics."""

    manifest = project.model.integration_manifest
    if manifest is None:
        return ()
    selected = set(selection.applicable_rule_ids)
    grouped: dict[str, set[str]] = {}
    for binding in manifest.checker_bindings:
        applicable = selected.intersection(binding.rule_refs)
        if applicable:
            grouped.setdefault(binding.checker, set()).update(applicable)
    planned: list[PlannedCheck] = []
    for name in sorted(grouped):
        try:
            adapter = adapters[name]
        except KeyError as error:
            raise ValueError(
                f"Checker binding {name!r} has no local authoritative adapter."
            ) from error
        planned.append(
            PlannedCheck(
                adapter=adapter.name,
                kind=adapter.kind,
                trusted_checker=adapter.trusted_checker,
                rule_ids=tuple(sorted(grouped[name])),
                source_refs=tuple(sorted(set(adapter.source_refs))),
            )
        )
    return tuple(planned)


def build_gate_evidence(
    project: ProjectModel,
    selection: ImpactSelection,
    planned_checks: Sequence[PlannedCheck],
    executions: Sequence[CheckerExecution],
    *,
    assurance_scope: Literal["local_advisory", "ci_job_result"],
) -> GateEvidence:
    if len(executions) > MAX_EVIDENCE_EXECUTIONS:
        raise ValueError(f"Execution count exceeds {MAX_EVIDENCE_EXECUTIONS}.")
    decisions = {item.decision for item in executions}
    covered_rules = {
        rule_id for planned in planned_checks for rule_id in planned.rule_ids
    }
    complete_coverage = covered_rules == set(selection.applicable_rule_ids)
    if "fail" in decisions:
        decision: Literal["pass", "fail", "indeterminate"] = "fail"
    elif (
        "indeterminate" in decisions
        or len(executions) != len(planned_checks)
        or not complete_coverage
    ):
        decision = "indeterminate"
    else:
        decision = "pass"
    changed_digest = _digest(selection.changed_files)
    content = {
        "model_digest": project.digest,
        "changed_files_digest": changed_digest,
        "assurance_scope": assurance_scope,
        "selected_rule_ids": selection.applicable_rule_ids,
        "planned_checks": [
            item.model_dump(mode="json") for item in planned_checks
        ],
        "execution_ids": [item.argv_digest for item in executions],
        "decision": decision,
    }
    return GateEvidence(
        evidence_version="projectlore-gate-evidence/0.1.0",
        evidence_id=_digest(content),
        model_digest=project.digest,
        changed_files_digest=changed_digest,
        assurance_scope=assurance_scope,
        repository_certified=False,
        selected_rule_ids=selection.applicable_rule_ids,
        planned_checks=tuple(planned_checks),
        executions=tuple(executions),
        decision=decision,
    )


def gate_exit_code(evidence: GateEvidence) -> int:
    return {"pass": 0, "fail": 1, "indeterminate": 2}[evidence.decision]


def execute_repository_gate(
    project: ProjectModel,
    changed_files: Sequence[str],
    adapters: Mapping[str, AuthoritativeCheckAdapter],
    invoke: Callable[[PlannedCheck], CheckerExecution],
    *,
    assurance_scope: Literal["local_advisory", "ci_job_result"],
) -> GateEvidence:
    """Run delegated authoritative checks and assemble one bounded artifact."""

    selection = resolve_changed_file_impact(project, changed_files)
    planned = plan_authoritative_checks(project, selection, adapters)
    executions = tuple(invoke(item) for item in planned)
    return build_gate_evidence(
        project,
        selection,
        planned,
        executions,
        assurance_scope=assurance_scope,
    )


def invoke_authoritative_check(
    planned: PlannedCheck,
    *,
    registry: CheckerRegistry,
    project_root: Path,
    sandbox: NetworkSandbox | None,
) -> CheckerExecution:
    """Delegate to the exact trusted command configured for the project check."""

    return run_checker(
        registry,
        planned.trusted_checker,
        project_root=project_root,
        sandbox=sandbox,
    )


def write_gate_evidence(path: Path, evidence: GateEvidence) -> None:
    """Atomically write a machine-readable evidence artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = evidence.model_dump_json(indent=2)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _selection(
    project: ProjectModel,
    changed_files: tuple[str, ...],
    applicable: tuple[str, ...],
    reasons: tuple[str, ...],
    fallback: bool,
) -> ImpactSelection:
    return ImpactSelection(
        selection_version="projectlore-impact/0.1.0",
        model_digest=project.digest,
        changed_files=changed_files,
        applicable_rule_ids=applicable,
        reasons=reasons,
        conservative_fallback=fallback,
    )


def _normalize_path(value: str) -> str:
    if "\x00" in value or Path(value).is_absolute():
        raise ValueError(f"Changed path must be repository-relative: {value!r}")
    path = PurePosixPath(value.replace("\\", "/"))
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Changed path is not normalized: {value!r}")
    return path.as_posix()


def _paths_overlap(changed: str, anchor: str) -> bool:
    return (
        changed == anchor
        or changed.startswith(f"{anchor}/")
        or anchor.startswith(f"{changed}/")
    )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
