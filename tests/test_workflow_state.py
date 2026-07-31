from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from projectlore.cli import main
from projectlore.scope import ScopeSnapshot
from projectlore.source_policy import load_scope_snapshot
from projectlore.workflow import (
    DeclaredWorkflowContext,
    ObservedWorkflowContext,
    WorkflowTarget,
    make_local_declaration,
    make_observation,
)
from projectlore.workflow_state import (
    CONTEXT_PATH,
    MAX_STATE_BYTES,
    apply_clear,
    apply_legacy_local_migration,
    apply_local_declaration,
    load_workflow_context,
    preview_clear,
    preview_legacy_local_migration,
    preview_local_declaration,
)


def _target() -> WorkflowTarget:
    return WorkflowTarget(
        target_version="projectlore-workflow-target/1.0.0",
        project_id="lore:test/project",
        model_entrypoint="projectlore.yaml",
        provider_id="local",
        scope_id="work-1",
        container_id=None,
    )


def test_local_declaration_is_preview_first_and_not_age_stale(tmp_path: Path) -> None:
    now = datetime(2026, 7, 31, tzinfo=UTC)
    preview = preview_local_declaration(
        tmp_path, _target(), title="Work", status="active"
    )
    assert not (tmp_path / CONTEXT_PATH).exists()
    assert preview.before_digest is None
    assert preview.after_digest is not None

    context = apply_local_declaration(tmp_path, preview)

    assert context.valid_at(now + timedelta(days=3650)) is True
    assert load_workflow_context(tmp_path) == context


def test_explicit_expiration_controls_local_validity(tmp_path: Path) -> None:
    expires = datetime(2026, 8, 1, tzinfo=UTC)
    context = make_local_declaration(
        _target(), title="Work", status="active", expires_at=expires
    )
    assert context.valid_at(expires) is True
    assert context.valid_at(expires + timedelta(microseconds=1)) is False


def test_external_observation_uses_age_freshness() -> None:
    target = _target().model_copy(
        update={"provider_id": "fake", "container_id": "workspace"}
    )
    observed = datetime(2026, 7, 31, tzinfo=UTC)
    context = ObservedWorkflowContext(
        context_version="projectlore-workflow-context/1.0.0",
        context_kind="observed",
        observation=make_observation(
            target,
            assurance="observed",
            title="Work",
            status="active",
            validation_open=0,
            observed_at=observed,
            authority_ref="fake://scope/work-1",
        ),
        maximum_age_seconds=300,
    )
    assert context.valid_at(observed + timedelta(seconds=300)) is True
    assert context.valid_at(observed + timedelta(seconds=301)) is False


def test_switch_to_local_removes_external_target_only_on_apply(tmp_path: Path) -> None:
    external = tmp_path / ".projectlore" / "scope-target.json"
    external.parent.mkdir()
    external.write_text("external", encoding="utf-8")
    preview = preview_local_declaration(
        tmp_path, _target(), title="Work", status="active"
    )
    assert preview.removes_external_target is True
    assert external.exists()

    apply_local_declaration(tmp_path, preview)

    assert not external.exists()


def test_clear_is_digest_bound_and_rejects_preview_apply_race(tmp_path: Path) -> None:
    context = apply_local_declaration(
        tmp_path,
        preview_local_declaration(
            tmp_path, _target(), title="Work", status="active"
        ),
    )
    preview = preview_clear(tmp_path, target_digest=context.content_digest)
    path = tmp_path / CONTEXT_PATH
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after preview"):
        apply_clear(tmp_path, preview)
    assert path.exists()


def test_clear_preview_is_non_mutating_and_apply_removes_exact_state(
    tmp_path: Path,
) -> None:
    context = apply_local_declaration(
        tmp_path,
        preview_local_declaration(
            tmp_path, _target(), title="Work", status="active"
        ),
    )
    preview = preview_clear(tmp_path, target_digest=context.content_digest)
    assert (tmp_path / CONTEXT_PATH).exists()

    apply_clear(tmp_path, preview)

    assert not (tmp_path / CONTEXT_PATH).exists()


