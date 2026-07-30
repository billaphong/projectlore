"""Validated request-driven refresh with atomic last-valid activation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal, cast

from projectlore.service import InvalidModelError, ModelService


@dataclass(frozen=True)
class RefreshSnapshot:
    """One atomic view of the active service and latest refresh attempt."""

    service: ModelService
    state: Literal["current", "last_valid"]
    attempted_at: datetime
    diagnostics: tuple[dict[str, object], ...]

    def decorate(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(payload)
        freshness = dict(result.get("freshness", {}))
        freshness.update(
            {
                "refresh_state": self.state,
                "refresh_attempted_at": self.attempted_at.isoformat(),
                "refresh_diagnostics": list(self.diagnostics),
            }
        )
        result["freshness"] = freshness
        return result


class RefreshingModelService:
    """Poll canonical files at request boundaries and retain the last valid model."""

    def __init__(self, model_path: Path) -> None:
        self._path = model_path.resolve()
        self._lock = RLock()
        self._active = ModelService(self._path)

    def refresh(self) -> RefreshSnapshot:
        attempted_at = datetime.now(UTC)
        with self._lock:
            try:
                candidate = ModelService(self._path)
            except InvalidModelError as error:
                raw_diagnostics = cast(
                    list[dict[str, object]],
                    error.report.to_dict()["diagnostics"],
                )
                diagnostics = tuple(
                    item
                    for item in raw_diagnostics
                    if isinstance(item, dict)
                )
                return RefreshSnapshot(
                    service=self._active,
                    state="last_valid",
                    attempted_at=attempted_at,
                    diagnostics=diagnostics,
                )
            self._active = candidate
            return RefreshSnapshot(
                service=candidate,
                state="current",
                attempted_at=attempted_at,
                diagnostics=(),
            )
