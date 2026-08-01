"""Evidence-bound repository assurance reporting."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from projectlore.assurance import (
    GateEvidenceAny,
    GateEvidenceV0,
    validate_gate_evidence,
)
from projectlore.compiler import ProjectModel
from projectlore.models import StrictModel


class AssuranceState(StrEnum):
    AVAILABLE = "available"
    HOOK_ACTIVE = "hook_active"
    LOCAL_GATE_PASSED = "local_gate_passed"
    CI_GATE_PASSED = "ci_gate_passed"
    PROTECTED_GATE_ENFORCED = "protected_gate_enforced"


class ProtectedGateObservation(StrictModel):
    observation_version: Literal["projectlore-protected-gate/0.1.0"]
    accessible: bool
    repository: str = Field(min_length=1, max_length=512)
    repository_verified: bool
    branch: str = Field(min_length=1, max_length=512)
    branch_verified: bool
    required_hosted_check: str = Field(min_length=1, max_length=512)
    check_is_required: bool
    bypass_allowed: bool
    bypass_policy_verified: bool
    configuration_revision: str = Field(min_length=1, max_length=512)
    observed_at: datetime
    maximum_age_seconds: int = Field(default=300, ge=1, le=3600)
    verifier_permission_scope: tuple[str, ...]
    verifier_identity: str = Field(min_length=1, max_length=512)
    source_url: str = Field(pattern=r"^https://", max_length=2048)


class IntegrationEvidence(StrictModel):
    evidence_version: Literal["projectlore-integration-evidence/0.1.0"]
    hook_active: bool = False
    hook_evidence_refs: tuple[str, ...] = ()
    local_gate: GateEvidenceAny | None = None
    ci_gate: GateEvidenceAny | None = None
    protected_gate: ProtectedGateObservation | None = None


MAX_INTEGRATION_EVIDENCE_BYTES = 384 * 1024


def parse_integration_evidence(
    raw: bytes,
) -> tuple[IntegrationEvidence | None, tuple[str, ...]]:
    """Tolerantly parse bounded imported evidence without granting trust."""

    if len(raw) > MAX_INTEGRATION_EVIDENCE_BYTES:
        return None, ("invalid_integration_evidence:artifact_too_large",)
    try:
        evidence = IntegrationEvidence.model_validate_json(raw)
    except (ValidationError, ValueError):
        return None, ("invalid_integration_evidence:malformed",)
    return evidence, ()


def load_integration_evidence(
    path: Path,
) -> tuple[IntegrationEvidence | None, tuple[str, ...]]:
    """Read no more than the accepted artifact bound plus one sentinel byte."""

    if not path.is_file() or path.is_symlink():
        return None, ("invalid_integration_evidence:not_regular_file",)
    with path.open("rb") as handle:
        raw = handle.read(MAX_INTEGRATION_EVIDENCE_BYTES + 1)
    return parse_integration_evidence(raw)


class AssuranceReport(StrictModel):
    report_version: Literal["projectlore-assurance-report/0.1.0"]
    achieved_state: AssuranceState = Field(strict=False)
    protected_verification: Literal[
        "not_requested", "verified", "indeterminate"
    ]
    missing_requirements: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    offline_useful: Literal[True] = True


def assess_assurance(
    model_digest: str,
    evidence: IntegrationEvidence | None = None,
    *,
    project: ProjectModel | None = None,
    ingestion_diagnostics: tuple[str, ...] = (),
    now: datetime | None = None,
) -> AssuranceReport:
    """Advance only through contiguous assurance levels with valid evidence."""

    current_time = now or datetime.now(UTC)
    supplied = evidence or IntegrationEvidence(
        evidence_version="projectlore-integration-evidence/0.1.0"
    )
    achieved = AssuranceState.AVAILABLE
    refs: list[str] = [f"model:{model_digest}"]
    missing: list[str] = list(ingestion_diagnostics)

    hook_valid = supplied.hook_active and bool(supplied.hook_evidence_refs)
    if hook_valid:
        achieved = AssuranceState.HOOK_ACTIVE
        refs.extend(supplied.hook_evidence_refs)
    else:
        missing.append("active_hook_with_reviewable_evidence")

    local_consistent = _valid_gate(
        supplied.local_gate, project, "local_advisory"
    )
    if local_consistent:
        missing.append("authenticated_local_gate_provenance")
    else:
        missing.append("passing_local_gate_for_current_model")

    ci_valid = _valid_gate(supplied.ci_gate, project, "ci_job_result")
    if ci_valid:
        missing.append("authenticated_ci_provenance")
    else:
        missing.append("passing_ci_gate_for_current_model")

    protected_status: Literal[
        "not_requested", "verified", "indeterminate"
    ] = "not_requested"
    observation = supplied.protected_gate
    if observation is None:
        missing.append("authorized_protected_gate_observation")
    else:
        protected_status = "indeterminate"
        protected_missing = _protected_missing(observation, current_time)
        missing.extend(protected_missing)
        if (
            achieved == AssuranceState.CI_GATE_PASSED
            and not protected_missing
        ):
            achieved = AssuranceState.PROTECTED_GATE_ENFORCED
            protected_status = "verified"
            refs.append(
                "protected:"
                f"{observation.repository}:{observation.branch}:"
                f"{observation.configuration_revision}"
            )

    return AssuranceReport(
        report_version="projectlore-assurance-report/0.1.0",
        achieved_state=achieved,
        protected_verification=protected_status,
        missing_requirements=tuple(dict.fromkeys(missing)),
        evidence_refs=tuple(dict.fromkeys(refs)),
        offline_useful=True,
    )


def _valid_gate(
    evidence: GateEvidenceAny | None,
    project: ProjectModel | None,
    scope: Literal["local_advisory", "ci_job_result"],
) -> bool:
    if evidence is None or isinstance(evidence, GateEvidenceV0) or project is None:
        return False
    try:
        state = validate_gate_evidence(evidence, project)
    except ValueError:
        return False
    return bool(
        state == "project_semantics_validated"
        and evidence.assurance_scope == scope
        and evidence.decision == "pass"
    )


def _protected_missing(
    observation: ProtectedGateObservation,
    now: datetime,
) -> list[str]:
    missing: list[str] = []
    if not observation.accessible:
        missing.append("hosted_configuration_accessible")
    if not observation.repository or not observation.repository_verified:
        missing.append("verified_repository")
    if not observation.branch or not observation.branch_verified:
        missing.append("verified_branch")
    if not observation.required_hosted_check or not observation.check_is_required:
        missing.append("required_hosted_check")
    if observation.bypass_allowed or not observation.bypass_policy_verified:
        missing.append("non_bypassable_policy")
    if not observation.configuration_revision:
        missing.append("configuration_revision")
    observed_at = observation.observed_at
    if observed_at.tzinfo is None:
        missing.append("timezone_aware_observation")
    else:
        age = (now - observed_at.astimezone(UTC)).total_seconds()
        if age < 0 or age > observation.maximum_age_seconds:
            missing.append("fresh_hosted_configuration")
    required_scopes = {"repository:read", "rules:read"}
    if not required_scopes.issubset(observation.verifier_permission_scope):
        missing.append("sufficient_read_only_verifier_permissions")
    return missing
