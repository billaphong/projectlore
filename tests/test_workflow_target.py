from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from projectlore.cli import main
from projectlore.scope import ScopeSnapshot
from projectlore.source_policy import load_scope_snapshot
from projectlore.workflow import (
    ObservedWorkflowContext,
    WorkflowTarget,
    make_observation,
)
from projectlore.workflow_state import (
    apply_local_declaration,
    preview_local_declaration,
    write_observed_context,
)
from projectlore.workflow_target import (
    configure_workflow_target,
    load_workflow_target,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"


def _target() -> WorkflowTarget:
    return WorkflowTarget(
        target_version="projectlore-workflow-target/1.0.0",
        project_id="lore:test/project",
        model_entrypoint="projectlore.yaml",
        provider_id="fake",
        scope_id="work",
        container_id="workspace",
    )


def test_target_round_trip_and_link_rejection(tmp_path: Path) -> None:
    path = configure_workflow_target(tmp_path, _target())
    assert load_workflow_target(tmp_path) == _target()
    path.unlink()
    destination = tmp_path / "target.json"
    destination.write_text("{}", encoding="utf-8")
    try:
        path.symlink_to(destination)
    except OSError:
        pytest.skip("Symbolic links are unavailable on this platform.")
    with pytest.raises(ValueError, match="symbolic links"):
        load_workflow_target(tmp_path)


def test_target_rejects_symlinked_state_directory(tmp_path: Path) -> None:
    destination = tmp_path / "state"
    destination.mkdir()
    try:
        (tmp_path / ".projectlore").symlink_to(destination, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links are unavailable on this platform.")
    with pytest.raises(ValueError, match="symbolic links"):
        configure_workflow_target(tmp_path, _target())


def test_external_target_requires_preview_apply_and_cannot_overlap_local(
    tmp_path: Path,
) -> None:
    model = tmp_path / "projectlore.yaml"
    model.write_text(MODEL.read_text(encoding="utf-8"), encoding="utf-8")
    preview = [
        "scope",
        "target",
        "work",
        "workspace",
        "--provider",
        "fraimed",
        "--root",
        str(tmp_path),
    ]
    assert main(preview) == 0
    assert load_workflow_target(tmp_path) is None
    assert main([*preview, "--apply"]) == 0
    target = load_workflow_target(tmp_path, required=True)
    assert target is not None and target.provider_id == "fraimed"

    (tmp_path / ".projectlore" / "workflow-target.json").unlink()
    local_target = target.model_copy(
        update={"provider_id": "local", "container_id": None}
    )
    apply_local_declaration(
        tmp_path,
        preview_local_declaration(
            tmp_path, local_target, title="Local", status="active"
        ),
    )
    with pytest.raises(SystemExit):
        main([*preview, "--apply"])
    assert load_workflow_target(tmp_path) is None


def test_changed_target_rejects_snapshot_from_previous_generation(
    tmp_path: Path,
) -> None:
    first = _target()
    configure_workflow_target(tmp_path, first)
    snapshot = ScopeSnapshot(
        authority="fake",
        frame_id=first.scope_id,
        frame_title="First",
        frame_status="active",
        validation_open=0,
        observed_at=datetime.now(UTC),
        authority_ref="fake://scope/work",
    )
    state = tmp_path / ".projectlore"
    (state / "scope.json").write_text(
        snapshot.model_dump_json(), encoding="utf-8"
    )
    observation = make_observation(
        first,
        assurance="observed",
        title=snapshot.frame_title,
        status=snapshot.frame_status,
        validation_open=snapshot.validation_open,
        observed_at=snapshot.observed_at,
        authority_ref=snapshot.authority_ref,
    )
    write_observed_context(
        tmp_path,
        ObservedWorkflowContext(
            context_version="projectlore-workflow-context/1.0.0",
            context_kind="observed",
            observation=observation,
            maximum_age_seconds=300,
        ),
    )
    assert load_scope_snapshot(tmp_path) == snapshot

    configure_workflow_target(
        tmp_path, first.model_copy(update={"container_id": "different-workspace"})
    )
    with pytest.raises(ValueError, match="configured target"):
        load_scope_snapshot(tmp_path)

    (state / "workflow-context.json").unlink()
    with pytest.raises(ValueError, match="target-bound observation"):
        load_scope_snapshot(tmp_path)
