"""Read-only Fraimed scope authority adapter."""

from __future__ import annotations

import json
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


class FraimedScopeAuthority:
    """Compatibility adapter for legacy scope payloads."""

    def __init__(self, url: str, token: str, *, timeout_seconds: float = 10) -> None:
        if not url.startswith("https://"):
            raise ValueError("Fraimed MCP URL must use HTTPS.")
        if not token:
            raise ValueError("Fraimed API token is required.")
        self._url = url
        self._token = token
        self._timeout_seconds = timeout_seconds

    async def current_scope(
        self, frame_id: str, space_id: str | None = None
    ) -> ScopeSnapshot:
        if space_id is None:
            raise ValueError("Fraimed workflow scope requires a Space ID.")
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
                    {"frameId": frame_id, "spaceId": space_id, "brief": True},
                )
        except Exception as error:
            raise RuntimeError("Fraimed scope lookup failed.") from error
        if result.isError:
            raise RuntimeError("Fraimed rejected the scope lookup.")
        documents = []
        for block in result.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                try:
                    documents.append(json.loads(text))
                except json.JSONDecodeError:
                    continue
        context = next(
            (item for item in documents if isinstance(item, dict) and "frame" in item),
            None,
        )
        if context is None:
            raise RuntimeError("Fraimed scope response did not include a Frame.")
        frame = context["frame"]
        validation = context.get("validationItems", [])
        if frame.get("id") != frame_id:
            raise RuntimeError("Fraimed returned a different Frame.")
        return ScopeSnapshot(
            authority="fraimed",
            frame_id=frame["id"],
            frame_title=frame["title"],
            frame_status=frame["status"],
            validation_open=sum(
                not item.get("met", False)
                for item in validation
                if isinstance(item, dict)
            ),
            observed_at=datetime.now(UTC),
            authority_ref=f"fraimed://frame/{frame['id']}",
        )


class FraimedWorkflowProvider:
    """Provider-neutral adapter for observed Fraimed context."""

    def __init__(self, url: str, token: str, *, timeout_seconds: float = 10) -> None:
        if not url.startswith("https://"):
            raise ValueError("Fraimed MCP URL must use HTTPS.")
        if not token:
            raise WorkflowAuthenticationRequired()
        self._url = url
        self._token = token
        self._timeout_seconds = timeout_seconds

    async def observe(self, target: WorkflowTarget) -> WorkflowObservation:
        if target.provider_id != "fraimed" or target.container_id is None:
            raise WorkflowTargetMismatch()
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
        documents: list[object] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                try:
                    documents.append(json.loads(text))
                except json.JSONDecodeError:
                    continue
        context = next(
            (
                item
                for item in documents
                if isinstance(item, dict) and "frame" in item
            ),
            None,
        )
        if context is None:
            raise WorkflowResponseInvalid()
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
                observed_at=datetime.now(UTC),
                authority_ref=f"fraimed://frame/{target.scope_id}",
                provider_revision=(
                    str(frame["closureGeneration"])
                    if frame.get("closureGeneration") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WorkflowResponseInvalid() from error
