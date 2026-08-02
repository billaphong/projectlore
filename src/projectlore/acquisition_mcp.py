"""Separately versioned read-only MCP sidecar for acquisition evidence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import (
    INVALID_PARAMS,
    CallToolResult,
    ErrorData,
    TextContent,
    ToolAnnotations,
)
from pydantic import Field

from projectlore.acquisition.digest import canonical_json, content_digest
from projectlore.acquisition.onboarding import canonical_model_digest
from projectlore.acquisition.passive import knowledge_status
from projectlore.acquisition.store import CorruptStore, KnowledgeStore

ROOT_ENV = "PROJECTLORE_ROOT"
TOOL_VERSION = "projectlore-acquisition-tools/0.6.1"
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def _tool_error(code: str, message: str, *, retryable: bool) -> CallToolResult:
    payload = {"code": code, "message": message, "retryable": retryable}
    return CallToolResult(
        content=[
            TextContent(type="text", text=canonical_json(payload).decode("utf-8"))
        ],
        structuredContent=payload,
        isError=True,
    )


def _objects(repository: Path, contract_version: str) -> list[dict[str, Any]]:
    store = KnowledgeStore(repository)
    if not store.active_root.exists():
        return []
    return sorted(
        (
            item
            for item in (
                store.get_object(member) for member in store.current_root().members
            )
            if item.get("contract_version") == contract_version
        ),
        key=lambda item: str(
            item.get("packet_id")
            or item.get("proposal_id")
            or item.get("review_id")
            or item.get("receipt_id")
        ),
    )


def _page(
    repository: Path,
    contract_version: str,
    identity: str,
    selected_id: str | None,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    store = KnowledgeStore(repository)
    root_digest = (
        canonical_model_digest(repository)
        if not store.active_root.exists()
        else store.current_root().root_digest
    )
    items = _objects(repository, contract_version)
    if selected_id is not None:
        items = [item for item in items if item.get(identity) == selected_id]
    elif cursor is not None:
        start = None
        for index, item in enumerate(items):
            candidate = content_digest(
                "projectlore:acquisition-cursor:0.6.1",
                {
                    "tool": contract_version,
                    "root_digest": root_digest,
                    "last_id": item[identity],
                    "limit": limit,
                },
            )
            if candidate == cursor:
                start = index + 1
                break
        if start is None:
            raise ValueError("PLKA4004 stale or invalid acquisition cursor")
        items = items[start:]
    truncated = len(items) > limit
    selected = items[:limit]
    next_cursor = None
    if truncated and selected:
        next_cursor = content_digest(
            "projectlore:acquisition-cursor:0.6.1",
            {
                "tool": contract_version,
                "root_digest": root_digest,
                "last_id": selected[-1][identity],
                "limit": limit,
            },
        )
    initialized = store.active_root.exists()
    return {
        "contract_version": TOOL_VERSION,
        "state": (
            "present"
            if initialized and selected_id is None
            else ("present" if selected else "missing")
        ),
        "items": selected,
        "diagnostics": [],
        "provenance": [{"source_kind": "derived", "source_digest": root_digest}],
        "truncated": truncated,
        **({"next_cursor": next_cursor} if next_cursor is not None else {}),
    }


def create_server(repository: Path) -> FastMCP:
    root = repository.resolve(strict=True)
    server = FastMCP(
        "projectlore-acquisition",
        instructions="Read-only ProjectLore acquisition evidence tools.",
    )

    @server.tool(name="knowledge_status", annotations=READ_ONLY, structured_output=True)
    def status() -> dict[str, Any]:
        try:
            raw = knowledge_status(root)
        except CorruptStore as error:
            source_digest = canonical_model_digest(root)
            return {
                "contract_version": "projectlore-knowledge-status/0.6.1",
                "state": "corrupt",
                "canonical_model_digest": source_digest,
                "next_action": "repair",
                "diagnostics": [{"code": "PLKA4003", "message": str(error)}],
                "provenance": [
                    {"source_kind": "derived", "source_digest": source_digest}
                ],
            }
        state = raw["state"]
        mapped = {
            "not_initialized": "missing",
            "current": "ready",
            "outstanding": "outstanding",
        }.get(state, state)
        source_digest = raw["canonical_model_digest"]
        return {
            "contract_version": "projectlore-knowledge-status/0.6.1",
            "state": mapped,
            "canonical_model_digest": (
                None if source_digest.endswith("0" * 64) else source_digest
            ),
            "next_action": {
                "missing": "onboard_start",
                "outstanding": "review",
                "ready": "scan",
            }.get(mapped, "recover"),
            "diagnostics": [],
            "provenance": [{"source_kind": "derived", "source_digest": source_digest}],
        }

    def selector(
        contract: str,
        identity: str,
        selected_id: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if selected_id is not None and cursor is not None:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS, message="id and cursor are mutually exclusive"
                )
            )
        try:
            return _page(root, contract, identity, selected_id, cursor, limit)
        except (CorruptStore, ValueError) as error:
            code = "PLKA4004" if isinstance(error, ValueError) else "PLKA4003"
            return _tool_error(
                code, str(error), retryable=isinstance(error, ValueError)
            )  # type: ignore[return-value]

    @server.tool(
        name="knowledge_get_packet", annotations=READ_ONLY, structured_output=True
    )
    def get_packet(
        id: str | None = None,
        cursor: str | None = None,
        limit: Annotated[int, Field(ge=1, le=256)] = 50,
    ) -> dict[str, Any]:
        return selector(
            "projectlore-knowledge-packet/0.6.1", "packet_id", id, cursor, limit
        )

    @server.tool(
        name="knowledge_get_proposal", annotations=READ_ONLY, structured_output=True
    )
    def get_proposal(
        id: str | None = None,
        cursor: str | None = None,
        limit: Annotated[int, Field(ge=1, le=256)] = 50,
    ) -> dict[str, Any]:
        return selector(
            "projectlore-knowledge-proposal/0.6.1",
            "proposal_id",
            id,
            cursor,
            limit,
        )

    @server.tool(
        name="knowledge_get_review", annotations=READ_ONLY, structured_output=True
    )
    def get_review(
        id: str | None = None,
        cursor: str | None = None,
        limit: Annotated[int, Field(ge=1, le=256)] = 50,
    ) -> dict[str, Any]:
        return selector(
            "projectlore-knowledge-review/0.6.1", "review_id", id, cursor, limit
        )

    @server.tool(
        name="knowledge_get_receipt", annotations=READ_ONLY, structured_output=True
    )
    def get_receipt(
        id: str | None = None,
        cursor: str | None = None,
        limit: Annotated[int, Field(ge=1, le=256)] = 50,
    ) -> dict[str, Any]:
        return selector(
            "projectlore-knowledge-receipt/0.6.1", "receipt_id", id, cursor, limit
        )

    return server


def main() -> None:
    raw_root = os.environ.get(ROOT_ENV)
    if not raw_root:
        raise SystemExit(f"{ROOT_ENV} must point to a ProjectLore repository.")
    create_server(Path(raw_root)).run(transport="stdio")


if __name__ == "__main__":
    main()