def test_invalid_oversized_and_symlinked_state_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / CONTEXT_PATH
    path.parent.mkdir()
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid"):
        load_workflow_context(tmp_path)

    path.write_bytes(b"x" * (MAX_STATE_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        load_workflow_context(tmp_path)

    path.unlink()
    target = tmp_path / "outside.json"
    target.write_text("{}", encoding="utf-8")
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("Symbolic links are unavailable on this platform.")
    with pytest.raises(ValueError, match="symbolic link"):
        load_workflow_context(tmp_path)


def test_failed_replacement_preserves_previous_valid_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = apply_local_declaration(
        tmp_path,
        preview_local_declaration(
            tmp_path, _target(), title="First", status="active"
        ),
    )
    second = preview_local_declaration(
        tmp_path, _target(), title="Second", status="active"
    )
    original_replace = Path.replace

    def interrupt(self: Path, target: Path) -> Path:
        if self.name.endswith(".tmp"):
            raise KeyboardInterrupt
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", interrupt)
    with pytest.raises(KeyboardInterrupt):
        apply_local_declaration(tmp_path, second)

    restored = load_workflow_context(tmp_path)
    assert isinstance(restored, DeclaredWorkflowContext)
    assert restored.content_digest == first.content_digest


def test_cli_local_and_clear_are_preview_first(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = Path(__file__).resolve().parents[1] / "examples" / "homebrew.project.yaml"
    (tmp_path / "projectlore.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    arguments = [
        "scope",
        "local",
        "work-1",
        "--title",
        "Work",
        "--root",
        str(tmp_path),
    ]
    assert main(arguments) == 0
    assert '"applied": false' in capsys.readouterr().out
    assert not (tmp_path / CONTEXT_PATH).exists()

    assert main([*arguments, "--apply"]) == 0
    applied = capsys.readouterr().out
    assert '"applied": true' in applied
    context = load_workflow_context(tmp_path)
    assert isinstance(context, DeclaredWorkflowContext)

    clear = [
        "scope",
        "clear",
        "--target-digest",
        context.content_digest,
        "--root",
        str(tmp_path),
    ]
    assert main(clear) == 0
    assert (tmp_path / CONTEXT_PATH).exists()
    capsys.readouterr()
    assert main([*clear, "--apply"]) == 0
    assert not (tmp_path / CONTEXT_PATH).exists()


def test_legacy_local_migration_is_validated_atomic_and_idempotent(
    tmp_path: Path,
) -> None:
    legacy_path = tmp_path / ".projectlore" / "scope.json"
    legacy_path.parent.mkdir()
    observed = datetime(2026, 7, 31, tzinfo=UTC)
    legacy = ScopeSnapshot(
        authority="local",
        frame_id="work-1",
        frame_title="Legacy work",
        frame_status="active",
        validation_open=1,
        observed_at=observed,
        authority_ref="local://scope/work-1",
    )
    legacy_path.write_text(legacy.model_dump_json(), encoding="utf-8")

    migrated = apply_legacy_local_migration(
        tmp_path, preview_legacy_local_migration(tmp_path, _target())
    )
    again = apply_legacy_local_migration(
        tmp_path, preview_legacy_local_migration(tmp_path, _target())
    )

    assert migrated == again
    assert migrated.declared_at == observed
    assert not legacy_path.exists()


def test_policy_scope_loader_routes_canonical_declaration_through_provider(
    tmp_path: Path,
) -> None:
    declaration = apply_local_declaration(
        tmp_path,
        preview_local_declaration(
            tmp_path, _target(), title="Canonical", status="active"
        ),
    )

    projected = load_scope_snapshot(tmp_path)

    assert projected is not None
    assert projected.frame_id == declaration.scope_id
    assert projected.frame_title == declaration.title


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("project_id", "lore:other/project"),
        ("model_entrypoint", "other.yaml"),
        ("scope_id", "other-work"),
        ("title", "Tampered"),
        ("status", "tampered"),
        ("validation_open", 99),
        ("expires_at", "2030-01-01T00:00:00Z"),
        ("target_digest", "sha256:" + "f" * 64),
        ("content_digest", "sha256:" + "e" * 64),
    ),
)
def test_loaded_declaration_recomputes_identity_and_content_digests(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    apply_local_declaration(
        tmp_path,
        preview_local_declaration(
            tmp_path, _target(), title="Work", status="active"
        ),
    )
    path = tmp_path / CONTEXT_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid"):
        load_workflow_context(tmp_path)


def test_apply_binds_legacy_target_and_context_digests(tmp_path: Path) -> None:
    state = tmp_path / ".projectlore"
    state.mkdir()
    target = state / "scope-target.json"
    legacy = state / "scope.json"
    target.write_text("target-v1", encoding="utf-8")
    legacy.write_text("context-v1", encoding="utf-8")
    preview = preview_local_declaration(
        tmp_path, _target(), title="Work", status="active"
    )
    target.write_text("target-v2", encoding="utf-8")

    with pytest.raises(ValueError, match="Legacy workflow state changed"):
        apply_local_declaration(tmp_path, preview)
    assert not (tmp_path / CONTEXT_PATH).exists()
    assert legacy.exists()


def test_naive_local_timestamps_are_rejected() -> None:
    with pytest.raises(Exception, match="invalid response"):
        make_local_declaration(
            _target(),
            title="Work",
            status="active",
            declared_at=datetime(2026, 7, 31),
        )


def test_cli_migration_is_preview_first_and_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = Path(__file__).resolve().parents[1] / "examples" / "homebrew.project.yaml"
    (tmp_path / "projectlore.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    legacy_path = tmp_path / ".projectlore" / "scope.json"
    legacy_path.parent.mkdir()
    legacy_path.write_text(
        ScopeSnapshot(
            authority="local",
            frame_id="work-1",
            frame_title="Legacy",
            frame_status="active",
            validation_open=0,
            observed_at=datetime(2026, 7, 31, tzinfo=UTC),
            authority_ref="local://scope/work-1",
        ).model_dump_json(),
        encoding="utf-8",
    )
    command = ["scope", "migrate", "--root", str(tmp_path)]
    assert main(command) == 0
    assert '"applied": false' in capsys.readouterr().out
    assert legacy_path.exists()

    assert main([*command, "--apply"]) == 0
    assert '"applied": true' in capsys.readouterr().out
    assert not legacy_path.exists()
    assert isinstance(load_workflow_context(tmp_path), DeclaredWorkflowContext)

    assert main(command) == 0
    assert '"applied": false' in capsys.readouterr().out


@pytest.mark.parametrize("payload", (b"{", b"null", b"[]"))
def test_migration_rejects_corrupt_or_truncated_legacy_state(
    tmp_path: Path,
    payload: bytes,
) -> None:
    path = tmp_path / ".projectlore" / "scope.json"
    path.parent.mkdir()
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="invalid"):
        preview_legacy_local_migration(tmp_path, _target())


def test_migration_rejects_oversized_and_external_legacy_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".projectlore" / "scope.json"
    path.parent.mkdir()
    path.write_bytes(b"x" * (MAX_STATE_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        preview_legacy_local_migration(tmp_path, _target())

    path.write_text(
        ScopeSnapshot(
            authority="fraimed",
            frame_id="work-1",
            frame_title="External",
            frame_status="active",
            validation_open=0,
            observed_at=datetime(2026, 7, 31, tzinfo=UTC),
            authority_ref="fraimed://frame/work-1",
        ).model_dump_json(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Only legacy local"):
        preview_legacy_local_migration(tmp_path, _target())


def test_interrupted_migration_preserves_legacy_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / ".projectlore" / "scope.json"
    path.parent.mkdir()
    path.write_text(
        ScopeSnapshot(
            authority="local",
            frame_id="work-1",
            frame_title="Legacy",
            frame_status="active",
            validation_open=0,
            observed_at=datetime(2026, 7, 31, tzinfo=UTC),
            authority_ref="local://scope/work-1",
        ).model_dump_json(),
        encoding="utf-8",
    )
    preview = preview_legacy_local_migration(tmp_path, _target())

    def interrupt(self: Path, target: Path) -> Path:
        raise KeyboardInterrupt

    monkeypatch.setattr(Path, "replace", interrupt)
    with pytest.raises(KeyboardInterrupt):
        apply_legacy_local_migration(tmp_path, preview)
    assert path.exists()
    assert not (tmp_path / CONTEXT_PATH).exists()


def test_post_activation_migration_interruption_cleans_up_on_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / ".projectlore"
    state.mkdir()
    legacy_context = state / "scope.json"
    legacy_target = state / "scope-target.json"
    legacy_context.write_text(
        ScopeSnapshot(
            authority="local",
            frame_id="work-1",
            frame_title="Legacy",
            frame_status="active",
            validation_open=0,
            observed_at=datetime(2026, 7, 31, tzinfo=UTC),
            authority_ref="local://scope/work-1",
        ).model_dump_json(),
        encoding="utf-8",
    )
    legacy_target.write_text("legacy-target", encoding="utf-8")
    preview = preview_legacy_local_migration(tmp_path, _target())
    original_unlink = Path.unlink
    interrupted = False

    def interrupt_once(self: Path, missing_ok: bool = False) -> None:
        nonlocal interrupted
        if self == legacy_target and not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", interrupt_once)
    with pytest.raises(KeyboardInterrupt):
        apply_legacy_local_migration(tmp_path, preview)
    assert (tmp_path / CONTEXT_PATH).exists()
    assert legacy_target.exists()

    monkeypatch.setattr(Path, "unlink", original_unlink)
    retry = preview_legacy_local_migration(tmp_path, _target())
    apply_legacy_local_migration(tmp_path, retry)

    assert not legacy_target.exists()
    assert not legacy_context.exists()


def test_intermediate_symlink_and_symlinked_migration_are_rejected(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    state = tmp_path / ".projectlore"
    try:
        state.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links are unavailable on this platform.")
    with pytest.raises(ValueError, match="symbolic links"):
        preview_local_declaration(
            tmp_path, _target(), title="Work", status="active"
        )

    state.unlink()
    state.mkdir()
    legacy = state / "scope.json"
    source = tmp_path / "legacy.json"
    source.write_text("{}", encoding="utf-8")
    legacy.symlink_to(source)
    with pytest.raises(ValueError, match="symbolic links"):
        preview_legacy_local_migration(tmp_path, _target())
