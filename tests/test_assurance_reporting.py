from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from projectlore.assurance import GateEvidence
from projectlore.assurance_report import (
    AssuranceState,
    IntegrationEvidence,
    ProtectedGateObservation,
    assess_assurance,
)
from projectlore.cli import main

MODEL_DIGEST = "sha256:model"


def _gate(scope: str) -> GateEvidence:
    return GateEvidence.model_validate(
        {
            "evidence_version": "projectlore-gate-evidence/0.1.0",
            "evidence_id": f"sha256:{scope}",
            "model_digest": MODEL_DIGEST,
            "changed_files_digest": "sha256:files",
            "assurance_scope": scope,
            "repository_certified": False,
            "selected_rule_ids": (),
            "planned_checks": (),
            "executions": (),
            "decision": "pass",
        }
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
    *,
    local: bool = False,
    ci: bool = False,
    protected: ProtectedGateObservation | None = None,
) -> IntegrationEvidence:
    return IntegrationEvidence(
        evidence_version="projectlore-integration-evidence/0.1.0",
        hook_active=True,
        hook_evidence_refs=("file:.projectlore/trust/client.json",),
        local_gate=_gate("local_advisory") if local else None,
        ci_gate=_gate("ci_job_result") if ci else None,
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
    now = datetime.now(UTC)
    assert assess_assurance(MODEL_DIGEST).achieved_state == "available"
    assert assess_assurance(
        MODEL_DIGEST, _evidence()
    ).achieved_state == "hook_active"
    assert assess_assurance(
        MODEL_DIGEST, _evidence(local=True)
    ).achieved_state == "local_gate_passed"
    assert assess_assurance(
        MODEL_DIGEST, _evidence(local=True, ci=True)
    ).achieved_state == "ci_gate_passed"
    report = assess_assurance(
        MODEL_DIGEST,
        _evidence(local=True, ci=True, protected=_protected(now)),
        now=now,
    )
    assert report.achieved_state == "protected_gate_enforced"
    assert report.protected_verification == "verified"


def test_protected_gate_requires_complete_fresh_read_only_evidence() -> None:
    now = datetime.now(UTC)
    stale = _protected(
        now - timedelta(minutes=10),
        accessible=False,
        bypass_allowed=True,
        verifier_permission_scope=("repository:read",),
    )
    report = assess_assurance(
        MODEL_DIGEST,
        _evidence(local=True, ci=True, protected=stale),
        now=now,
    )
    assert report.achieved_state == "ci_gate_passed"
    assert report.protected_verification == "indeterminate"
    assert "fresh_hosted_configuration" in report.missing_requirements
    assert "hosted_configuration_accessible" in report.missing_requirements
    assert "non_bypassable_policy" in report.missing_requirements
    assert "sufficient_read_only_verifier_permissions" in (
        report.missing_requirements
    )


def test_offline_report_is_useful_and_lists_every_missing_requirement() -> None:
    report = assess_assurance(MODEL_DIGEST)
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
