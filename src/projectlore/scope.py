"""Fresh evidence that a policy decision used authoritative workflow scope."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScopeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    authority: Literal["fraimed"]
    frame_id: str = Field(min_length=1)
    frame_title: str = Field(min_length=1)
    frame_status: str = Field(min_length=1)
    validation_open: int = Field(ge=0)
    observed_at: datetime = Field(strict=False)
    authority_ref: str = Field(pattern=r"^fraimed://frame/")


class ScopeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

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

    @model_validator(mode="after")
    def receipt_is_fresh(self) -> ScopeReceipt:
        if not self.fresh:
            raise ValueError("Fraimed scope snapshot is stale.")
        return self


def issue_scope_receipt(
    snapshot: ScopeSnapshot,
    *,
    now: datetime | None = None,
    maximum_age_seconds: int = 300,
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
    )
