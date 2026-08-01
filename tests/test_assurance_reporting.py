from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from projectlore.assurance import (
    GateEvidenceV1,
    build_gate_evidence,
    resolve_changed_file_impact,
)
from projectlore.assurance_report import (
    AssuranceState,
    IntegrationEvidence,
    ProtectedGateObservation,
    assess_assurance,
    parse_integration_evidence,
)
from projectlore.cli import main
from projectlore.compiler import ProjectModel, compile_model
from projectlore.models import ProjectKnowledgeModel


def _project() -> ProjectModel:
    return compile_model(
        ProjectKnowledgeModel.model_validate(
            {
                "schema_version": "0.1.0",
                "model_version": "0.1.0",
                "id": "lore:test",
                "name": "Test",
            }
        )
    )


def _gate(project: ProjectModel, scope: str) -> GateEvidenceV1:
    selection = resolve_changed_file_impact(project, ())
    return build_gate_evidence(
        project, selection, (), (), assurance_scope=scope  # type: ignore[arg-type]
    )


def _protected(now: datetime, **changes: object) -> ProtectedGateObservation:
    values: dict[str, object] = {
        "observation_version": "projectlore-protected-gate/0.1.0",
        "accessible": True,
        "repository": "owner/repo",
        "repository_verified": True,
        "branch": "main",
        "branch_verified": True,
        "required_hosted_check": "projectlore",
        "check_is_required": True,
        "bypass_allowed": False,
        "bypass_policy_verified": True,
        "configuration_revision": "ruleset:42",
        "observed_at": now,
        "maximum_age_seconds": 300,
        "verifier_permission_scope": ("repository:read", "rules:read"),
        "verifier_identity": "github:user:reviewer",
        "source_url": "https://api.github.test/repos/owner/repo/rules/42",
    }
    values.update(changes)
    return ProtectedGateObservation.model_validate(values)


def _evidence(
    project: ProjectModel,
    *,
    local: bool = False,
    ci: bool = False,
    protected: ProtectedGateObservation | None = None,
) -> IntegrationEvidence:
    return IntegrationEvidence(
        evidence_version="projectlore-integration-evidence/0.1.0",
        hook_active=True,
        hook_evidence_refs=("file:.projectlore/trust/client.json",),
        local_gate=_gate(project, "local_advisory") if local else None,
        ci_gate=_gate(project, "ci_job_result") if ci else None,
        protected_gate=protected,
    )


def test_assurance_states_are_exact_and_promote_contiguously() -> None:
    assert {item.value for item in AssuranceState} == {
        "available",
        "hook_active",
        "local_gate_passed",
        "ci_gate_passed",
        "protected_gate_enforced",
    }
    project = _project()
    model_digest = project.digest
    now = datetime.now(UTC)
    assert assess_assurance(model_digest).achieved_state == "available"
    assert assess_assurance(
        model_digest, _evidence(project)
    ).achieved_state == "hook_active"
    assert assess_assurance(
        model_digest, _evidence(project, local=True), project=project
    ).achieved_state == "hook_active"
    assert assess_assurance(
        model_digest, _evidence(project, local=True, ci=True), project=project
    ).achieved_state == "hook_active"
    report = assess_assurance(
        model_digest,
        _evidence(project, local=True, ci=True, protected=_protected(now)),
        project=project,
        now=now,
    )
    assert report.achieved_state == "hook_active"
    assert report.protected_verification == "indeterminate"
    assert "authenticated_ci_provenance" in report.missing_requirements


def test_protected_gate_requires_complete_fresh_read_only_evidence() -> None:
    now = datetime.now(UTC)
    project = _project()
    stale = _protected(
        now - timedelta(minutes=10),
        accessible=False,
        bypass_allowed=True,
        verifier_permission_scope=("repository:read",),
    )
    report = assess_assurance(
        project.digest,
        _evidence(project, local=True, ci=True, protected=stale),
        project=project,
        now=now,
    )
    assert report.achieved_state == "hook_active"
    assert report.protected_verification == "indeterminate"
    assert "fresh_hosted_configuration" in report.missing_requirements
    assert "hosted_configuration_accessible" in report.missing_requirements
    assert "non_bypassable_policy" in report.missing_requirements
    assert "sufficient_read_only_verifier_permissions" in (
        report.missing_requirements
    )


def test_offline_report_is_useful_and_lists_every_missing_requirement() -> None:
    report = assess_assurance(_project().digest)
    assert report.offline_useful is True
    assert report.protected_verification == "not_requested"
    assert report.missing_requirements == (
        "active_hook_with_reviewable_evidence",
        "passing_local_gate_for_current_model",
        "passing_ci_gate_for_current_model",
        "authorized_protected_gate_observation",
    )


def test_integration_check_cli_reports_without_hosted_credentials(
    tmp_path: Path, capsys: object
) -> None:
    model = tmp_path / "model.yaml"
    model.write_text(
        "\n".join(
            [
                "schema_version: 0.1.0",
                "model_version: 0.1.0",
                "id: lore:test",
                "name: Test",
            ]
        ),
        encoding="utf-8",
    )
    assert main(["integration", "check", str(model)]) == 2
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert payload["achieved_state"] == "available"
    assert payload["offline_useful"] is True


def test_imported_evidence_is_bounded_and_malformed_input_is_diagnostic() -> None:
    evidence, diagnostics = parse_integration_evidence(b"{" + b"x" * 400_000)
    assert evidence is None
    assert diagnostics == ("invalid_integration_evidence:artifact_too_large",)
    evidence, diagnostics = parse_integration_evidence(b"{not-json}")
    assert evidence is None
    assert diagnostics == ("invalid_integration_evidence:malformed",)
