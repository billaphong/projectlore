"""ProjectLore stdio MCP server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from projectlore.loader import project_root_for_model
from projectlore.policy import (
    FailedWorkflowResolution,
    MissingWorkflowResolution,
    PlannedPolicyResult,
    ValidWorkflowResolution,
    load_policy_registry,
    plan_policy,
)
from projectlore.policy import (
    evaluate_policy as evaluate_plan,
)
from projectlore.provider_dispatch import resolve_workflow_observation
from projectlore.query import QueryService
from projectlore.refresh import RefreshingModelService
from projectlore.scope_cache import LegacyScopeAuthority
from projectlore.service import ModelService
from projectlore.workflow import (
    DeclaredWorkflowContext,
    ObservedWorkflowContext,
    WorkflowProviderFailure,
    WorkflowTarget,
    issue_workflow_receipt,
)
from projectlore.workflow_state import load_workflow_context
from projectlore.workflow_target import load_workflow_target

MODEL_ENV = "PROJECTLORE_MODEL"
FRAIMED_URL_ENV = "PROJECTLORE_FRAIMED_MCP_URL"
FRAIMED_TOKEN_ENV = "FRAIMED_API_TOKEN"


def create_server(
    model_path: Path,
    scope_authority: LegacyScopeAuthority | None = None,
) -> FastMCP:
    injected_authority = scope_authority
    server = FastMCP(
        "ProjectLore",
        instructions="Read-only project meaning and deterministic policy tools.",
    )
    models = RefreshingModelService(model_path)
    project_root = project_root_for_model(model_path)

    @server.tool(name="model_status", structured_output=True)
    def model_status() -> dict[str, Any]:
        snapshot = models.refresh()
        return snapshot.decorate(snapshot.service.model_status())

    @server.tool(name="model_search", structured_output=True)
    def model_search(
        query: str,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> dict[str, Any]:
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
        max_depth: Annotated[int, Field(ge=1, le=5)] = 1,
        limit: Annotated[int, Field(ge=1, le=500)] = 100,
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
    def context_for_task(
        task: str,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> dict[str, Any]:
        snapshot = models.refresh()
        return snapshot.decorate(
            snapshot.service.context_for_task(task, limit=limit)
        )

    @server.tool(name="policy_check", structured_output=True)
    async def policy_check(
        facts: dict[str, str],
        context_requirements: list[
            Literal["workflow", "observed_workflow"]
        ] | None = None,
        target_identity: WorkflowTarget | None = None,
    ) -> dict[str, Any]:
        snapshot = models.refresh()
        service = snapshot.service
        registry = load_policy_registry(project_root)
        target = load_workflow_target(project_root)
        local_context: DeclaredWorkflowContext | None = None
        if target is None:
            try:
                loaded_context = load_workflow_context(project_root)
            except ValueError:
                loaded_context = None
            if isinstance(loaded_context, DeclaredWorkflowContext):
                local_context = loaded_context
                target = WorkflowTarget(
                    target_version="projectlore-workflow-target/1.0.0",
                    project_id=loaded_context.project_id,
                    model_entrypoint=loaded_context.model_entrypoint,
                    provider_id="local",
                    scope_id=loaded_context.scope_id,
                    container_id=None,
                )
        if target is not None and (
            target.project_id != service.model.id
            or target.model_entrypoint
            != model_path.relative_to(project_root).as_posix()
        ):
            raise ValueError("Configured workflow target does not match this model.")
        if target_identity is not None and target_identity != target:
            raise ValueError("Requested workflow target is not operator-configured.")
        plan = plan_policy(facts, registry, service.project, target)
        if context_requirements is not None and tuple(context_requirements) != (
            plan.context_requirements
        ):
            raise ValueError("Requested context requirements do not match the plan.")
        if not plan.context_requirements:
            planned = evaluate_plan(
                plan,
                MissingWorkflowResolution(
                    state="missing_context",
                    model_digest=plan.model_digest,
                    target_config_digest=plan.target_config_digest,
                ),
            )
            return snapshot.decorate(_planned_envelope(service, planned))
        if target is None:
            planned = evaluate_plan(
                plan,
                MissingWorkflowResolution(
                    state="missing_context",
                    model_digest=plan.model_digest,
                    target_config_digest=plan.target_config_digest,
                ),
            )
            return snapshot.decorate(_planned_envelope(service, planned))
        try:
            observation = await resolve_workflow_observation(
                target,
                local_context=local_context,
                injected_authority=injected_authority,
                fraimed_url=os.environ.get(
                    FRAIMED_URL_ENV, "https://www.fraimed.ai/api/mcp"
                ),
                fraimed_token=os.environ.get(FRAIMED_TOKEN_ENV, ""),
            )
        except TimeoutError:
            planned = evaluate_plan(
                plan,
                FailedWorkflowResolution(
                    state="provider_failure",
                    model_digest=plan.model_digest,
                    target_config_digest=plan.target_config_digest,
                    failure_code="workflow_timeout",
                ),
            )
            return snapshot.decorate(_planned_envelope(service, planned))
        except WorkflowProviderFailure as error:
            planned = evaluate_plan(
                plan,
                FailedWorkflowResolution(
                    state="provider_failure",
                    model_digest=plan.model_digest,
                    target_config_digest=plan.target_config_digest,
                    failure_code=error.code,
                ),
            )
            return snapshot.decorate(_planned_envelope(service, planned))
        except Exception:
            planned = evaluate_plan(
                plan,
                FailedWorkflowResolution(
                    state="provider_failure",
                    model_digest=plan.model_digest,
                    target_config_digest=plan.target_config_digest,
                    failure_code="workflow_unavailable",
                ),
            )
            return snapshot.decorate(_planned_envelope(service, planned))
        receipt = issue_workflow_receipt(
            observation,
            target,
            model_digest=plan.model_digest,
        )
        if target.provider_id == "local":
            if not isinstance(local_context, DeclaredWorkflowContext):
                raise ValueError("Configured local workflow context is invalid.")
            context: DeclaredWorkflowContext | ObservedWorkflowContext = local_context
        else:
            context = ObservedWorkflowContext(
                context_version="projectlore-workflow-context/1.0.0",
                context_kind="observed",
                observation=observation,
                maximum_age_seconds=receipt.maximum_age_seconds,
            )
        planned = evaluate_plan(
            plan,
            ValidWorkflowResolution(
                state="valid_context",
                model_digest=plan.model_digest,
                target_config_digest=plan.target_config_digest,
                context=context,
                observation=observation,
                receipt=receipt,
            ),
        )
        return snapshot.decorate(_planned_envelope(service, planned))

    return server


def _planned_envelope(
    service: ModelService,
    planned: PlannedPolicyResult,
) -> dict[str, Any]:
    source_refs = {ref for item in planned.findings for ref in item.source_refs}
    sources = [
        source
        for source in service.project.model.sources
        if source.id in source_refs
    ]
    payload = planned.model_dump(mode="json")
    # Frozen tools/0.2 clients still expect this result-level key. Canonical
    # evidence is carried per finding and this compatibility field stays empty.
    payload["scope_receipt"] = None
    return QueryService(service.project).envelope(
        payload,
        provenance=sources,
    )


def main() -> None:
    raw_path = os.environ.get(MODEL_ENV)
    if not raw_path:
        raise SystemExit(f"{MODEL_ENV} must point to a ProjectLore model.")
    create_server(Path(raw_path)).run(transport="stdio")


if __name__ == "__main__":
    main()
