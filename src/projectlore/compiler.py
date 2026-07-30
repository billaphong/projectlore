"""Deterministic compilation of validated project knowledge."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from projectlore.models import ProjectKnowledgeModel


@dataclass(frozen=True)
class ProjectModel:
    model: ProjectKnowledgeModel
    normalized_json: bytes
    digest: str


def compile_model(model: ProjectKnowledgeModel) -> ProjectModel:
    normalized = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = f"sha256:{hashlib.sha256(normalized).hexdigest()}"
    return ProjectModel(model=model, normalized_json=normalized, digest=digest)
