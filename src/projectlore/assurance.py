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


class PlannedCheckV0(StrictModel):
    adapter: str
    kind: AdapterKind
    trusted_checker: str
    rule_ids: tuple[str, ...]
    source_refs: tuple[str, ...]


class GateEvidenceV0(StrictModel):
    evidence_version: Literal["projectlore-gate-evidence/0.1.0"]
    evidence_id: str
    model_digest: str
    changed_files_digest: str
    assurance_scope: Literal["local_advisory", "ci_job_result"]
    repository_certified: Literal[False] = False
    selected_rule_ids: tuple[str, ...]
    planned_checks: tuple[PlannedCheckV0, ...]
    executions: tuple[CheckerExecution, ...]
    decision: Literal["pass", "fail", "indeterminate"]


class ImpactSelectionV1(StrictModel):
    selection_version: Literal["projectlore-impact/1.0.0"]
    model_digest: str
    changed_files: tuple[str, ...]
    changed_files_digest: str
    applicable_rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    conservative_fallback: bool


class PlannedCheck(StrictModel):
    planned_check_version: Literal["projectlore-planned-check/1.0.0"]
    planned_check_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    adapter: str
    kind: AdapterKind
    trusted_checker: str
    rule_ids: tuple[str, ...]
    source_refs: tuple[str, ...]


class BoundCheckerExecution(StrictModel):
    binding_version: Literal["projectlore-bound-execution/1.0.0"]
    planned_check_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    execution: CheckerExecution


class GateEvidenceV1(StrictModel):
    evidence_version: Literal["projectlore-gate-evidence/1.0.0"]
    evidence_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selection: ImpactSelectionV1
    assurance_scope: Literal["local_advisory", "ci_job_result"]
    repository_certified: Literal[False] = False
    planned_checks: tuple[PlannedCheck, ...]
    bound_executions: tuple[BoundCheckerExecution, ...]
    decision: Literal["pass", "fail", "indeterminate"]

    @property
    def model_digest(self) -> str:
        return self.selection.model_digest

    @property
    def changed_files_digest(self) -> str:
        return self.selection.changed_files_digest

    @property
    def selected_rule_ids(self) -> tuple[str, ...]:
        return self.selection.applicable_rule_ids

    @property
    def executions(self) -> tuple[CheckerExecution, ...]:
        return tuple(item.execution for item in self.bound_executions)


# Preserve the original public name for frozen 0.1 callers.
GateEvidence = GateEvidenceV0
GateEvidenceAny = GateEvidenceV0 | GateEvidenceV1


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
        rule_ids = tuple(sorted(grouped[name]))
        source_refs = tuple(sorted(set(adapter.source_refs)))
        values: dict[str, object] = {
            "adapter": adapter.name,
            "kind": adapter.kind,
            "trusted_checker": adapter.trusted_checker,
            "rule_ids": rule_ids,
            "source_refs": source_refs,
        }
        planned.append(
            PlannedCheck(
                planned_check_version="projectlore-planned-check/1.0.0",
                planned_check_id=_planned_check_id(values),
                adapter=adapter.name,
                kind=adapter.kind,
                trusted_checker=adapter.trusted_checker,
                rule_ids=rule_ids,
                source_refs=source_refs,
            )
        )
    return tuple(sorted(planned, key=_planned_sort_key))


