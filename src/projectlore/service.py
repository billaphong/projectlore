"""Deterministic read-only query surface for a project knowledge model."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from projectlore.models import ProjectKnowledgeModel, Rule, Source
from projectlore.validation import ValidationReport, validate_path

CONTRACT_VERSION = "projectlore-tools/0.1.0"
_TOKEN = re.compile(r"[a-z0-9_]+")


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
        self._model = model
        self._model_digest = _digest(model.model_dump(mode="json"))
        self._contract_digest = _digest(
            {"contract_version": CONTRACT_VERSION, "tools": _tool_contract()}
        )
        self._sources = {source.id: source for source in model.sources}

    @property
    def model(self) -> ProjectKnowledgeModel:
        return self._model

    def model_status(self) -> dict[str, Any]:
        return self._envelope(
            {
                "model_id": self._model.id,
                "model_version": self._model.model_version,
                "schema_version": self._model.schema_version,
                "path": str(self._path),
                "counts": {
                    "domains": len(self._model.domains),
                    "concepts": len(self._model.concepts),
                    "relationships": len(self._model.relationships),
                    "rules": len(self._model.rules),
                    "sources": len(self._model.sources),
                },
            }
        )

    def context_for_task(self, task: str) -> dict[str, Any]:
        task_tokens = _tokens(task)
        ranked: list[tuple[int, Rule]] = []
        for rule in self._model.rules:
            text = " ".join(
                (
                    rule.id,
                    rule.statement,
                    rule.rationale or "",
                    rule.remediation or "",
                )
            )
            score = len(task_tokens & _tokens(text))
            ranked.append((score, rule))
        matched = [rule for score, rule in ranked if score > 0]
        if not matched:
            matched = [rule for _, rule in ranked]
        matched.sort(key=lambda rule: rule.id)
        source_ids = sorted({item for rule in matched for item in rule.source_refs})
        return self._envelope(
            {
                "task": task,
                "rules": [rule.model_dump(mode="json") for rule in matched],
                "sources": [
                    self._sources[source_id].model_dump(mode="json")
                    for source_id in source_ids
                ],
                "missing": False,
            }
        )

    def sources_for_rule(self, rule: Rule) -> list[Source]:
        return [self._sources[source_id] for source_id in rule.source_refs]

    def envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._envelope(payload)

    def _envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "contract_digest": self._contract_digest,
            "model_digest": self._model_digest,
            **payload,
        }


def diagnostics_payload(report: ValidationReport) -> dict[str, object]:
    return {
        "valid": report.valid,
        "diagnostics": [asdict(item) for item in report.diagnostics],
    }


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value.casefold()))


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _tool_contract() -> dict[str, object]:
    return {
        "model_status": {"arguments": []},
        "context_for_task": {"arguments": ["task"]},
        "policy_check": {"arguments": ["facts", "scope"]},
    }
