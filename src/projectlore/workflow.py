"""Provider-neutral workflow scope contracts and local provider."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from projectlore.scope import ScopeSnapshot


class WorkflowScopeProvider(Protocol):
    """Read-only provider for current workflow authorization context."""

    async def current_scope(
        self,
        scope_id: str,
        container_id: str | None = None,
    ) -> ScopeSnapshot: ...


class LocalScopeProvider:
    """Read a strict local workflow scope without network access."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def current_scope(
        self,
        scope_id: str,
        container_id: str | None = None,
    ) -> ScopeSnapshot:
        del container_id
        try:
            snapshot = ScopeSnapshot.model_validate_json(self._path.read_bytes())
        except OSError as error:
            raise RuntimeError(
                f"Local workflow scope is unavailable: {error}"
            ) from error
        if snapshot.scope_id != scope_id:
            raise RuntimeError("Local workflow scope does not match the target.")
        return snapshot
