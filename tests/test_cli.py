from pathlib import Path

import pytest

from projectlore.cli import main, model_status
from projectlore.schema import render_json_schema, schema_matches
from projectlore.validation import validate_path


def test_model_status_counts_example_entities() -> None:
    model = Path(__file__).parents[1] / "examples" / "homebrew.project.yaml"

    status = model_status(model)

    assert status["project"] == "Homebrew"
    assert status["domains"] == 1
    assert status["concepts"] == 2
    assert status["relationships"] == 1


def test_model_status_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        model_status(tmp_path / "missing.yaml")


def test_example_validates() -> None:
    model = Path(__file__).parents[1] / "examples" / "homebrew.project.yaml"

    _, report = validate_path(model)

    assert report.valid, report.diagnostics


def test_semantic_validation_rejects_dangling_reference(tmp_path: Path) -> None:
    model = tmp_path / "invalid.yaml"
    model.write_text(
        """
schema_version: 0.1.0
model_version: 0.1.0
id: lore:test
name: Test
domains: []
concepts:
  - id: lore:test/concept
    name: Concept
    description: Test concept.
    domain_ref: lore:test/missing-domain
    source_refs:
      - lore:test/missing-source
relationships: []
rules: []
sources: []
""".lstrip(),
        encoding="utf-8",
    )

    _, report = validate_path(model)

    assert not report.valid
    assert {item.code for item in report.diagnostics} == {"PL2002"}


def test_semantic_validation_rejects_duplicate_id_and_missing_provenance(
    tmp_path: Path,
) -> None:
    model = tmp_path / "invalid.yaml"
    model.write_text(
        """
schema_version: 0.1.0
model_version: 0.1.0
id: lore:test
name: Test
domains:
  - id: lore:test/domain
    name: Domain
  - id: lore:test/domain
    name: Duplicate
concepts:
  - id: lore:test/concept
    name: Concept
    description: Test concept.
    domain_ref: lore:test/domain
relationships: []
rules: []
sources: []
""".lstrip(),
        encoding="utf-8",
    )

    _, report = validate_path(model)

    assert not report.valid
    assert {item.code for item in report.diagnostics} == {"PL2001", "PL2101"}


def test_validate_command_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        main(["validate", str(tmp_path / "missing.yaml")])

    assert error.value.code == 2


def test_generated_schema_is_deterministic(tmp_path: Path) -> None:
    schema = tmp_path / "projectlore.schema.json"
    schema.write_text(render_json_schema(), encoding="utf-8")

    assert schema_matches(schema)


def test_committed_schema_has_no_drift() -> None:
    schema = (
        Path(__file__).parents[1] / "schemas" / "projectlore.schema.json"
    )

    assert schema_matches(schema)
