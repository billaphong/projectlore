from __future__ import annotations

from collections import deque

import pytest

from projectlore.compiler import compile_model
from projectlore.models import ProjectKnowledgeModel, Relationship
from projectlore.query import QueryService


def _query() -> QueryService:
    model = ProjectKnowledgeModel.model_validate(
        {
            "schema_version": "0.1.0",
            "model_version": "0.1.0",
            "id": "graph",
            "name": "Graph",
            "domains": [{"id": "d", "name": "D"}],
            "sources": [
                {"id": "s:a", "kind": "documentation", "uri": "file:a"},
                {"id": "s:b", "kind": "documentation", "uri": "file:b"},
            ],
            "concepts": [
                {"id": item, "name": item, "description": item, "domain_ref": "d"}
                for item in ("a", "b", "c", "d", "isolated")
            ],
            "relationships": [
                {
                    "id": "r:4",
                    "subject_ref": "c",
                    "predicate": "relates_to",
                    "object_ref": "a",
                    "source_refs": ["s:b"],
                },
                {
                    "id": "r:1",
                    "subject_ref": "a",
                    "predicate": "relates_to",
                    "object_ref": "b",
                    "source_refs": ["s:b"],
                },
                {
                    "id": "r:3",
                    "subject_ref": "b",
                    "predicate": "relates_to",
                    "object_ref": "c",
                    "source_refs": ["s:a"],
                },
                {
                    "id": "r:2",
                    "subject_ref": "b",
                    "predicate": "relates_to",
                    "object_ref": "b",
                    "source_refs": ["s:a"],
                },
                {
                    "id": "r:5",
                    "subject_ref": "a",
                    "predicate": "relates_to",
                    "object_ref": "d",
                },
            ],
        }
    )
    return QueryService(compile_model(model))


def _reference(
    relationships: tuple[Relationship, ...],
    concept: str,
    direction: str,
    depth: int,
    limit: int,
) -> tuple[list[str], bool]:
    queue: deque[tuple[str, int]] = deque([(concept, 0)])
    visited = {concept}
    selected: list[str] = []
    seen: set[str] = set()
    while queue and len(selected) < limit:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for relationship in sorted(relationships, key=lambda item: item.id):
            next_ids = []
            if (
                direction in {"outgoing", "both"}
                and relationship.subject_ref == current
            ):
                next_ids.append(relationship.object_ref)
            if direction in {"incoming", "both"} and relationship.object_ref == current:
                next_ids.append(relationship.subject_ref)
            if not next_ids:
                continue
            if relationship.id not in seen:
                selected.append(relationship.id)
                seen.add(relationship.id)
                if len(selected) == limit:
                    break
            for next_id in next_ids:
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, current_depth + 1))
    return selected, bool(queue) or len(selected) == limit


@pytest.mark.parametrize("direction", ["incoming", "outgoing", "both"])
@pytest.mark.parametrize("depth", [1, 2, 5])
@pytest.mark.parametrize("limit", [1, 3, 100])
def test_indexed_traversal_matches_reference(
    direction: str, depth: int, limit: int
) -> None:
    query = _query()
    result = query.get_relationships(
        "a", direction=direction, max_depth=depth, limit=limit
    )  # type: ignore[arg-type]
    expected, truncated = _reference(
        query.model.relationships, "a", direction, depth, limit
    )
    assert [item["id"] for item in result["relationships"]] == expected
    assert result["truncated"] is truncated
    assert [item["id"] for item in result["provenance"]] == sorted(
        {ref for item in result["relationships"] for ref in item["source_refs"]}
    )


def test_missing_and_isolated_concepts_remain_distinct() -> None:
    query = _query()
    assert query.get_relationships("missing")["result_state"] == "not_found"
    assert query.get_relationships("isolated")["result_state"] == "empty"
