"""Small composition root for built-in workflow providers."""

from __future__ import annotations

from collections.abc import Callable

from projectlore.fraimed import FraimedWorkflowProvider
from projectlore.workflow import (
    LocalScopeProvider,
    WorkflowAuthenticationRequired,
    WorkflowObservation,
    WorkflowScopeProvider,
    WorkflowUnavailable,
)


def build_workflow_provider(
    provider_id: str,
    *,
    local_observation: WorkflowObservation | None = None,
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


def _local(observation: WorkflowObservation | None) -> WorkflowScopeProvider:
    if observation is None:
        raise WorkflowUnavailable()
    return LocalScopeProvider(observation)


def _fraimed(url: str | None, token: str | None) -> WorkflowScopeProvider:
    if token is None or token == "":
        raise WorkflowAuthenticationRequired()
    if url is None:
        raise WorkflowUnavailable()
    return FraimedWorkflowProvider(url, token)
