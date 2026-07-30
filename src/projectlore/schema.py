"""Portable JSON Schema generation and drift checks."""

from __future__ import annotations

import json
from pathlib import Path

from projectlore.models import ProjectKnowledgeModel


def render_json_schema() -> str:
    schema = ProjectKnowledgeModel.model_json_schema(
        ref_template="#/$defs/{model}",
        mode="validation",
    )
    schema["$id"] = "https://projectlore.ai/schema/projectlore.schema.json"
    schema["title"] = "ProjectLore Project Knowledge Model"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def schema_matches(path: Path) -> bool:
    return path.is_file() and path.read_text(encoding="utf-8") == render_json_schema()
