"""Crash-safe local persistence for provider-neutral workflow context."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from projectlore.scope import ScopeSnapshot
from projectlore.workflow import (
    WORKFLOW_CONTEXT_ADAPTER,
    DeclaredWorkflowContext,
    WorkflowContext,
    WorkflowTarget,
    make_local_declaration,
)

CONTEXT_PATH = Path(".projectlore/workflow-context.json")
LEGACY_TARGET_PATH = Path(".projectlore/scope-target.json")
LEGACY_CONTEXT_PATH = Path(".projectlore/scope.json")
MAX_STATE_BYTES = 16 * 1024


@dataclass(frozen=True)
class WorkflowStatePreview:
    operation: str
    path: Path
    before_digest: str | None
    after_digest: str | None
    target_digest: str
    removes_external_target: bool
    legacy_target_digest: str | None
    legacy_context_digest: str | None
    content: str | None


def preview_local_declaration(
    root: Path,
    target: WorkflowTarget,
    *,
    title: str,
    status: str,
    expires_at: datetime | None = None,
) -> WorkflowStatePreview:
    context = make_local_declaration(
        target,
        title=title,
        status=status,
        expires_at=expires_at,
    )
    path = _state_path(root, CONTEXT_PATH)
    content = f"{context.model_dump_json(indent=2)}\n"
    return WorkflowStatePreview(
        operation="set_local",
        path=path,
        before_digest=_file_digest(path),
        after_digest=_bytes_digest(content.encode()),
        target_digest=context.content_digest,
        removes_external_target=_state_path(root, LEGACY_TARGET_PATH).is_file(),
        legacy_target_digest=_file_digest(_state_path(root, LEGACY_TARGET_PATH)),
        legacy_context_digest=_file_digest(_state_path(root, LEGACY_CONTEXT_PATH)),
        content=content,
    )


def apply_local_declaration(
    root: Path,
    preview: WorkflowStatePreview,
) -> DeclaredWorkflowContext:
    if preview.operation != "set_local" or preview.content is None:
        raise ValueError("Local declaration preview is invalid.")
    path = _state_path(root, CONTEXT_PATH)
    if path != preview.path or _file_digest(path) != preview.before_digest:
        raise ValueError("Workflow state changed after preview; preview again.")
    _validate_legacy_digests(root, preview)
    _atomic_write(path, preview.content)
    context = load_workflow_context(root)
    if not isinstance(context, DeclaredWorkflowContext):
        raise ValueError("Written workflow declaration did not validate.")
    _state_path(root, LEGACY_TARGET_PATH).unlink(missing_ok=True)
    _state_path(root, LEGACY_CONTEXT_PATH).unlink(missing_ok=True)
    return context


def preview_clear(root: Path, *, target_digest: str) -> WorkflowStatePreview:
    path = _state_path(root, CONTEXT_PATH)
    context = load_workflow_context(root)
    actual = (
        context.content_digest
        if isinstance(context, DeclaredWorkflowContext)
        else context.observation.content_digest
    )
    if actual != target_digest:
        raise ValueError("Workflow context digest does not match --target-digest.")
    return WorkflowStatePreview(
        operation="clear",
        path=path,
        before_digest=_file_digest(path),
        after_digest=None,
        target_digest=target_digest,
        removes_external_target=_state_path(root, LEGACY_TARGET_PATH).is_file(),
        legacy_target_digest=_file_digest(_state_path(root, LEGACY_TARGET_PATH)),
        legacy_context_digest=_file_digest(_state_path(root, LEGACY_CONTEXT_PATH)),
        content=None,
    )


def apply_clear(root: Path, preview: WorkflowStatePreview) -> None:
    if preview.operation != "clear":
        raise ValueError("Clear preview is invalid.")
    path = _state_path(root, CONTEXT_PATH)
    if path != preview.path or _file_digest(path) != preview.before_digest:
        raise ValueError("Workflow state changed after preview; preview again.")
    _validate_legacy_digests(root, preview)
    context = load_workflow_context(root)
    actual = (
        context.content_digest
        if isinstance(context, DeclaredWorkflowContext)
        else context.observation.content_digest
    )
    if actual != preview.target_digest:
        raise ValueError("Workflow context changed after preview; nothing cleared.")
    # Canonical context remains authoritative until every legacy refresh input
    # is gone. An interruption therefore leaves a valid canonical state.
    _state_path(root, LEGACY_TARGET_PATH).unlink(missing_ok=True)
    _state_path(root, LEGACY_CONTEXT_PATH).unlink(missing_ok=True)
    path.unlink()


def load_workflow_context(root: Path) -> WorkflowContext:
    path = _state_path(root, CONTEXT_PATH)
    if not path.is_file():
        raise ValueError("Workflow context is not configured.")
    if path.is_symlink():
        raise ValueError("Workflow context cannot be a symbolic link.")
    raw = path.read_bytes()
    if len(raw) > MAX_STATE_BYTES:
        raise ValueError("Workflow context exceeds 16 KiB.")
    try:
        return WORKFLOW_CONTEXT_ADAPTER.validate_json(raw)
    except ValidationError as error:
        raise ValueError(f"Workflow context is invalid: {error}") from error


def preview_legacy_local_migration(
    root: Path,
    target: WorkflowTarget,
) -> WorkflowStatePreview:
    """Preview a bounded migration without changing either representation."""
    current_path = _state_path(root, CONTEXT_PATH)
    if current_path.is_file():
        current = load_workflow_context(root)
        if not isinstance(current, DeclaredWorkflowContext):
            raise ValueError("Cannot downgrade observed workflow context to local.")
        if current.target_digest != target.digest:
            raise ValueError(
                "Existing workflow context targets another project or scope."
            )
        return WorkflowStatePreview(
            operation="migrate_local",
            path=current_path,
            before_digest=_file_digest(current_path),
            after_digest=_file_digest(current_path),
            target_digest=current.content_digest,
            removes_external_target=_state_path(
                root, LEGACY_TARGET_PATH
            ).is_file(),
            legacy_target_digest=_file_digest(
                _state_path(root, LEGACY_TARGET_PATH)
            ),
            legacy_context_digest=_file_digest(
                _state_path(root, LEGACY_CONTEXT_PATH)
            ),
            content=f"{current.model_dump_json(indent=2)}\n",
        )
    legacy_path = _state_path(root, LEGACY_CONTEXT_PATH)
    legacy = _load_legacy_local(legacy_path, target)
    context = make_local_declaration(
        target,
        title=legacy.frame_title,
        status=legacy.frame_status,
        validation_open=legacy.validation_open,
        declared_at=legacy.observed_at,
    )
    content = f"{context.model_dump_json(indent=2)}\n"
    return WorkflowStatePreview(
        operation="migrate_local",
        path=current_path,
        before_digest=None,
        after_digest=_bytes_digest(content.encode()),
        target_digest=context.content_digest,
        removes_external_target=_state_path(root, LEGACY_TARGET_PATH).is_file(),
        legacy_target_digest=_file_digest(_state_path(root, LEGACY_TARGET_PATH)),
        legacy_context_digest=_file_digest(legacy_path),
        content=content,
    )


def apply_legacy_local_migration(
    root: Path,
    preview: WorkflowStatePreview,
) -> DeclaredWorkflowContext:
    if preview.operation != "migrate_local" or preview.content is None:
        raise ValueError("Migration preview is invalid.")
    path = _state_path(root, CONTEXT_PATH)
    if _file_digest(path) != preview.before_digest:
        raise ValueError("Workflow state changed after preview; preview again.")
    _validate_legacy_digests(root, preview)
    if path.is_file():
        current = load_workflow_context(root)
        if not isinstance(current, DeclaredWorkflowContext):
            raise ValueError("Cannot downgrade observed workflow context to local.")
        # Canonical state remains authoritative while cleanup finishes. This
        # makes a retry complete an interruption after activation.
        _state_path(root, LEGACY_TARGET_PATH).unlink(missing_ok=True)
        _state_path(root, LEGACY_CONTEXT_PATH).unlink(missing_ok=True)
        return current
    validated = WORKFLOW_CONTEXT_ADAPTER.validate_json(preview.content)
    if not isinstance(validated, DeclaredWorkflowContext):
        raise ValueError("Migrated workflow context has the wrong variant.")
    _atomic_write(path, preview.content)
    _state_path(root, LEGACY_TARGET_PATH).unlink(missing_ok=True)
    _state_path(root, LEGACY_CONTEXT_PATH).unlink(missing_ok=True)
    return validated


def _load_legacy_local(path: Path, target: WorkflowTarget) -> ScopeSnapshot:
    if not path.is_file():
        raise ValueError("No legacy local workflow context is available to migrate.")
    if path.is_symlink():
        raise ValueError("Legacy workflow context cannot be a symbolic link.")
    raw = path.read_bytes()
    if len(raw) > MAX_STATE_BYTES:
        raise ValueError("Legacy workflow context exceeds 16 KiB.")
    try:
        legacy = ScopeSnapshot.model_validate_json(raw)
    except ValidationError as error:
        raise ValueError(f"Legacy workflow context is invalid: {error}") from error
    if legacy.authority != "local":
        raise ValueError("Only legacy local declarations can be migrated offline.")
    if legacy.frame_id != target.scope_id:
        raise ValueError("Legacy workflow context does not match the migration target.")
    return legacy


def _validate_legacy_digests(
    root: Path,
    preview: WorkflowStatePreview,
) -> None:
    if _file_digest(_state_path(root, LEGACY_TARGET_PATH)) != (
        preview.legacy_target_digest
    ) or _file_digest(_state_path(root, LEGACY_CONTEXT_PATH)) != (
        preview.legacy_context_digest
    ):
        raise ValueError("Legacy workflow state changed after preview; preview again.")


def _state_path(root: Path, relative: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    candidate = resolved_root / relative
    cursor = resolved_root
    for part in relative.parts:
        cursor /= part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError("Workflow context path cannot contain symbolic links.")
    path = candidate.resolve(strict=False)
    if not path.is_relative_to(resolved_root):
        raise ValueError("Workflow state path escapes the project root.")
    return path


def _atomic_write(path: Path, content: str) -> None:
    payload = content.encode("utf-8")
    if len(payload) > MAX_STATE_BYTES:
        raise ValueError("Workflow context exceeds 16 KiB.")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    if path.is_symlink():
        raise ValueError("Workflow context cannot be a symbolic link.")
    return _bytes_digest(path.read_bytes())


def _bytes_digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"
