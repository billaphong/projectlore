"""Fresh evidence that a policy decision used authoritative workflow scope."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field

from projectlore.models import StrictModel


class ScopeSnapshot(StrictModel):
    authority: Literal["fraimed"]
    frame_id: str = Field(min_length=1)
    frame_title: str = Field(min_length=1)
    frame_status: str = Field(min_length=1)
    validation_open: int = Field(ge=0)
    observed_at: datetime = Field(strict=False)
    authority_ref: str = Field(pattern=r"^fraimed://frame/")
    confirmed_scope_version: int | None = Field(default=None, ge=1)
    closure_generation: int | None = Field(default=None, ge=0)


class ScopeReceipt(StrictModel):
    receipt_version: Literal["scope-receipt/0.1.0"]
    authority: Literal["fraimed"]
    frame_id: str
    authority_ref: str
    observed_at: datetime
    evaluated_at: datetime
    age_seconds: float = Field(ge=0)
    scope_digest: str = Field(pattern=r"^sha256:")
    fresh: bool
    claim: Literal["scope_observed"]
    obtained_via: Literal["fraimed_mcp", "provided_snapshot"]
    confirmed_scope_version: int | None = None
    closure_generation: int | None = None
    maximum_age_seconds: int = Field(ge=1)

def issue_scope_receipt(
    snapshot: ScopeSnapshot,
    *,
    now: datetime | None = None,
    maximum_age_seconds: int = 300,
    obtained_via: Literal["fraimed_mcp", "provided_snapshot"] = "provided_snapshot",
) -> ScopeReceipt:
    evaluated_at = now or datetime.now(UTC)
    observed_at = snapshot.observed_at
    if observed_at.tzinfo is None:
        raise ValueError("Fraimed scope observed_at must include a timezone.")
    age = (evaluated_at - observed_at.astimezone(UTC)).total_seconds()
    fresh = 0 <= age <= maximum_age_seconds
    content: dict[str, Any] = snapshot.model_dump(mode="json")
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    return ScopeReceipt(
        receipt_version="scope-receipt/0.1.0",
        authority="fraimed",
        frame_id=snapshot.frame_id,
        authority_ref=snapshot.authority_ref,
        observed_at=observed_at,
        evaluated_at=evaluated_at,
        age_seconds=age,
        scope_digest=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        fresh=fresh,
        claim="scope_observed",
        obtained_via=obtained_via,
        confirmed_scope_version=snapshot.confirmed_scope_version,
        closure_generation=snapshot.closure_generation,
        maximum_age_seconds=maximum_age_seconds,
    )
