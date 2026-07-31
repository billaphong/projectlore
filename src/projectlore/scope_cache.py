"""Explicit local targeting and atomic refresh of Fraimed workflow scope."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field, ValidationError

from projectlore.fraimed import FraimedScopeAuthority, ScopeAuthority
from projectlore.models import StrictModel
from projectlore.scope import ScopeSnapshot

SCOPE_TARGET_PATH = Path(".projectlore/scope-target.json")
SCOPE_SNAPSHOT_PATH = Path(".projectlore/scope.json")
MAX_SCOPE_STATE_BYTES = 16 * 1024
DEFAULT_FRAIMED_MCP_URL = "https://www.fraimed.ai/api/mcp"


class ScopeTarget(StrictModel):
    target_version: str = Field(pattern=r"^scope-target/0\.1\.0$")
    frame_id: str = Field(min_length=1, max_length=256)
    space_id: str = Field(min_length=1, max_length=256)


def configure_scope_target(
    root: Path,
    *,
    frame_id: str,
    space_id: str,
) -> tuple[Path, ScopeTarget]:
    """Atomically configure non-secret local workflow identity."""
    target = ScopeTarget(
        target_version="scope-target/0.1.0",
        frame_id=frame_id,
        space_id=space_id,
    )
    path = _fixed_path(root, SCOPE_TARGET_PATH)
    _atomic_write(path, f"{target.model_dump_json(indent=2)}\n")
    return path, target


def load_scope_target(root: Path, *, required: bool = True) -> ScopeTarget | None:
    path = _fixed_path(root, SCOPE_TARGET_PATH)
    if not path.is_file():
        if required:
            raise ValueError(
                "Scope target is not configured; run "
                "'lore scope target FRAME_ID SPACE_ID'."
            )
        return None
    raw = path.read_bytes()
    if len(raw) > MAX_SCOPE_STATE_BYTES:
        raise ValueError("Scope target exceeds 16 KiB.")
    try:
        return ScopeTarget.model_validate_json(raw)
    except ValidationError as error:
        raise ValueError(f"Scope target is invalid: {error}") from error


async def refresh_scope(
    root: Path,
    authority: ScopeAuthority,
) -> tuple[Path, ScopeSnapshot]:
    """Fetch target scope and atomically activate it only after validation."""
    target = load_scope_target(root)
    assert target is not None
    snapshot = await authority.current_scope(target.frame_id, target.space_id)
    if snapshot.frame_id != target.frame_id:
        raise ValueError("Fraimed returned a different Frame than the target.")
    path = _fixed_path(root, SCOPE_SNAPSHOT_PATH)
    _atomic_write(path, f"{snapshot.model_dump_json(indent=2)}\n")
    return path, snapshot


async def refresh_scope_from_environment(
    root: Path,
) -> tuple[Path, ScopeSnapshot]:
    """Refresh through HTTPS Fraimed MCP using an environment-only token."""
    token = os.environ.get("FRAIMED_API_TOKEN", "")
    if not token:
        raise ValueError("FRAIMED_API_TOKEN is required to refresh scope.")
    url = os.environ.get("PROJECTLORE_FRAIMED_MCP_URL", DEFAULT_FRAIMED_MCP_URL)
    authority = FraimedScopeAuthority(url, token)
    return await refresh_scope(root, authority)


def configure_local_scope(
    root: Path,
    *,
    scope_id: str,
    title: str,
    status: str,
) -> tuple[Path, ScopeSnapshot]:
    """Atomically activate standalone local workflow context."""
    snapshot = ScopeSnapshot(
        authority="local",
        frame_id=scope_id,
        frame_title=title,
        frame_status=status,
        validation_open=0,
        observed_at=datetime.now(UTC),
        authority_ref=f"local://scope/{scope_id}",
    )
    path = _fixed_path(root, SCOPE_SNAPSHOT_PATH)
    _atomic_write(path, f"{snapshot.model_dump_json(indent=2)}\n")
    _fixed_path(root, SCOPE_TARGET_PATH).unlink(missing_ok=True)
    return path, snapshot


def _fixed_path(root: Path, relative: Path) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ValueError(f"ProjectLore state path escapes project root: {relative}")
    return path


def _atomic_write(path: Path, content: str) -> None:
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_SCOPE_STATE_BYTES:
        raise ValueError("Scope state exceeds 16 KiB.")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
