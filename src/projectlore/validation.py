"""Structural and whole-model validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from projectlore.loader import (
    LoadedDocument,
    LoaderError,
    SourceLocation,
    load_repository_model,
)
from projectlore.models import (
    Authority,
    AuthorityKind,
    LifecycleStatus,
    ProjectKnowledgeModel,
    TrustLabel,
)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: str
    file: str | None = None
    line: int | None = None
    column: int | None = None


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
    return load_repository_model(path).value


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
        loaded = load_repository_model(path)
    except LoaderError as error:
        return None, ValidationReport(
            valid=False,
            diagnostics=(
                Diagnostic(
                    error.code,
                    str(error),
                    "$",
                    str(error.file),
                    error.line,
                    error.column,
                ),
            ),
        )
    model, report = validate_document(loaded.value)
    return model, _locate_diagnostics(report, loaded)


def _locate_diagnostics(
    report: ValidationReport,
    loaded: LoadedDocument,
) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    for item in report.diagnostics:
        location = _nearest_location(loaded, item.path)
        diagnostics.append(
            Diagnostic(
                code=item.code,
                message=item.message,
                path=item.path,
                file=None if location is None else str(location.file),
                line=None if location is None else location.line,
                column=None if location is None else location.column,
            )
        )
    return ValidationReport(valid=report.valid, diagnostics=tuple(diagnostics))


def _nearest_location(
    loaded: LoadedDocument,
    model_path: str,
) -> SourceLocation | None:
    candidate = model_path
    while candidate:
        location = loaded.locations.get(candidate) or loaded.locations.get(
            f"$.{candidate}"
        )
        if location is not None:
            return location
        candidate = candidate.rpartition(".")[0]
    return loaded.locations.get("$")


def _semantic_diagnostics(model: ProjectKnowledgeModel) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not model.schema_version.startswith("0."):
        diagnostics.append(
            Diagnostic(
                "PL2301",
                f"Unsupported schema version {model.schema_version!r}.",
                "schema_version",
            )
        )
    entity_ids: dict[str, str] = {}

    groups: list[tuple[str, list[str]]] = [
        ("domains", [entity.id for entity in model.domains]),
        ("concepts", [entity.id for entity in model.concepts]),
        ("relationships", [entity.id for entity in model.relationships]),
        ("rules", [entity.id for entity in model.rules]),
        ("sources", [entity.id for entity in model.sources]),
    ]
    if model.integration_manifest is not None:
        groups.extend(
            [
                (
                    "integration_manifest.checker_bindings",
                    [item.id for item in model.integration_manifest.checker_bindings],
                ),
                (
                    "integration_manifest.context_profiles",
                    [item.id for item in model.integration_manifest.context_profiles],
                ),
            ]
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

    for index, domain in enumerate(model.domains):
        _require_sources(
            diagnostics,
            domain.source_refs,
            source_ids,
            f"domains.{index}",
        )

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
        _require_supersession(
            diagnostics,
            concept.lifecycle,
            concept.superseded_by,
            concept_ids,
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
        _require_supersession(
            diagnostics,
            relationship.lifecycle,
            relationship.superseded_by,
            {item.id for item in model.relationships},
            f"relationships.{index}",
        )

    for index, rule in enumerate(model.rules):
        _require_sources(diagnostics, rule.source_refs, source_ids, f"rules.{index}")
        _require_supersession(
            diagnostics,
            rule.lifecycle,
            rule.superseded_by,
            rule_ids,
            f"rules.{index}",
        )

    for index, source in enumerate(model.sources):
        if source.supersedes is not None:
            _require_ref(
                diagnostics,
                source.supersedes,
                source_ids,
                f"sources.{index}.supersedes",
            )
        _require_authority_boundary(
            diagnostics,
            source.authority,
            source.trust,
            f"sources.{index}",
        )

    source_claims: dict[str, tuple[str | None, str]] = {}
    for index, source in enumerate(model.sources):
        if source.uri is None:
            continue
        source_prior = source_claims.get(source.uri)
        if source_prior is not None and source_prior[0] != source.revision:
            diagnostics.append(
                Diagnostic(
                    "PL2302",
                    (
                        f"Source URI {source.uri!r} has conflicting revisions "
                        f"{source_prior[0]!r} and {source.revision!r}."
                    ),
                    f"sources.{index}.revision",
                )
            )
        else:
            source_claims[source.uri] = (source.revision, source.id)

    manifest = model.integration_manifest
    if manifest is not None:
        for index, binding in enumerate(manifest.checker_bindings):
            path = f"integration_manifest.checker_bindings.{index}"
            for ref_index, reference in enumerate(binding.rule_refs):
                _require_ref(
                    diagnostics,
                    reference,
                    rule_ids,
                    f"{path}.rule_refs.{ref_index}",
                )
            _require_sources(diagnostics, binding.source_refs, source_ids, path)
        for index, profile in enumerate(manifest.context_profiles):
            path = f"integration_manifest.context_profiles.{index}"
            _require_refs(
                diagnostics, profile.domain_refs, domain_ids, f"{path}.domain_refs"
            )
            _require_refs(
                diagnostics, profile.concept_refs, concept_ids, f"{path}.concept_refs"
            )
            _require_refs(diagnostics, profile.rule_refs, rule_ids, f"{path}.rule_refs")
            _require_sources(diagnostics, profile.source_refs, source_ids, path)

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


def _require_refs(
    diagnostics: list[Diagnostic],
    references: list[str],
    valid_ids: set[str],
    path: str,
) -> None:
    for index, reference in enumerate(references):
        _require_ref(diagnostics, reference, valid_ids, f"{path}.{index}")


def _require_supersession(
    diagnostics: list[Diagnostic],
    lifecycle: LifecycleStatus,
    superseded_by: str | None,
    valid_ids: set[str],
    path: str,
) -> None:
    if lifecycle is LifecycleStatus.SUPERSEDED and superseded_by is None:
        diagnostics.append(
            Diagnostic(
                "PL2201",
                "Superseded knowledge must identify its replacement.",
                f"{path}.superseded_by",
            )
        )
    if superseded_by is not None:
        _require_ref(diagnostics, superseded_by, valid_ids, f"{path}.superseded_by")


def _require_authority_boundary(
    diagnostics: list[Diagnostic],
    authority: Authority | None,
    trust: TrustLabel,
    path: str,
) -> None:
    if (
        authority is not None
        and authority.kind is AuthorityKind.EXTERNAL
        and trust is TrustLabel.AUTHORITATIVE
    ):
        diagnostics.append(
            Diagnostic(
                "PL2303",
                "External material cannot declare itself project-authoritative.",
                f"{path}.trust",
            )
        )