def build_gate_evidence(
    project: ProjectModel,
    selection: ImpactSelection,
    planned_checks: Sequence[PlannedCheck],
    bound_executions: Sequence[BoundCheckerExecution],
    *,
    assurance_scope: Literal["local_advisory", "ci_job_result"],
) -> GateEvidenceV1:
    authoritative = resolve_changed_file_impact(project, selection.changed_files)
    if authoritative != selection:
        raise ValueError("Impact selection does not match the current project.")
    ordered_plans = tuple(sorted(planned_checks, key=_planned_sort_key))
    if len({item.planned_check_id for item in ordered_plans}) != len(ordered_plans):
        raise ValueError("Planned check identifiers must be unique.")
    bound = tuple(bound_executions)
    if [item.planned_check_id for item in bound] != [
        item.planned_check_id for item in ordered_plans
    ]:
        raise ValueError("Executions must bind one-to-one in planned-check order.")
    for plan, item in zip(ordered_plans, bound, strict=True):
        _validate_execution_bounds(item.execution)
        if item.execution.checker != plan.trusted_checker:
            raise ValueError("Execution checker does not match its planned check.")
    changed_digest = _digest(authoritative.changed_files)
    selection_v1 = ImpactSelectionV1(
        selection_version="projectlore-impact/1.0.0",
        model_digest=project.digest,
        changed_files=authoritative.changed_files,
        changed_files_digest=changed_digest,
        applicable_rule_ids=authoritative.applicable_rule_ids,
        reasons=authoritative.reasons,
        conservative_fallback=authoritative.conservative_fallback,
    )
    decision = _derived_decision(selection_v1, ordered_plans, bound)
    provisional = GateEvidenceV1(
        evidence_version="projectlore-gate-evidence/1.0.0",
        evidence_id="sha256:" + "0" * 64,
        selection=selection_v1,
        assurance_scope=assurance_scope,
        repository_certified=False,
        planned_checks=ordered_plans,
        bound_executions=bound,
        decision=decision,
    )
    unsigned = provisional.model_dump(mode="json", exclude={"evidence_id"})
    evidence = provisional.model_copy(update={"evidence_id": _digest(unsigned)})
    validate_gate_evidence(evidence, project)
    return evidence


def gate_exit_code(evidence: GateEvidenceAny) -> int:
    return {"pass": 0, "fail": 1, "indeterminate": 2}[evidence.decision]


def bind_checker_execution(
    planned: PlannedCheck,
    execution: CheckerExecution,
) -> BoundCheckerExecution:
    """Bind a bounded execution to the exact plan that authorized it."""

    _validate_execution_bounds(execution)
    if execution.checker != planned.trusted_checker:
        raise ValueError("Execution checker does not match its planned check.")
    return BoundCheckerExecution(
        binding_version="projectlore-bound-execution/1.0.0",
        planned_check_id=planned.planned_check_id,
        execution=execution,
    )


def validate_gate_evidence(
    evidence: GateEvidenceV1,
    project: ProjectModel | None = None,
) -> Literal["structurally_self_consistent", "project_semantics_validated"]:
    """Validate canonical identity, bindings, and optional current-model semantics."""

    if len(evidence.bound_executions) > MAX_EVIDENCE_EXECUTIONS:
        raise ValueError(f"Execution count exceeds {MAX_EVIDENCE_EXECUTIONS}.")
    plans = tuple(sorted(evidence.planned_checks, key=_planned_sort_key))
    if plans != evidence.planned_checks:
        raise ValueError("Planned checks are not in canonical order.")
    plan_ids = [item.planned_check_id for item in plans]
    if len(set(plan_ids)) != len(plan_ids):
        raise ValueError("Planned check identifiers must be unique.")
    for plan in plans:
        values = {
            "adapter": plan.adapter,
            "kind": plan.kind,
            "trusted_checker": plan.trusted_checker,
            "rule_ids": plan.rule_ids,
            "source_refs": plan.source_refs,
        }
        if plan.rule_ids != tuple(sorted(set(plan.rule_ids))):
            raise ValueError("Planned rule identifiers must be sorted and unique.")
        if plan.source_refs != tuple(sorted(set(plan.source_refs))):
            raise ValueError("Planned source references must be sorted and unique.")
        if plan.planned_check_id != _planned_check_id(values):
            raise ValueError("Planned check identifier does not match its content.")
    bound_ids = [item.planned_check_id for item in evidence.bound_executions]
    if bound_ids != plan_ids:
        raise ValueError("Executions must bind one-to-one in planned-check order.")
    for plan, bound in zip(plans, evidence.bound_executions, strict=True):
        _validate_execution_bounds(bound.execution)
        if bound.execution.checker != plan.trusted_checker:
            raise ValueError("Execution checker does not match its planned check.")
    if evidence.selection.changed_files != tuple(
        sorted(set(evidence.selection.changed_files))
    ):
        raise ValueError("Changed files are not normalized, sorted, and unique.")
    normalized = tuple(
        _normalize_path(item) for item in evidence.selection.changed_files
    )
    if normalized != evidence.selection.changed_files:
        raise ValueError("Changed files are not normalized.")
    if evidence.selection.changed_files_digest != _digest(normalized):
        raise ValueError("Changed-files digest does not match changed files.")
    derived = _derived_decision(evidence.selection, plans, evidence.bound_executions)
    if evidence.decision != derived:
        raise ValueError("Gate decision does not match its plans and executions.")
    unsigned = evidence.model_dump(mode="json", exclude={"evidence_id"})
    if evidence.evidence_id != _digest(unsigned):
        raise ValueError("Gate evidence identifier does not match its content.")
    if project is None:
        return "structurally_self_consistent"
    authoritative = resolve_changed_file_impact(project, normalized)
    expected = (
        authoritative.model_digest,
        authoritative.changed_files,
        authoritative.applicable_rule_ids,
        authoritative.reasons,
        authoritative.conservative_fallback,
    )
    observed = (
        evidence.selection.model_digest,
        evidence.selection.changed_files,
        evidence.selection.applicable_rule_ids,
        evidence.selection.reasons,
        evidence.selection.conservative_fallback,
    )
    if observed != expected:
        raise ValueError("Gate impact selection does not match the current project.")
    return "project_semantics_validated"


