from __future__ import annotations

from pathlib import Path

from projectlore.assurance import (
    AuthoritativeCheckAdapter,
    GateEvidence,
    build_gate_evidence,
    execute_repository_gate,
    gate_exit_code,
    plan_authoritative_checks,
    resolve_changed_file_impact,
    write_gate_evidence,
)
from projectlore.checker import CheckerExecution
from projectlore.compiler import ProjectModel, compile_model
from projectlore.models import ProjectKnowledgeModel


def _project() -> ProjectModel:
    model = ProjectKnowledgeModel.model_validate(
        {
            "schema_version": "0.1.0",
            "model_version": "0.1.0",
            "id": "lore:test",
            "name": "Test",
            "domains": [{"id": "d", "name": "D"}],
            "concepts": [
                {
                    "id": "c",
                    "name": "C",
                    "description": "C",
                    "domain_ref": "d",
                    "rule_refs": ["r:one"],
                    "implementation_anchors": [{"path": "src/owned.py"}],
                }
            ],
            "rules": [
                {
                    "id": "r:one",
                    "statement": "One",
                    "kind": "invariant",
                    "severity": "blocker",
                },
                {
                    "id": "r:two",
                    "statement": "Two",
                    "kind": "invariant",
                    "severity": "error",
                },
            ],
            "integration_manifest": {
                "manifest_version": "0.1.0",
                "checker_bindings": [
                    {
                        "id": "binding",
                        "rule_refs": ["r:one"],
                        "checker": "project.tests",
                    }
                ],
            },
        }
    )
    return compile_model(model)


def _execution(decision: str) -> CheckerExecution:
    return CheckerExecution.model_validate(
        {
            "execution_version": "projectlore-checker-execution/0.1.0",
            "checker": "tests",
            "decision": decision,
            "reason_code": "completed",
            "exit_code": 0 if decision == "pass" else 1,
            "stdout": "",
            "stderr": "",
            "output_truncated": False,
            "network": "deny",
            "network_enforcement": "os_sandbox",
            "sandbox_backend": "test",
            "argv_digest": "sha256:abc",
        }
    )


def test_impact_resolution_is_deterministic_and_conservative() -> None:
    project = _project()
    anchored = resolve_changed_file_impact(project, ["src/owned.py", "src/owned.py"])
    assert anchored.applicable_rule_ids == ("r:one",)
    assert anchored.conservative_fallback is False

    unknown = resolve_changed_file_impact(project, ["src/new.py"])
    assert unknown.applicable_rule_ids == ("r:one", "r:two")
    assert unknown.conservative_fallback is True


def test_model_change_selects_all_rules_and_paths_are_bounded() -> None:
    project = _project()
    selection = resolve_changed_file_impact(project, ["projectlore.yaml"])
    assert selection.applicable_rule_ids == ("r:one", "r:two")


def test_adapters_delegate_to_authoritative_checkers() -> None:
    project = _project()
    selection = resolve_changed_file_impact(project, ["src/owned.py"])
    adapter = AuthoritativeCheckAdapter(
        name="project.tests",
        kind="project_test",
        trusted_checker="project.pytest",
        source_refs=("file:tests/test_rules.py",),
    )
    planned = plan_authoritative_checks(
        project, selection, {"project.tests": adapter}
    )
    assert planned[0].trusted_checker == "project.pytest"
    assert planned[0].rule_ids == ("r:one",)


def test_evidence_is_stable_bounded_and_never_certifies_repository() -> None:
    project = _project()
    selection = resolve_changed_file_impact(project, ["src/owned.py"])
    planned = plan_authoritative_checks(
        project,
        selection,
        {
            "project.tests": AuthoritativeCheckAdapter(
                name="project.tests",
                kind="project_test",
                trusted_checker="project.pytest",
            )
        },
    )
    first = build_gate_evidence(
        project, selection, planned, [_execution("pass")],
        assurance_scope="local_advisory",
    )
    second = build_gate_evidence(
        project, selection, planned, [_execution("pass")],
        assurance_scope="local_advisory",
    )
    assert first.evidence_id == second.evidence_id
    assert first.repository_certified is False
    assert gate_exit_code(first) == 0

    failed = build_gate_evidence(
        project, selection, planned, [_execution("fail")],
        assurance_scope="ci_job_result",
    )
    assert gate_exit_code(failed) == 1


def test_uncovered_applicable_rule_is_indeterminate() -> None:
    project = _project()
    selection = resolve_changed_file_impact(project, ["src/unmapped.py"])
    evidence = build_gate_evidence(
        project,
        selection,
        (),
        (),
        assurance_scope="local_advisory",
    )
    assert evidence.decision == "indeterminate"
    assert gate_exit_code(evidence) == 2


def test_local_and_ci_like_execution_pass_and_fail_without_credentials(
    tmp_path: Path,
) -> None:
    project = _project()
    adapter = AuthoritativeCheckAdapter(
        name="project.tests",
        kind="project_test",
        trusted_checker="project.pytest",
    )

    def compliant(planned: object) -> CheckerExecution:
        del planned
        return _execution("pass")

    def violating(planned: object) -> CheckerExecution:
        del planned
        return _execution("fail")

    local = execute_repository_gate(
        project,
        ["src/owned.py"],
        {"project.tests": adapter},
        compliant,
        assurance_scope="local_advisory",
    )
    ci = execute_repository_gate(
        project,
        ["src/owned.py"],
        {"project.tests": adapter},
        violating,
        assurance_scope="ci_job_result",
    )
    assert gate_exit_code(local) == 0
    assert gate_exit_code(ci) == 1
    assert local.repository_certified is ci.repository_certified is False

    output = tmp_path / ".projectlore" / "evidence" / "gate.json"
    write_gate_evidence(output, ci)
    assert GateEvidence.model_validate_json(
        output.read_text(encoding="utf-8")
    ) == ci
