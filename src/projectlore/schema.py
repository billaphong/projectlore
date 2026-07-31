"""Portable JSON Schema generation and drift checks."""

from __future__ import annotations

import json
from pathlib import Path

from projectlore.models import (
    CheckerBinding,
    ContextProfile,
    IntegrationManifest,
    ProjectKnowledgeModel,
)
from projectlore.scope import ScopeReceipt
from projectlore.workflow import (
    DeclaredWorkflowContext,
    ObservedWorkflowContext,
    WorkflowObservation,
    WorkflowReceipt,
    WorkflowTarget,
)


def render_json_schema() -> str:
    schema = ProjectKnowledgeModel.model_json_schema(
        ref_template="#/$defs/{model}",
        mode="validation",
    )
    definitions = schema.setdefault("$defs", {})
    for contract in (
        CheckerBinding,
        ContextProfile,
        IntegrationManifest,
        ScopeReceipt,
        WorkflowTarget,
        WorkflowObservation,
        WorkflowReceipt,
        DeclaredWorkflowContext,
        ObservedWorkflowContext,
    ):
        contract_schema = contract.model_json_schema(
            ref_template="#/$defs/{model}",
            mode="validation",
        )
        definitions.update(contract_schema.pop("$defs", {}))
        definitions[contract.__name__] = contract_schema
    schema["$id"] = "https://projectlore.ai/schema/projectlore.schema.json"
    schema["title"] = "ProjectLore Project Knowledge Model"
    schema["x-projectlore-public-contracts"] = [
        "ProjectKnowledgeModel",
        "Domain",
        "Concept",
        "Term",
        "Relationship",
        "Rule",
        "Source",
        "ImplementationAnchor",
        "CheckerBinding",
        "ContextProfile",
        "IntegrationManifest",
        "ScopeReceipt",
        "WorkflowTarget",
        "WorkflowObservation",
        "WorkflowReceipt",
        "DeclaredWorkflowContext",
        "ObservedWorkflowContext",
    ]
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def schema_matches(path: Path) -> bool:
    return path.is_file() and path.read_text(encoding="utf-8") == render_json_schema()
