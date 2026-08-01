"""Small composition root for built-in workflow providers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from projectlore.fraimed import FraimedWorkflowProvider
from projectlore.scope import ScopeSnapshot
from projectlore.workflow import (
    DeclaredWorkflowContext,
    LocalScopeProvider,
    WorkflowAuthenticationRequired,
    WorkflowObservation,
    WorkflowScopeProvider,
    WorkflowTarget,
    WorkflowUnavailable,
)
from projectlore.workflow_compat import legacy_snapshot_to_observation


class LegacyAuthority(Protocol):
    async def current_scope(
        self, scope_id: str, container_id: str | None = None
    ) -> ScopeSnapshot: ...


def build_workflow_provider(
    provider_id: str,
    *,
    local_observation: DeclaredWorkflowContext | WorkflowObservation | None = None,
    fraimed_url: str | None = None,
    fraimed_token: str | None = None,
) -> WorkflowScopeProvider:
    """Construct one of the two deliberately supported provider adapters."""
    builders: dict[str, Callable[[], WorkflowScopeProvider]] = {
        "local": lambda: _local(local_observation),
        "fraimed": lambda: _fraimed(fraimed_url, fraimed_token),
    }
    try:
        builder = builders[provider_id]
    except KeyError as error:
        raise WorkflowUnavailable() from error
    return builder()


async def resolve_workflow_observation(
    target: WorkflowTarget,
    *,
    local_context: DeclaredWorkflowContext | WorkflowObservation | None = None,
    injected_authority: LegacyAuthority | None = None,
    fraimed_url: str | None = None,
    fraimed_token: str | None = None,
) -> WorkflowObservation:
    """Resolve exactly one configured target through the shared composition root."""

    if injected_authority is not None:
        snapshot = await injected_authority.current_scope(
            target.scope_id, target.container_id
        )
        return legacy_snapshot_to_observation(snapshot, target)
    provider = build_workflow_provider(
        target.provider_id,
        local_observation=local_context,
        fraimed_url=fraimed_url,
        fraimed_token=fraimed_token,
    )
    return await provider.observe(target)


def _local(
    observation: DeclaredWorkflowContext | WorkflowObservation | None,
) -> WorkflowScopeProvider:
    if observation is None:
        raise WorkflowUnavailable()
    return LocalScopeProvider(observation)


def _fraimed(url: str | None, token: str | None) -> WorkflowScopeProvider:
    if token is None or token == "":
        raise WorkflowAuthenticationRequired()
    if url is None:
        raise WorkflowUnavailable()
    return FraimedWorkflowProvider(url, token)
