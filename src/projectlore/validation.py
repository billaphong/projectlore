"""Structural and whole-model validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from projectlore.models import ProjectKnowledgeModel


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: str


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    diagnostics: tuple[Diagnostic, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "diagnostics": [asdict(item) for item in self.diagnostics],
        }


def load_document(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Project knowledge model not found: {path}")
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def validate_document(
    document: Any,
) -> tuple[ProjectKnowledgeModel | None, ValidationReport]:
    try:
        model = ProjectKnowledgeModel.model_validate(document)
    except ValidationError as error:
        structural_diagnostics = tuple(
            Diagnostic(
                code="PL1001",
                message=item["msg"],
                path=".".join(str(part) for part in item["loc"]),
            )
            for item in error.errors()
        )
        return None, ValidationReport(
            valid=False,
            diagnostics=structural_diagnostics,
        )

    diagnostics = _semantic_diagnostics(model)
    return model, ValidationReport(
        valid=not diagnostics,
        diagnostics=tuple(diagnostics),
    )


def validate_path(path: Path) -> tuple[ProjectKnowledgeModel | None, ValidationReport]:
    try:
        document = load_document(path)
    except yaml.YAMLError as error:
        return None, ValidationReport(
            valid=False,
            diagnostics=(Diagnostic("PL1001", str(error), "$"),),
        )
    return validate_document(document)


def _semantic_diagnostics(model: ProjectKnowledgeModel) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    entity_ids: dict[str, str] = {}

    groups = (
        ("domains", [entity.id for entity in model.domains]),
        ("concepts", [entity.id for entity in model.concepts]),
        ("relationships", [entity.id for entity in model.relationships]),
        ("rules", [entity.id for entity in model.rules]),
        ("sources", [entity.id for entity in model.sources]),
    )
    for group_name, identifiers in groups:
        for index, identifier in enumerate(identifiers):
            prior = entity_ids.get(identifier)
            if prior is not None:
                diagnostics.append(
                    Diagnostic(
                        "PL2001",
                        (
                            f"Duplicate identifier {identifier!r}; "
                            f"first declared at {prior}."
                        ),
                        f"{group_name}.{index}.id",
                    )
                )
            else:
                entity_ids[identifier] = f"{group_name}.{index}.id"

    domain_ids = {item.id for item in model.domains}
    concept_ids = {item.id for item in model.concepts}
    rule_ids = {item.id for item in model.rules}
    source_ids = {item.id for item in model.sources}

    for index, concept in enumerate(model.concepts):
        _require_ref(
            diagnostics,
            concept.domain_ref,
            domain_ids,
            f"concepts.{index}.domain_ref",
        )
        for ref_index, reference in enumerate(concept.rule_refs):
            _require_ref(
                diagnostics,
                reference,
                rule_ids,
                f"concepts.{index}.rule_refs.{ref_index}",
            )
        _require_sources(
            diagnostics,
            concept.source_refs,
            source_ids,
            f"concepts.{index}",
        )

    for index, relationship in enumerate(model.relationships):
        _require_ref(
            diagnostics,
            relationship.subject_ref,
            concept_ids,
            f"relationships.{index}.subject_ref",
        )
        _require_ref(
            diagnostics,
            relationship.object_ref,
            concept_ids,
            f"relationships.{index}.object_ref",
        )
        _require_sources(
            diagnostics,
            relationship.source_refs,
            source_ids,
            f"relationships.{index}",
        )

    for index, rule in enumerate(model.rules):
        _require_sources(diagnostics, rule.source_refs, source_ids, f"rules.{index}")

    for index, source in enumerate(model.sources):
        if source.supersedes is not None:
            _require_ref(
                diagnostics,
                source.supersedes,
                source_ids,
                f"sources.{index}.supersedes",
            )

    return diagnostics


def _require_ref(
    diagnostics: list[Diagnostic],
    reference: str,
    valid_ids: set[str],
    path: str,
) -> None:
    if reference not in valid_ids:
        diagnostics.append(
            Diagnostic("PL2002", f"Dangling reference {reference!r}.", path)
        )


def _require_sources(
    diagnostics: list[Diagnostic],
    references: list[str],
    source_ids: set[str],
    path: str,
) -> None:
    if not references:
        diagnostics.append(
            Diagnostic("PL2101", "At least one provenance source is required.", path)
        )
    for index, reference in enumerate(references):
        _require_ref(diagnostics, reference, source_ids, f"{path}.source_refs.{index}")
