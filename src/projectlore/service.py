"""Deterministic read-only query surface for a project knowledge model."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from projectlore.compiler import ProjectModel, compile_model
from projectlore.models import ProjectKnowledgeModel, Rule, Source
from projectlore.query import CONTRACT_VERSION as CONTRACT_VERSION
from projectlore.query import QueryService
from projectlore.validation import ValidationReport, validate_path


class InvalidModelError(ValueError):
    def __init__(self, path: Path, report: ValidationReport) -> None:
        locations = "; ".join(
            f"{path}:{item.path} [{item.code}] {item.message}"
            for item in report.diagnostics
        )
        super().__init__(f"Project knowledge model is invalid: {locations}")
        self.report = report


class ModelService:
    """An immutable in-memory projection of one validated model file."""

    def __init__(self, model_path: Path) -> None:
        model, report = validate_path(model_path)
        if model is None or not report.valid:
            raise InvalidModelError(model_path, report)
        self._path = model_path.resolve()
        self._project = compile_model(model)
        self._model = self._project.model
        self._model_digest = self._project.digest
        self._query = QueryService(self._project)
        self._sources = {source.id: source for source in model.sources}

    @property
    def model(self) -> ProjectKnowledgeModel:
        return self._model

    @property
    def project(self) -> ProjectModel:
        return self._project

    def model_status(self) -> dict[str, Any]:
        result = self._query.model_status()
        result["path"] = str(self._path)
        return result

    def context_for_task(self, task: str) -> dict[str, Any]:
        result = self._query.context_for_task(task)
        result["sources"] = result["provenance"]
        return result

    def sources_for_rule(self, rule: Rule) -> list[Source]:
        return [self._sources[source_id] for source_id in rule.source_refs]

    def envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._envelope(payload)

    def _envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._query.envelope(payload)


def diagnostics_payload(report: ValidationReport) -> dict[str, object]:
    return {
        "valid": report.valid,
        "diagnostics": [asdict(item) for item in report.diagnostics],
    }