def execute_repository_gate(
    project: ProjectModel,
    changed_files: Sequence[str],
    adapters: Mapping[str, AuthoritativeCheckAdapter],
    invoke: Callable[[PlannedCheck], CheckerExecution],
    *,
    assurance_scope: Literal["local_advisory", "ci_job_result"],
) -> GateEvidenceV1:
    """Run delegated authoritative checks and assemble one bounded artifact."""

    selection = resolve_changed_file_impact(project, changed_files)
    planned = plan_authoritative_checks(project, selection, adapters)
    bound: list[BoundCheckerExecution] = []
    for item in planned:
        try:
            execution = invoke(item)
        except (OSError, TimeoutError) as error:
            execution = _operational_failure(item, error)
        bound.append(bind_checker_execution(item, execution))
    return build_gate_evidence(
        project,
        selection,
        planned,
        bound,
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


def write_gate_evidence(path: Path, evidence: GateEvidenceV1) -> None:
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


def _planned_check_id(values: Mapping[str, object]) -> str:
    encoded = json.dumps(
        values, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    prefix = b"projectlore-planned-check/1.0.0\0"
    return f"sha256:{hashlib.sha256(prefix + encoded).hexdigest()}"


def _planned_sort_key(item: PlannedCheck) -> tuple[str, str, str, str]:
    return (item.adapter, item.kind, item.trusted_checker, item.planned_check_id)


def _derived_decision(
    selection: ImpactSelectionV1,
    plans: Sequence[PlannedCheck],
    bound: Sequence[BoundCheckerExecution],
) -> Literal["pass", "fail", "indeterminate"]:
    covered = {rule_id for plan in plans for rule_id in plan.rule_ids}
    if covered != set(selection.applicable_rule_ids):
        return "indeterminate"
    decisions = {item.execution.decision for item in bound}
    if "fail" in decisions:
        return "fail"
    if "indeterminate" in decisions:
        return "indeterminate"
    return "pass"


def _validate_execution_bounds(execution: CheckerExecution) -> None:
    fields = {
        "checker": (execution.checker, 128),
        "reason_code": (execution.reason_code, 256),
        "stdout": (execution.stdout, 64 * 1024),
        "stderr": (execution.stderr, 64 * 1024),
        "sandbox_backend": (execution.sandbox_backend or "", 256),
        "argv_digest": (execution.argv_digest, 256),
    }
    for name, (value, maximum) in fields.items():
        if len(value.encode("utf-8")) > maximum:
            raise ValueError(f"Execution {name} exceeds {maximum} bytes.")


def _operational_failure(
    planned: PlannedCheck,
    error: OSError | TimeoutError,
) -> CheckerExecution:
    reason = (
        "checker_timeout"
        if isinstance(error, TimeoutError)
        else "checker_unavailable"
    )
    return CheckerExecution(
        execution_version="projectlore-checker-execution/0.1.0",
        checker=planned.trusted_checker,
        decision="indeterminate",
        reason_code=reason,
        exit_code=None,
        stdout="",
        stderr="",
        output_truncated=False,
        network="deny",
        network_enforcement="not_run",
        sandbox_backend=None,
        argv_digest="sha256:unavailable",
    )
