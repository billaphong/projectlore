"""ProjectLore stdio MCP server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from projectlore.fraimed import FraimedScopeAuthority, ScopeAuthority
from projectlore.policy import PolicyRequest
from projectlore.policy import policy_check as evaluate_policy
from projectlore.query import QueryService
from projectlore.refresh import RefreshingModelService

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
    models = RefreshingModelService(model_path)

    @server.tool(name="model_status", structured_output=True)
    def model_status() -> dict[str, Any]:
        snapshot = models.refresh()
        return snapshot.decorate(snapshot.service.model_status())

    @server.tool(name="model_search", structured_output=True)
    def model_search(query: str, limit: int = 20) -> dict[str, Any]:
        snapshot = models.refresh()
        result = QueryService(snapshot.service.project).search(query, limit=limit)
        return snapshot.decorate(result)

    @server.tool(name="model_get_concept", structured_output=True)
    def model_get_concept(concept_id: str) -> dict[str, Any]:
        snapshot = models.refresh()
        result = QueryService(snapshot.service.project).get_concept(concept_id)
        return snapshot.decorate(result)

    @server.tool(name="model_resolve_term", structured_output=True)
    def model_resolve_term(term: str) -> dict[str, Any]:
        snapshot = models.refresh()
        result = QueryService(snapshot.service.project).resolve_term(term)
        return snapshot.decorate(result)

    @server.tool(name="model_get_relationships", structured_output=True)
    def model_get_relationships(
        concept_id: str,
        direction: Literal["incoming", "outgoing", "both"] = "both",
        max_depth: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        snapshot = models.refresh()
        query = QueryService(snapshot.service.project)
        result = query.get_relationships(
            concept_id,
            direction=direction,
            max_depth=max_depth,
            limit=limit,
        )
        return snapshot.decorate(result)

    @server.tool(name="model_validate", structured_output=True)
    def model_validate() -> dict[str, Any]:
        snapshot = models.refresh()
        query = QueryService(snapshot.service.project)
        result = query.envelope(
            {
                "valid": snapshot.state == "current",
                "diagnostics": list(snapshot.diagnostics),
            }
        )
        return snapshot.decorate(result)

    @server.tool(name="context_for_task", structured_output=True)
    def context_for_task(task: str) -> dict[str, Any]:
        snapshot = models.refresh()
        return snapshot.decorate(snapshot.service.context_for_task(task))

    @server.tool(name="policy_check", structured_output=True)
    async def policy_check(
        facts: dict[str, str],
        frame_id: str,
        space_id: str,
    ) -> dict[str, Any]:
        snapshot = models.refresh()
        service = snapshot.service
        try:
            scope = await authority.current_scope(frame_id, space_id)
        except TimeoutError:
            result = QueryService(service.project).envelope(
                {
                    "decision": "indeterminate",
                    "findings": [
                        {
                            "rule_id": "projectlore:workflow/current-scope",
                            "decision": "indeterminate",
                            "outcome": "dependency_timeout",
                            "message": "Workflow scope lookup timed out.",
                            "source_refs": [],
                        }
                    ],
                    "scope_receipt": None,
                }
            )
            return snapshot.decorate(result)
        result = evaluate_policy(
            service,
            PolicyRequest(facts=facts, scope=scope),
            scope_obtained_via="fraimed_mcp",
        )
        return snapshot.decorate(result)

    return server


def main() -> None:
    raw_path = os.environ.get(MODEL_ENV)
    if not raw_path:
        raise SystemExit(f"{MODEL_ENV} must point to a ProjectLore model.")
    create_server(Path(raw_path)).run(transport="stdio")


if __name__ == "__main__":
    main()
