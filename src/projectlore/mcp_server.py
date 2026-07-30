"""ProjectLore stdio MCP server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from projectlore.fraimed import FraimedScopeAuthority, ScopeAuthority
from projectlore.policy import PolicyRequest
from projectlore.policy import policy_check as evaluate_policy
from projectlore.service import ModelService

MODEL_ENV = "PROJECTLORE_MODEL"
FRAIMED_URL_ENV = "PROJECTLORE_FRAIMED_MCP_URL"
FRAIMED_TOKEN_ENV = "FRAIMED_API_TOKEN"


def create_server(
    model_path: Path,
    scope_authority: ScopeAuthority | None = None,
) -> FastMCP:
    authority = scope_authority or FraimedScopeAuthority(
        os.environ.get(
            FRAIMED_URL_ENV,
            "https://www.fraimed.ai/api/mcp",
        ),
        os.environ.get(FRAIMED_TOKEN_ENV, ""),
    )
    server = FastMCP(
        "ProjectLore",
        instructions="Read-only project meaning and deterministic policy tools.",
    )

    @server.tool(name="model_status", structured_output=True)
    def model_status() -> dict[str, Any]:
        return ModelService(model_path).model_status()

    @server.tool(name="context_for_task", structured_output=True)
    def context_for_task(task: str) -> dict[str, Any]:
        return ModelService(model_path).context_for_task(task)

    @server.tool(name="policy_check", structured_output=True)
    async def policy_check(
        facts: dict[str, str],
        frame_id: str,
        space_id: str,
    ) -> dict[str, Any]:
        scope = await authority.current_scope(frame_id, space_id)
        return evaluate_policy(
            ModelService(model_path),
            PolicyRequest(facts=facts, scope=scope),
            scope_obtained_via="fraimed_mcp",
        )

    return server


def main() -> None:
    raw_path = os.environ.get(MODEL_ENV)
    if not raw_path:
        raise SystemExit(f"{MODEL_ENV} must point to a ProjectLore model.")
    create_server(Path(raw_path)).run(transport="stdio")


if __name__ == "__main__":
    main()
