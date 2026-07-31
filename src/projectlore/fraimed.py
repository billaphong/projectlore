"""Read-only Fraimed scope authority adapter."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from projectlore.scope import ScopeSnapshot
from projectlore.workflow import (
    WorkflowAuthenticationRequired,
    WorkflowObservation,
    WorkflowResponseInvalid,
    WorkflowTarget,
    WorkflowTargetMismatch,
    WorkflowTimeout,
    WorkflowUnavailable,
    make_observation,
)
from projectlore.workflow_compat import observation_to_legacy_snapshot


class FraimedScopeAuthority:
    """Compatibility adapter for legacy scope payloads."""

    def __init__(self, url: str, token: str, *, timeout_seconds: float = 10) -> None:
        self._provider = FraimedWorkflowProvider(
            url, token, timeout_seconds=timeout_seconds
        )

    async def current_scope(
        self, frame_id: str, space_id: str | None = None
    ) -> ScopeSnapshot:
        if space_id is None:
            raise WorkflowTargetMismatch()
        target = WorkflowTarget(
            target_version="projectlore-workflow-target/1.0.0",
            project_id="legacy:projectlore/compatibility",
            model_entrypoint="legacy://scope-snapshot/0.1.0",
            provider_id="fraimed",
            scope_id=frame_id,
            container_id=space_id,
        )
        observation = await self._provider.observe(target)
        return observation_to_legacy_snapshot(observation)


MAX_RESPONSE_BLOCKS = 32
MAX_RESPONSE_BYTES = 64 * 1024
MAX_RESPONSE_DEPTH = 32
ContextFetcher = Callable[[WorkflowTarget], Awaitable[Sequence[str]]]


class FraimedWorkflowProvider:
    """Provider-neutral adapter for observed Fraimed context."""

    def __init__(
        self,
        url: str,
        token: str,
        *,
        timeout_seconds: float = 10,
        context_fetcher: ContextFetcher | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not url.startswith("https://"):
            raise ValueError("Fraimed MCP URL must use HTTPS.")
        if not token:
            raise WorkflowAuthenticationRequired()
        self._url = url
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._context_fetcher = context_fetcher
        self._clock = clock or (lambda: datetime.now(UTC))

    async def observe(self, target: WorkflowTarget) -> WorkflowObservation:
        if target.provider_id != "fraimed" or target.container_id is None:
            raise WorkflowTargetMismatch()
        try:
            texts = (
                await self._context_fetcher(target)
                if self._context_fetcher is not None
                else await self._fetch_context(target)
            )
        except (
            WorkflowAuthenticationRequired,
            WorkflowResponseInvalid,
            WorkflowTargetMismatch,
            WorkflowTimeout,
            WorkflowUnavailable,
        ):
            raise
        except Exception as error:
            raise WorkflowUnavailable() from error
        context = _bounded_context(texts)
        frame = context.get("frame")
        validation = context.get("validationItems", [])
        if not isinstance(frame, dict) or not isinstance(validation, list):
            raise WorkflowResponseInvalid()
        if frame.get("id") != target.scope_id:
            raise WorkflowTargetMismatch()
        try:
            return make_observation(
                target,
                assurance="observed",
                title=str(frame["title"]),
                status=str(frame["status"]),
                validation_open=sum(
                    not item.get("met", False)
                    for item in validation
                    if isinstance(item, dict)
                ),
                observed_at=self._clock(),
                authority_ref=f"fraimed://frame/{target.scope_id}",
                provider_revision=(
                    str(frame["closureGeneration"])
                    if frame.get("closureGeneration") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WorkflowResponseInvalid() from error

    async def _fetch_context(self, target: WorkflowTarget) -> list[str]:
        headers = {"Authorization": f"Bearer {self._token}"}
        timeout = httpx.Timeout(self._timeout_seconds)
        try:
            async with (
                httpx.AsyncClient(headers=headers, timeout=timeout) as client,
                streamable_http_client(
                    self._url,
                    http_client=client,
                ) as (read_stream, write_stream, _),
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(
                        seconds=self._timeout_seconds
                    ),
                ) as session,
            ):
                await session.initialize()
                result = await session.call_tool(
                    "get_frame_context",
                    {
                        "frameId": target.scope_id,
                        "spaceId": target.container_id,
                        "brief": True,
                    },
                )
        except httpx.TimeoutException as error:
            raise WorkflowTimeout() from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                raise WorkflowAuthenticationRequired() from error
            raise WorkflowUnavailable() from error
        except Exception as error:
            raise WorkflowUnavailable() from error
        if result.isError:
            raise WorkflowResponseInvalid()
        texts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                texts.append(text)
        return texts


def _bounded_context(texts: Sequence[str]) -> dict[str, object]:
    if len(texts) > MAX_RESPONSE_BLOCKS:
        raise WorkflowResponseInvalid()
    total = 0
    documents: list[object] = []
    for text in texts:
        total += len(text.encode("utf-8"))
        if total > MAX_RESPONSE_BYTES:
            raise WorkflowResponseInvalid()
        try:
            document = json.loads(text)
        except (json.JSONDecodeError, RecursionError) as error:
            raise WorkflowResponseInvalid() from error
        if _json_depth(document) > MAX_RESPONSE_DEPTH:
            raise WorkflowResponseInvalid()
        documents.append(document)
    context = next(
        (
            item
            for item in documents
            if isinstance(item, dict) and "frame" in item
        ),
        None,
    )
    if not isinstance(context, dict):
        raise WorkflowResponseInvalid()
    return context


def _json_depth(value: object, depth: int = 0) -> int:
    if depth > MAX_RESPONSE_DEPTH:
        return depth
    if isinstance(value, dict):
        return max(
            (_json_depth(item, depth + 1) for item in value.values()),
            default=depth,
        )
    if isinstance(value, list):
        return max((_json_depth(item, depth + 1) for item in value), default=depth)
    return depth
