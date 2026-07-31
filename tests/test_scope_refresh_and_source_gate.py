from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from projectlore.cli import main
from projectlore.onboarding import apply_initialization, initialization_previews
from projectlore.scope import ScopeSnapshot
from projectlore.scope_cache import (
    configure_local_scope,
    configure_scope_target,
    load_scope_target,
    refresh_scope,
)
from projectlore.service import ModelService
from projectlore.source_gate import (
    evaluate_source_gate,
    source_gate_exit_code,
    write_source_gate_evidence,
)
from projectlore.workflow import WorkflowTarget
from projectlore.workflow_state import (
    apply_local_declaration,
    preview_local_declaration,
)

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "examples" / "sienna.campaign-authority.project.yaml"
MODEL_RULE_ID = "lore:sienna/rule/authoritative-command-boundary"
RULE_ID = "lore:merchant-pricing/rule/discount-cap"
SOURCE = '''from decimal import Decimal

DISCOUNT_RATES = {
    "STANDARD": Decimal("0.00"),
    "GOLD": Decimal("0.20"),
}
'''


class FakeScopeAuthority:
    def __init__(
        self,
        snapshot: ScopeSnapshot | None = None,
        error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def current_scope(
        self,
        frame_id: str,
        space_id: str,
    ) -> ScopeSnapshot:
        self.calls.append((frame_id, space_id))
        if self.error is not None:
            raise self.error
        assert self.snapshot is not None
        return self.snapshot


def _scope(*, observed_at: datetime | None = None) -> ScopeSnapshot:
    return ScopeSnapshot(
        authority="fraimed",
        frame_id="frame-123",
        frame_title="Gate configured source",
        frame_status="in_progress",
        validation_open=3,
        observed_at=observed_at or datetime.now(UTC),
        authority_ref="fraimed://frame/frame-123",
    )


def _project(tmp_path: Path) -> Path:
    model = tmp_path / "projectlore.yaml"
    model.write_text(
        MODEL.read_text(encoding="utf-8").replace(MODEL_RULE_ID, RULE_ID),
        encoding="utf-8",
    )
    (tmp_path / "pricing.py").write_text(SOURCE, encoding="utf-8")
    state = tmp_path / ".projectlore"
    state.mkdir()
    (state / "policy-bindings.json").write_text(
        json.dumps(
            [
                {
                    "rule_id": RULE_ID,
                    "left_fact": "discount_rate",
                    "relation": "lte",
                    "right_fact": None,
                    "right_literal": "0.30",
                    "value_type": "decimal",
                    "failure_outcome": "discount_cap_exceeded",
                    "failure_message": "Discount exceeds the approved cap.",
                }
            ]
        ),
        encoding="utf-8",
    )
    (state / "source-policy-bindings.json").write_text(
        json.dumps(
            [
                {
                    "path": "pricing.py",
                    "fact_name": "discount_rate",
                    "selector": "mapping_item",
                    "target": "DISCOUNT_RATES",
                    "key": "GOLD",
                    "value_syntax": "decimal_call",
                }
            ]
        ),
        encoding="utf-8",
    )
    (state / "scope.json").write_text(_scope().model_dump_json(), encoding="utf-8")
    return tmp_path


def test_scope_target_is_non_secret_and_refresh_is_atomic(
    tmp_path: Path,
) -> None:
    target_path, target = configure_scope_target(
        tmp_path,
        frame_id="frame-123",
        space_id="space-456",
    )
    authority = FakeScopeAuthority(_scope())

    scope_path, snapshot = asyncio.run(refresh_scope(tmp_path, authority))

    assert load_scope_target(tmp_path) == target
    assert authority.calls == [("frame-123", "space-456")]
    assert ScopeSnapshot.model_validate_json(scope_path.read_bytes()) == snapshot
    target_text = target_path.read_text(encoding="utf-8")
    assert "token" not in target_text.lower()
    assert "secret" not in target_text.lower()


def test_local_scope_requires_no_network_or_target(tmp_path: Path) -> None:
    path, snapshot = configure_local_scope(
        tmp_path,
        scope_id="task-123",
        title="Local task",
        status="in_progress",
    )

    assert snapshot.authority == "local"
    assert snapshot.scope_id == "task-123"
    assert snapshot.authority_ref == "local://scope/task-123"
    assert path.is_file()
    assert load_scope_target(tmp_path, required=False) is None


def test_failed_refresh_preserves_previous_scope(tmp_path: Path) -> None:
    configure_scope_target(
        tmp_path,
        frame_id="frame-123",
        space_id="space-456",
    )
    state = tmp_path / ".projectlore" / "scope.json"
    state.write_text(_scope().model_dump_json(), encoding="utf-8")
    before = state.read_bytes()

    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(
            refresh_scope(
                tmp_path,
                FakeScopeAuthority(error=RuntimeError("Fraimed unavailable")),
            )
        )

    assert state.read_bytes() == before
    assert not tuple(state.parent.glob("*.tmp"))


def test_initialization_adds_scope_hooks_and_preserves_existing_hooks(
    tmp_path: Path,
) -> None:
    custom = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "existing-hook"}]}
            ]
        }
    }
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps(custom),
        encoding="utf-8",
    )

    apply_initialization(
        initialization_previews(tmp_path, project_name="Lifecycle Test")
    )

    for path in (
        tmp_path / ".claude" / "settings.json",
        tmp_path / ".codex" / "hooks.json",
    ):
        value = json.loads(path.read_text(encoding="utf-8"))
        commands = [
            hook["command"]
            for entry in value["hooks"]["SessionStart"]
            for hook in entry["hooks"]
        ]
        assert "projectlore-scope-hook" in commands
    claude = json.loads(
        (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    commands = [
        hook["command"]
        for entry in claude["hooks"]["SessionStart"]
        for hook in entry["hooks"]
    ]
    assert "existing-hook" in commands


def test_scope_hook_is_noop_without_target_and_advisory_without_token(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment.pop("FRAIMED_API_TOKEN", None)
    event = json.dumps({"cwd": str(tmp_path)})

    no_target = subprocess.run(
        [sys.executable, "-m", "projectlore.scope_hook"],
        input=event,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    configure_scope_target(
        tmp_path,
        frame_id="frame-123",
        space_id="space-456",
    )
    no_token = subprocess.run(
        [sys.executable, "-m", "projectlore.scope_hook"],
        input=event,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )

    assert no_target.returncode == 0
    assert no_target.stdout == ""
    assert no_target.stderr == ""
    assert no_token.returncode == 0
    assert "FRAIMED_API_TOKEN is required" in no_token.stderr
    assert not (tmp_path / ".projectlore" / "scope.json").exists()

    apply_local_declaration(
        tmp_path,
        preview_local_declaration(
            tmp_path,
            WorkflowTarget(
                target_version="projectlore-workflow-target/1.0.0",
                project_id="lore:test/project",
                model_entrypoint="projectlore.yaml",
                provider_id="local",
                scope_id="local-work",
                container_id=None,
            ),
            title="Local",
            status="active",
        ),
    )
    configure_scope_target(
        tmp_path,
        frame_id="hidden-frame",
        space_id="hidden-space",
    )
    environment["FRAIMED_API_TOKEN"] = "must-not-be-used"
    canonical_wins = subprocess.run(
        [sys.executable, "-m", "projectlore.scope_hook"],
        input=event,
        text=True,
        capture_output=True,
        env=environment,
        timeout=5,
        check=False,
    )
    assert canonical_wins.returncode == 0
    assert canonical_wins.stdout == ""
    assert canonical_wins.stderr == ""


def test_source_gate_emits_scoped_pass_and_fail_evidence(tmp_path: Path) -> None:
    project = _project(tmp_path)
    service = ModelService(project / "projectlore.yaml")

    passed = evaluate_source_gate(
        project,
        service,
        ("pricing.py",),
        assurance_scope="local_advisory",
    )
    (project / "pricing.py").write_text(
        SOURCE.replace('Decimal("0.20")', 'Decimal("0.40")'),
        encoding="utf-8",
    )
    failed = evaluate_source_gate(
        project,
        service,
        ("pricing.py",),
        assurance_scope="ci_job_result",
    )

    assert passed.decision == "pass"
    assert source_gate_exit_code(passed) == 0
    assert passed.repository_certified is False
    assert passed.scope_receipt.obtained_via == "provided_snapshot"
    assert failed.decision == "fail"
    assert source_gate_exit_code(failed) == 1
    assert failed.repository_certified is False
    assert failed.assurance_scope == "ci_job_result"
    assert failed.evidence_id != passed.evidence_id


def test_timeless_source_gate_runs_without_workflow_provider(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    (project / ".projectlore" / "scope.json").unlink()

    result = evaluate_source_gate(
        project,
        ModelService(project / "projectlore.yaml"),
        ("pricing.py",),
        assurance_scope="local_advisory",
    )

    assert result.decision == "pass"
    assert result.scope_receipt is None


def test_source_gate_writes_valid_evidence_atomically(tmp_path: Path) -> None:
    project = _project(tmp_path)
    evidence = evaluate_source_gate(
        project,
        ModelService(project / "projectlore.yaml"),
        ("pricing.py",),
        assurance_scope="local_advisory",
    )
    output = project / ".projectlore" / "evidence" / "source-gate.json"

    write_source_gate_evidence(output, evidence)

    assert json.loads(output.read_text(encoding="utf-8"))["evidence_id"] == (
        evidence.evidence_id
    )
    assert not tuple(output.parent.glob("*.tmp"))


def test_source_gate_rejects_unconfigured_and_stale_source(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    service = ModelService(project / "projectlore.yaml")
    with pytest.raises(ValueError, match="not configured"):
        evaluate_source_gate(
            project,
            service,
            ("other.py",),
            assurance_scope="local_advisory",
        )

    result = evaluate_source_gate(
        project,
        service,
        ("pricing.py",),
        assurance_scope="local_advisory",
    )

    assert result.decision == "pass"
    assert source_gate_exit_code(result) == 0
    assert result.scope_receipt is not None


def test_source_gate_rejects_snapshot_from_previous_target(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    configure_scope_target(
        project,
        frame_id="different-frame",
        space_id="space-456",
    )

    with pytest.raises(ValueError, match="does not match"):
        evaluate_source_gate(
            project,
            ModelService(project / "projectlore.yaml"),
            ("pricing.py",),
            assurance_scope="local_advisory",
        )


def test_scope_status_explains_target_mismatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _project(tmp_path)
    configure_scope_target(
        project,
        frame_id="different-frame",
        space_id="space-456",
    )

    assert main(["scope", "status", "--root", str(project)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["scope"] is None
    assert "does not match" in result["scope_error"]
