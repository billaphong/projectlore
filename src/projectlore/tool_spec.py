"""Normative provider- and transport-neutral public MCP tool specification."""

from __future__ import annotations

from typing import Any

TOOLS_CONTRACT_VERSION = "projectlore-tools/0.4.0"

# Human-readable summary retained beside the complete normative schemas below.
TOOL_SPECS: dict[str, dict[str, Any]] = {
    "model_status": {"required": (), "optional": {}, "types": {}},
    "model_search": {
        "required": ("query",),
        "types": {"query": "string", "limit": "integer"},
        "optional": {"limit": {"default": 20, "minimum": 1, "maximum": 100}},
    },
    "model_get_concept": {
        "required": ("concept_id",),
        "optional": {},
        "types": {"concept_id": "string"},
    },
    "model_resolve_term": {
        "required": ("term",),
        "optional": {},
        "types": {"term": "string"},
    },
    "model_get_relationships": {
        "required": ("concept_id",),
        "types": {
            "concept_id": "string",
            "direction": "string",
            "max_depth": "integer",
            "limit": "integer",
        },
        "optional": {
            "direction": {
                "default": "both",
                "enum": ("incoming", "outgoing", "both"),
            },
            "max_depth": {"default": 1, "minimum": 1, "maximum": 5},
            "limit": {"default": 100, "minimum": 1, "maximum": 500},
        },
    },
    "model_validate": {"required": (), "optional": {}, "types": {}},
    "context_for_task": {
        "required": ("task",),
        "types": {"task": "string", "limit": "integer"},
        "optional": {"limit": {"default": 20, "minimum": 1, "maximum": 100}},
    },
    "policy_check": {
        "required": ("facts",),
        "types": {
            "facts": "string_map",
            "context_requirements": "nullable_string_array",
            "target_identity": "nullable_workflow_target",
        },
        "optional": {
            "context_requirements": {
                "default": None,
                "item_enum": ("workflow", "observed_workflow"),
            },
            "target_identity": {"default": None},
        },
        "target_authority": "operator_configured_only",
        "workflow_target": {
            "required": (
                "target_version",
                "project_id",
                "model_entrypoint",
                "provider_id",
                "scope_id",
            ),
            "properties": {
                "target_version": {
                    "type": "string",
                    "const": "projectlore-workflow-target/1.0.0",
                },
                "project_id": {"type": "string", "minLength": 1, "maxLength": 256},
                "model_entrypoint": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 1024,
                },
                "provider_id": {
                    "type": "string",
                    "pattern": "^[a-z][a-z0-9_-]{0,63}$",
                },
                "scope_id": {"type": "string", "minLength": 1, "maxLength": 256},
                "container_id": {
                    "type": "nullable_string",
                    "minLength": 1,
                    "maxLength": 256,
                },
            },
        },
    },
}


WORKFLOW_TARGET_SCHEMA: dict[str, Any] = {
    "additionalProperties": False,
    "properties": {
        "target_version": {
            "const": "projectlore-workflow-target/1.0.0",
            "type": "string",
        },
        "project_id": {"maxLength": 256, "minLength": 1, "type": "string"},
        "model_entrypoint": {
            "maxLength": 1024,
            "minLength": 1,
            "type": "string",
        },
        "provider_id": {
            "pattern": "^[a-z][a-z0-9_-]{0,63}$",
            "type": "string",
        },
        "scope_id": {"maxLength": 256, "minLength": 1, "type": "string"},
        "container_id": {
            "anyOf": [
                {"maxLength": 256, "minLength": 1, "type": "string"},
                {"type": "null"},
            ],
            "default": None,
        },
    },
    "required": [
        "target_version",
        "project_id",
        "model_entrypoint",
        "provider_id",
        "scope_id",
    ],
    "type": "object",
}


def _object(
    properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    value: dict[str, Any] = {"properties": properties, "type": "object"}
    if required:
        value["required"] = required
    return value


# Complete normalized schemas; only presentation-only title/description fields
# are omitted. Runtime FastMCP schemas must equal these structures exactly.
TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "model_status": _object({}),
    "model_search": _object(
        {
            "query": {"type": "string"},
            "limit": {"default": 20, "maximum": 100, "minimum": 1, "type": "integer"},
        },
        ["query"],
    ),
    "model_get_concept": _object({"concept_id": {"type": "string"}}, ["concept_id"]),
    "model_resolve_term": _object({"term": {"type": "string"}}, ["term"]),
    "model_get_relationships": _object(
        {
            "concept_id": {"type": "string"},
            "direction": {
                "default": "both",
                "enum": ["incoming", "outgoing", "both"],
                "type": "string",
            },
            "max_depth": {"default": 1, "maximum": 5, "minimum": 1, "type": "integer"},
            "limit": {"default": 100, "maximum": 500, "minimum": 1, "type": "integer"},
        },
        ["concept_id"],
    ),
    "model_validate": _object({}),
    "context_for_task": _object(
        {
            "task": {"type": "string"},
            "limit": {"default": 20, "maximum": 100, "minimum": 1, "type": "integer"},
        },
        ["task"],
    ),
    "policy_check": {
        "$defs": {"WorkflowTarget": WORKFLOW_TARGET_SCHEMA},
        **_object(
            {
                "facts": {"additionalProperties": {"type": "string"}, "type": "object"},
                "context_requirements": {
                    "anyOf": [
                        {
                            "items": {
                                "enum": ["workflow", "observed_workflow"],
                                "type": "string",
                            },
                            "type": "array",
                        },
                        {"type": "null"},
                    ],
                    "default": None,
                },
                "target_identity": {
                    "anyOf": [
                        {"$ref": "#/$defs/WorkflowTarget"},
                        {"type": "null"},
                    ],
                    "default": None,
                },
            },
            ["facts"],
        ),
    },
}
