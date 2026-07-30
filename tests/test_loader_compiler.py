from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from projectlore.compiler import compile_model
from projectlore.loader import (
    LoaderError,
    LoaderLimits,
    discover_model,
    load_repository_model,
)
from projectlore.validation import validate_path


def _minimal_model() -> str:
    return """
schema_version: 0.2.0
model_version: 1.0.0
id: lore:test
name: Test
domains: []
concepts: []
relationships: []
rules: []
sources: []
""".lstrip()


def test_loader_rejects_root_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.yaml"
    outside.write_text(_minimal_model(), encoding="utf-8")
    entry = root / "model.yaml"
    entry.write_text("includes: [../outside.yaml]\n", encoding="utf-8")

    with pytest.raises(LoaderError) as error:
        load_repository_model(entry, repository_root=root)

    assert error.value.code == "PL1101"


def test_repository_discovery_is_unambiguous(tmp_path: Path) -> None:
    hidden = tmp_path / ".projectlore"
    hidden.mkdir()
    model = hidden / "model.yaml"
    model.write_text(_minimal_model(), encoding="utf-8")

    assert discover_model(tmp_path) == model.resolve()

    second = tmp_path / "projectlore.yaml"
    second.write_text(_minimal_model(), encoding="utf-8")
    with pytest.raises(LoaderError) as error:
        discover_model(tmp_path)
    assert error.value.code == "PL1108"


def test_loader_rejects_unsafe_yaml_tags(tmp_path: Path) -> None:
    model = tmp_path / "model.yaml"
    model.write_text(
        "value: !!python/object/apply:os.system ['echo unsafe']\n",
        encoding="utf-8",
    )

    with pytest.raises(LoaderError) as error:
        load_repository_model(model)

    assert error.value.code == "PL1001"


def test_loader_enforces_size_depth_and_file_count(tmp_path: Path) -> None:
    large = tmp_path / "large.yaml"
    large.write_text(_minimal_model(), encoding="utf-8")
    with pytest.raises(LoaderError, match="size"):
        load_repository_model(
            large,
            limits=LoaderLimits(maximum_file_bytes=8),
        )

    deep = tmp_path / "deep.yaml"
    deep.write_text("a:\n  b:\n    c: value\n", encoding="utf-8")
    with pytest.raises(LoaderError, match="depth"):
        load_repository_model(deep, limits=LoaderLimits(maximum_depth=1))

    include = tmp_path / "include.yaml"
    include.write_text(_minimal_model(), encoding="utf-8")
    entry = tmp_path / "entry.yaml"
    entry.write_text("includes: [include.yaml]\n", encoding="utf-8")
    with pytest.raises(LoaderError, match="count"):
        load_repository_model(entry, limits=LoaderLimits(maximum_files=1))


def test_diagnostics_include_file_line_and_column(tmp_path: Path) -> None:
    model = tmp_path / "invalid.yaml"
    model.write_text(
        _minimal_model().replace("name: Test", "name: Test\nunexpected: true"),
        encoding="utf-8",
    )

    _, report = validate_path(model)

    assert not report.valid
    diagnostic = report.diagnostics[0]
    assert diagnostic.code == "PL1001"
    assert diagnostic.file == str(model.resolve())
    assert diagnostic.line == 5
    assert diagnostic.column == 13


def test_compiler_is_byte_deterministic_and_model_is_frozen(tmp_path: Path) -> None:
    model_path = tmp_path / "model.yaml"
    model_path.write_text(_minimal_model(), encoding="utf-8")
    model, report = validate_path(model_path)
    assert report.valid
    assert model is not None

    first = compile_model(model)
    second = compile_model(model)

    assert first.normalized_json == second.normalized_json
    assert first.digest == second.digest
    with pytest.raises(ValidationError):
        model.name = "Changed"


def test_included_diagnostic_points_to_included_file(tmp_path: Path) -> None:
    entry = tmp_path / "model.yaml"
    entry.write_text(
        _minimal_model().replace(
            "domains: []",
            "includes: [domain.yaml]\ndomains: []",
        ),
        encoding="utf-8",
    )
    include = tmp_path / "domain.yaml"
    include.write_text(
        """
domains:
  - id: lore:test/domain
    name: Domain
    source_refs: [lore:test/missing]
""".lstrip(),
        encoding="utf-8",
    )

    _, report = validate_path(entry)

    diagnostic = next(item for item in report.diagnostics if item.code == "PL2002")
    assert diagnostic.file == str(include.resolve())
    assert diagnostic.line == 4


def test_semantics_reject_version_source_and_authority_conflicts(
    tmp_path: Path,
) -> None:
    model = tmp_path / "conflicts.yaml"
    model.write_text(
        """
schema_version: 1.0.0
model_version: 1.0.0
id: lore:test
name: Test
domains: []
concepts: []
relationships: []
rules: []
sources:
  - id: lore:test/source-a
    kind: external
    uri: https://example.invalid/source
    revision: one
    authority:
      kind: external
      reference: https://example.invalid
    trust: authoritative
  - id: lore:test/source-b
    kind: external
    uri: https://example.invalid/source
    revision: two
""".lstrip(),
        encoding="utf-8",
    )

    _, report = validate_path(model)

    assert {item.code for item in report.diagnostics} == {
        "PL2301",
        "PL2302",
        "PL2303",
    }
