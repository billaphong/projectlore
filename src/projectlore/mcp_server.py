"""ProjectLore stdio MCP server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from projectlore.fraimed import FraimedScopeAuthority, ScopeAuthority
from projectlore.policy import PolicyRequest
from projectlore.policy import policy_check as evaluate_policy
from projectlore.query import CONTRACT_VERSION, QueryService
from projectlore.service import ModelService
from projectlore.validation import validate_path

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

    @server.tool(name="model_search", structured_output=True)
    def model_search(query: str, limit: int = 20) -> dict[str, Any]:
        service = ModelService(model_path)
        return QueryService(service.project).search(query, limit=limit)

    @server.tool(name="model_get_concept", structured_output=True)
    def model_get_concept(concept_id: str) -> dict[str, Any]:
        service = ModelService(model_path)
        return QueryService(service.project).get_concept(concept_id)

    @server.tool(name="model_resolve_term", structured_output=True)
    def model_resolve_term(term: str) -> dict[str, Any]:
        service = ModelService(model_path)
        return QueryService(service.project).resolve_term(term)

    @server.tool(name="model_get_relationships", structured_output=True)
    def model_get_relationships(
        concept_id: str,
        direction: Literal["incoming", "outgoing", "both"] = "both",
        max_depth: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        service = ModelService(model_path)
        query = QueryService(service.project)
        return query.get_relationships(
            concept_id,
            direction=direction,
            max_depth=max_depth,
            limit=limit,
        )

    @server.tool(name="model_validate", structured_output=True)
    def model_validate() -> dict[str, Any]:
        model, report = validate_path(model_path)
        if model is not None and report.valid:
            query = QueryService(ModelService(model_path).project)
            return query.envelope(
                {
                    "valid": True,
                    "diagnostics": report.to_dict()["diagnostics"],
                }
            )
        return {
            "contract_version": CONTRACT_VERSION,
            "contract_digest": None,
            "model_digest": None,
            "freshness": {"state": "unavailable"},
            "authority": {"source_count": 0, "trust": [], "kinds": []},
            "result_state": "complete",
            "provenance": [],
            "valid": report.valid,
            "diagnostics": report.to_dict()["diagnostics"],
        }

    @server.tool(name="context_for_task", structured_output=True)
    def context_for_task(task: str) -> dict[str, Any]:
        return ModelService(model_path).context_for_task(task)

    @server.tool(name="policy_check", structured_output=True)
    async def policy_check(
        facts: dict[str, str],
        frame_id: str,
        space_id: str,
    ) -> dict[str, Any]:
        service = ModelService(model_path)
        try:
            scope = await authority.current_scope(frame_id, space_id)
        except TimeoutError:
            return QueryService(service.project).envelope(
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
        return evaluate_policy(
            service,
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
