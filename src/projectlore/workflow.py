"""Provider-neutral workflow context contracts.

This module is the dependency boundary between ProjectLore core behavior and
optional workflow systems. It intentionally imports no provider adapter.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from pydantic import Field, TypeAdapter, model_validator

from projectlore.models import StrictModel

WorkflowAssurance = Literal["declared", "observed"]


class WorkflowTarget(StrictModel):
    """Operator-configured identity for one provider lookup."""

    target_version: Literal["projectlore-workflow-target/1.0.0"]
    project_id: str = Field(min_length=1, max_length=256)
    model_entrypoint: str = Field(min_length=1, max_length=1024)
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    scope_id: str = Field(min_length=1, max_length=256)
    container_id: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def entrypoint_is_relative(self) -> WorkflowTarget:
        entrypoint = Path(self.model_entrypoint)
        if entrypoint.is_absolute() or ".." in entrypoint.parts:
            raise ValueError("model_entrypoint must be root-relative without '..'.")
        return self

    @property
    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class WorkflowObservation(StrictModel):
    """Bounded provider response bound to its configured target."""

    observation_version: Literal["projectlore-workflow-observation/1.0.0"]
    project_id: str
    model_entrypoint: str
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    scope_id: str
    container_id: str | None
    target_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    assurance: WorkflowAssurance
    title: str = Field(min_length=1)
    status: str = Field(min_length=1)
    validation_open: int = Field(ge=0)
    observed_at: datetime = Field(strict=False)
    authority_ref: str = Field(pattern=r"^[a-z][a-z0-9+.-]*://")
    provider_revision: str | None = None
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def digests_and_time_are_valid(self) -> WorkflowObservation:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must include a timezone.")
        target = WorkflowTarget(
            target_version="projectlore-workflow-target/1.0.0",
            project_id=self.project_id,
            model_entrypoint=self.model_entrypoint,
            provider_id=self.provider_id,
            scope_id=self.scope_id,
            container_id=self.container_id,
        )
        if self.target_digest != target.digest:
            raise ValueError("target_digest does not match observation identity.")
        content = {
            "project_id": self.project_id,
            "model_entrypoint": self.model_entrypoint,
            "provider_id": self.provider_id,
            "scope_id": self.scope_id,
            "container_id": self.container_id,
            "assurance": self.assurance,
            "title": self.title,
            "status": self.status,
            "validation_open": self.validation_open,
            "observed_at": self.observed_at.isoformat(),
            "authority_ref": self.authority_ref,
            "provider_revision": self.provider_revision,
        }
        if self.content_digest != _digest(content):
            raise ValueError("content_digest does not match observation content.")
        return self

    def validate_target(self, target: WorkflowTarget) -> None:
        expected = (
            target.project_id,
            target.model_entrypoint,
            target.provider_id,
            target.scope_id,
            target.container_id,
            target.digest,
        )
        actual = (
            self.project_id,
            self.model_entrypoint,
            self.provider_id,
            self.scope_id,
            self.container_id,
            self.target_digest,
        )
        if actual != expected:
            raise WorkflowTargetMismatch()


class WorkflowReceipt(StrictModel):
    """Evidence that evaluation consumed one target-bound observation."""

    receipt_version: Literal["projectlore-workflow-receipt/1.0.0"]
    project_id: str
    model_entrypoint: str
    model_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_id: str
    scope_id: str
    container_id: str | None
    target_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observation_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    assurance: WorkflowAssurance
    authority_ref: str = Field(pattern=r"^[a-z][a-z0-9+.-]*://")
    observed_at: datetime
    evaluated_at: datetime
    age_seconds: float = Field(ge=0)
    fresh: bool
    maximum_age_seconds: int = Field(ge=1)


class DeclaredWorkflowContext(StrictModel):
    """Durable local operator declaration; wall-clock age is not freshness."""

    context_version: Literal["projectlore-workflow-context/1.0.0"]
    context_kind: Literal["declared"]
    project_id: str
    model_entrypoint: str
    provider_id: Literal["local"]
    scope_id: str
    container_id: None = None
    target_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    title: str = Field(min_length=1)
    status: str = Field(min_length=1)
    validation_open: int = Field(ge=0)
    declared_at: datetime = Field(strict=False)
    expires_at: datetime | None = Field(default=None, strict=False)
    declared_by: Literal["operator"] = "operator"
    authority_ref: str = Field(pattern=r"^local://")
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def identity_content_and_time_are_valid(self) -> DeclaredWorkflowContext:
        if self.declared_at.tzinfo is None:
            raise ValueError("declared_at must include a timezone.")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must include a timezone.")
        target = WorkflowTarget(
            target_version="projectlore-workflow-target/1.0.0",
            project_id=self.project_id,
            model_entrypoint=self.model_entrypoint,
            provider_id=self.provider_id,
            scope_id=self.scope_id,
            container_id=self.container_id,
        )
        if self.target_digest != target.digest:
            raise ValueError("target_digest does not match declaration identity.")
        content = {
            "project_id": self.project_id,
            "model_entrypoint": self.model_entrypoint,
            "provider_id": self.provider_id,
            "scope_id": self.scope_id,
            "container_id": self.container_id,
            "target_digest": self.target_digest,
            "title": self.title,
            "status": self.status,
            "validation_open": self.validation_open,
            "declared_at": self.declared_at.isoformat(),
            "expires_at": (
                self.expires_at.isoformat() if self.expires_at is not None else None
            ),
            "declared_by": self.declared_by,
            "authority_ref": self.authority_ref,
        }
        if self.content_digest != _digest(content):
            raise ValueError("content_digest does not match declaration content.")
        return self

    def valid_at(self, now: datetime) -> bool:
        if self.expires_at is None:
            return True
        if self.expires_at.tzinfo is None or now.tzinfo is None:
            raise WorkflowResponseInvalid()
        return now <= self.expires_at


class ObservedWorkflowContext(StrictModel):
    """External observation with explicit age-based freshness."""

    context_version: Literal["projectlore-workflow-context/1.0.0"]
    context_kind: Literal["observed"]
    observation: WorkflowObservation
    maximum_age_seconds: int = Field(ge=1)

    def valid_at(self, now: datetime) -> bool:
        observed_at = self.observation.observed_at
        if observed_at.tzinfo is None or now.tzinfo is None:
            raise WorkflowResponseInvalid()
        age = (now - observed_at.astimezone(UTC)).total_seconds()
        return 0 <= age <= self.maximum_age_seconds


WorkflowContext = Annotated[
    DeclaredWorkflowContext | ObservedWorkflowContext,
    Field(discriminator="context_kind"),
]
WORKFLOW_CONTEXT_ADAPTER: TypeAdapter[WorkflowContext] = TypeAdapter(WorkflowContext)


def make_local_declaration(
    target: WorkflowTarget,
    *,
    title: str,
    status: str,
    validation_open: int = 0,
    declared_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> DeclaredWorkflowContext:
    if target.provider_id != "local" or target.container_id is not None:
        raise WorkflowTargetMismatch()
    timestamp = declared_at or datetime.now(UTC)
    if timestamp.tzinfo is None or (
        expires_at is not None and expires_at.tzinfo is None
    ):
        raise WorkflowResponseInvalid()
    content = {
        "project_id": target.project_id,
        "model_entrypoint": target.model_entrypoint,
        "provider_id": "local",
        "scope_id": target.scope_id,
        "container_id": None,
        "target_digest": target.digest,
        "title": title,
        "status": status,
        "validation_open": validation_open,
        "declared_at": timestamp.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at is not None else None,
        "declared_by": "operator",
        "authority_ref": f"local://scope/{target.scope_id}",
    }
    return DeclaredWorkflowContext(
        context_version="projectlore-workflow-context/1.0.0",
        context_kind="declared",
        content_digest=_digest(content),
        project_id=target.project_id,
        model_entrypoint=target.model_entrypoint,
        provider_id="local",
        scope_id=target.scope_id,
        container_id=None,
        target_digest=target.digest,
        title=title,
        status=status,
        validation_open=validation_open,
        declared_at=timestamp,
        expires_at=expires_at,
        declared_by="operator",
        authority_ref=f"local://scope/{target.scope_id}",
    )


class WorkflowScopeProvider(Protocol):
    """Read-only provider for current workflow context."""

    async def observe(self, target: WorkflowTarget) -> WorkflowObservation: ...


class WorkflowProviderFailure(Exception):
    """Safe, stable provider failure suitable for public diagnostics."""

    code: str = "workflow_unavailable"
    public_detail: str = "Workflow context is unavailable."

    def __init__(self) -> None:
        super().__init__(self.public_detail)


class WorkflowUnavailable(WorkflowProviderFailure):
    code = "workflow_unavailable"
    public_detail = "Workflow provider is unavailable."


class WorkflowTimeout(WorkflowProviderFailure):
    code = "workflow_timeout"
    public_detail = "Workflow provider timed out."


class WorkflowAuthenticationRequired(WorkflowProviderFailure):
    code = "workflow_authentication_required"
    public_detail = "Workflow provider authentication is required."


class WorkflowResponseInvalid(WorkflowProviderFailure):
    code = "workflow_response_invalid"
    public_detail = "Workflow provider returned an invalid response."


class WorkflowTargetMismatch(WorkflowProviderFailure):
    code = "workflow_target_mismatch"
    public_detail = "Workflow response does not match the configured target."


def make_observation(
    target: WorkflowTarget,
    *,
    assurance: WorkflowAssurance,
    title: str,
    status: str,
    validation_open: int,
    observed_at: datetime,
    authority_ref: str,
    provider_revision: str | None = None,
) -> WorkflowObservation:
    """Create a deterministic, target-bound observation."""
    content: dict[str, Any] = {
        "project_id": target.project_id,
        "model_entrypoint": target.model_entrypoint,
        "provider_id": target.provider_id,
        "scope_id": target.scope_id,
        "container_id": target.container_id,
        "assurance": assurance,
        "title": title,
        "status": status,
        "validation_open": validation_open,
        "observed_at": observed_at.isoformat(),
        "authority_ref": authority_ref,
        "provider_revision": provider_revision,
    }
    return WorkflowObservation(
        observation_version="projectlore-workflow-observation/1.0.0",
        target_digest=target.digest,
        content_digest=_digest(content),
        **content,
    )


def issue_workflow_receipt(
    observation: WorkflowObservation,
    target: WorkflowTarget,
    *,
    model_digest: str,
    now: datetime | None = None,
    maximum_age_seconds: int = 300,
) -> WorkflowReceipt:
    observation.validate_target(target)
    evaluated_at = now or datetime.now(UTC)
    if observation.observed_at.tzinfo is None:
        raise WorkflowResponseInvalid() from ValueError(
            "observed_at must include a timezone"
        )
    age = (
        evaluated_at - observation.observed_at.astimezone(UTC)
    ).total_seconds()
    return WorkflowReceipt(
        receipt_version="projectlore-workflow-receipt/1.0.0",
        project_id=target.project_id,
        model_entrypoint=target.model_entrypoint,
        model_digest=model_digest,
        provider_id=target.provider_id,
        scope_id=target.scope_id,
        container_id=target.container_id,
        target_digest=target.digest,
        observation_digest=observation.content_digest,
        assurance=observation.assurance,
        authority_ref=observation.authority_ref,
        observed_at=observation.observed_at,
        evaluated_at=evaluated_at,
        age_seconds=age,
        fresh=0 <= age <= maximum_age_seconds,
        maximum_age_seconds=maximum_age_seconds,
    )


class LocalScopeProvider:
    """Return an operator-supplied local declaration without network access."""

    def __init__(
        self,
        context: DeclaredWorkflowContext | WorkflowObservation,
    ) -> None:
        if context.provider_id != "local":
            raise ValueError("Local workflow context must be a local declaration.")
        if isinstance(context, WorkflowObservation) and context.assurance != "declared":
            raise ValueError("Local workflow context must be a local declaration.")
        self._context = context

    async def observe(self, target: WorkflowTarget) -> WorkflowObservation:
        return self.current_observation(target)

    def current_observation(self, target: WorkflowTarget) -> WorkflowObservation:
        """Resolve a local declaration synchronously for local boundaries."""
        if isinstance(self._context, WorkflowObservation):
            self._context.validate_target(target)
            return self._context
        if (
            self._context.project_id,
            self._context.model_entrypoint,
            self._context.provider_id,
            self._context.scope_id,
            self._context.container_id,
            self._context.target_digest,
        ) != (
            target.project_id,
            target.model_entrypoint,
            target.provider_id,
            target.scope_id,
            target.container_id,
            target.digest,
        ):
            raise WorkflowTargetMismatch()
        return make_observation(
            target,
            assurance="declared",
            title=self._context.title,
            status=self._context.status,
            validation_open=self._context.validation_open,
            observed_at=self._context.declared_at,
            authority_ref=self._context.authority_ref,
        )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
