from __future__ import annotations

from dataclasses import dataclass

import pytest

from projectlore.adapters import (
    MAX_ADAPTER_ANCHORS,
    AdapterError,
    AdapterRegistry,
    CodeGraphAdapter,
    CodeGraphLookup,
    CodeGraphMatch,
)
from projectlore.compiler import ProjectModel, compile_model
from projectlore.models import ImplementationAnchor, ProjectKnowledgeModel


def _project() -> ProjectModel:
    return compile_model(
        ProjectKnowledgeModel.model_validate(
            {
                "schema_version": "0.1.0",
                "model_version": "0.1.0",
                "id": "lore:test",
                "name": "Test",
                "domains": [{"id": "d", "name": "D"}],
                "concepts": [
                    {
                        "id": "c",
                        "name": "Concept",
                        "description": "Meaning",
                        "domain_ref": "d",
                        "implementation_anchors": [
                            {
                                "repository": "repo",
                                "path": "src/current.py",
                                "symbol": "current",
                                "revision": "rev1",
                            },
                            {
                                "repository": "repo",
                                "path": "src/broken.py",
                                "symbol": "broken",
                            },
                        ],
                    }
                ],
                "rules": [
                    {
                        "id": "r",
                        "statement": "Rule",
                        "kind": "invariant",
                        "severity": "error",
                        "implementation_anchors": [
                            {
                                "repository": "repo",
                                "path": "src/rule.py",
                                "symbol": "rule",
                                "revision": "rev1",
                            }
                        ],
                    }
                ],
            }
        )
    )


@dataclass
class _Client:
    state: str = "present"

    def lookup(self, anchor: ImplementationAnchor) -> CodeGraphLookup:
        if self.state != "present":
            return CodeGraphLookup.model_validate(
                {"dependency_state": self.state, "detail": self.state}
            )
        if anchor.path == "src/broken.py":
            return CodeGraphLookup(dependency_state="present", matches=())
        return CodeGraphLookup(
            dependency_state="present",
            repository_revision="rev1",
            matches=(
                CodeGraphMatch(
                    repository="repo",
                    revision="rev1",
                    path=anchor.path,
                    symbol=anchor.symbol,
                    qualified_name=f"repo::{anchor.path}::{anchor.symbol}",
                ),
            ),
        )


def test_registry_is_optional_and_adapter_is_bounded_read_only() -> None:
    assert AdapterRegistry().get("codegraph") is None
    adapter = CodeGraphAdapter(_Client())
    assert AdapterRegistry([adapter]).get("codegraph") is adapter
    assert not hasattr(adapter, "write")
    assert not hasattr(adapter, "mutate")


def test_concept_and_rule_anchors_resolve_with_provenance() -> None:
    resolution = CodeGraphAdapter(_Client()).resolve_anchors(_project())
    resolved = [item for item in resolution.observations if item.state == "resolved"]
    assert {item.owner_kind for item in resolved} == {"concept", "rule"}
    assert all(item.repository == "repo" for item in resolved)
    assert all(item.observed_revision == "rev1" for item in resolved)
    assert resolution.mirrored_graph is False


def test_broken_anchor_is_localized_without_invalidating_resolved_knowledge() -> None:
    resolution = CodeGraphAdapter(_Client()).resolve_anchors(_project())
    states = [item.state for item in resolution.observations]
    assert states.count("broken") == 1
    assert states.count("resolved") == 2
    assert resolution.result_state == "partial"


def test_absent_stale_and_rebuilding_never_become_required_success() -> None:
    for state, expected in (
        ("absent", "unavailable"),
        ("stale", "stale"),
        ("rebuilding", "rebuilding"),
    ):
        adapter = CodeGraphAdapter(_Client(state))
        optional = adapter.resolve_anchors(_project())
        required = adapter.resolve_anchors(_project(), required=True)
        assert {item.state for item in optional.observations} == {expected}
        assert optional.result_state == "partial"
        assert required.result_state == (
            "indeterminate"
            if state in {"absent", "rebuilding"}
            else "partial"
        )


def test_ambiguous_and_path_only_missing_anchors_are_localized() -> None:
    class AmbiguousClient:
        def lookup(self, anchor: ImplementationAnchor) -> CodeGraphLookup:
            match = CodeGraphMatch(
                repository="repo",
                revision="rev1",
                path=anchor.path,
                symbol=anchor.symbol,
                qualified_name="repo::duplicate",
            )
            return CodeGraphLookup(
                dependency_state="present",
                repository_revision="rev1",
                matches=(match, match),
            )

    ambiguous = CodeGraphAdapter(AmbiguousClient()).resolve_anchors(_project())
    assert {item.state for item in ambiguous.observations} == {"ambiguous"}

    model = _project().model.model_copy(
        update={
            "concepts": [
                _project().model.concepts[0].model_copy(
                    update={
                        "implementation_anchors": [
                            ImplementationAnchor(path="docs/missing.md")
                        ]
                    }
                )
            ],
            "rules": [],
        }
    )
    class MissingClient:
        def lookup(self, anchor: ImplementationAnchor) -> CodeGraphLookup:
            return CodeGraphLookup(dependency_state="present", matches=())

    missing = CodeGraphAdapter(MissingClient()).resolve_anchors(compile_model(model))
    assert missing.observations[0].state == "missing"
    assert missing.observations[0].owner_id == "c"


def test_client_failure_is_unavailable_and_required_is_indeterminate() -> None:
    class FailingClient:
        def lookup(self, anchor: ImplementationAnchor) -> CodeGraphLookup:
            raise RuntimeError("dependency offline")

    resolution = CodeGraphAdapter(FailingClient()).resolve_anchors(
        _project(), required=True
    )
    assert resolution.result_state == "indeterminate"
    assert {item.state for item in resolution.observations} == {"unavailable"}


def test_anchor_count_is_bounded_before_any_lookup() -> None:
    calls = 0

    class CountingClient:
        def lookup(self, anchor: ImplementationAnchor) -> CodeGraphLookup:
            nonlocal calls
            calls += 1
            return CodeGraphLookup(dependency_state="present")

    project = _project()
    concept = project.model.concepts[0].model_copy(
        update={
            "implementation_anchors": [
                ImplementationAnchor(path=f"src/{index}.py")
                for index in range(MAX_ADAPTER_ANCHORS + 1)
            ]
        }
    )
    oversized = compile_model(
        project.model.model_copy(update={"concepts": [concept], "rules": []})
    )
    with pytest.raises(AdapterError, match="Anchor count"):
        CodeGraphAdapter(CountingClient()).resolve_anchors(oversized)
    assert calls == 0
