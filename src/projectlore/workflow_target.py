"""Provider-neutral, project-bound workflow target configuration."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from projectlore.workflow import WorkflowTarget

TARGET_PATH = Path(".projectlore/workflow-target.json")
MAX_TARGET_BYTES = 16 * 1024


def configure_workflow_target(root: Path, target: WorkflowTarget) -> Path:
    path = _target_path(root)
    content = f"{target.model_dump_json(indent=2)}\n".encode()
    if len(content) > MAX_TARGET_BYTES:
        raise ValueError("Workflow target exceeds 16 KiB.")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def load_workflow_target(
    root: Path, *, required: bool = False
) -> WorkflowTarget | None:
    path = _target_path(root)
    if not path.is_file():
        if required:
            raise ValueError("Workflow target is not configured.")
        return None
    raw = path.read_bytes()
    if len(raw) > MAX_TARGET_BYTES:
        raise ValueError("Workflow target exceeds 16 KiB.")
    try:
        return WorkflowTarget.model_validate_json(raw)
    except ValidationError as error:
        raise ValueError(f"Workflow target is invalid: {error}") from error


def clear_workflow_target(root: Path) -> None:
    _target_path(root).unlink(missing_ok=True)


def _target_path(root: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    cursor = resolved_root
    for part in TARGET_PATH.parts:
        cursor /= part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError("Workflow target path cannot contain symbolic links.")
    path = (resolved_root / TARGET_PATH).resolve(strict=False)
    if not path.is_relative_to(resolved_root):
        raise ValueError("Workflow target path escapes project root.")
    return path
