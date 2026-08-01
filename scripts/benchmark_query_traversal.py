"""Reproducible old-scan versus indexed relationship traversal benchmark."""

from __future__ import annotations

import statistics
import time
from collections import deque

from projectlore.compiler import compile_model
from projectlore.models import ProjectKnowledgeModel, Relationship
from projectlore.query import QueryService


def _project(size: int) -> object:
    model = ProjectKnowledgeModel.model_validate(
        {
            "schema_version": "0.1.0",
            "model_version": "0.1.0",
            "id": "benchmark",
            "name": "Benchmark",
            "domains": [{"id": "d", "name": "D"}],
            "concepts": [
                {"id": f"c{i}", "name": f"C{i}", "description": "x", "domain_ref": "d"}
                for i in range(size)
            ],
            "relationships": [
                {
                    "id": f"r{i:05d}",
                    "subject_ref": f"c{i}",
                    "predicate": "relates_to",
                    "object_ref": f"c{(i + 1) % size}",
                }
                for i in range(size)
            ],
        }
    )
    return compile_model(model)


def _scan(relationships: tuple[Relationship, ...]) -> None:
    queue: deque[tuple[str, int]] = deque([("c0", 0)])
    visited = {"c0"}
    selected: set[str] = set()
    while queue:
        current, depth = queue.popleft()
        if depth >= 5:
            continue
        for relationship in sorted(relationships, key=lambda item: item.id):
            next_ids = []
            if relationship.subject_ref == current:
                next_ids.append(relationship.object_ref)
            if relationship.object_ref == current:
                next_ids.append(relationship.subject_ref)
            if next_ids:
                selected.add(relationship.id)
            for next_id in next_ids:
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, depth + 1))


def _median(call: object, runs: int = 20) -> float:
    samples = []
    for _ in range(runs):
        started = time.perf_counter_ns()
        call()  # type: ignore[operator]
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return statistics.median(samples)


def main() -> int:
    large = _project(1200)
    small = _project(40)
    large_query = QueryService(large)  # type: ignore[arg-type]
    small_query = QueryService(small)  # type: ignore[arg-type]
    old_large = _median(lambda: _scan(large.model.relationships))  # type: ignore[attr-defined]
    new_large = _median(
        lambda: large_query.get_relationships("c0", max_depth=5, limit=500)
    )
    old_small = _median(lambda: _scan(small.model.relationships))  # type: ignore[attr-defined]
    new_small = _median(
        lambda: small_query.get_relationships("c0", max_depth=5, limit=500)
    )
    improvement = 1 - new_large / old_large
    small_regression = new_small / old_small - 1
    print(
        {
            "runs": 20,
            "large_nodes": 1200,
            "old_large_median_ms": old_large,
            "new_large_median_ms": new_large,
            "large_improvement": improvement,
            "small_regression": small_regression,
        }
    )
    return 0 if improvement >= 0.30 and small_regression <= 0.05 else 1


if __name__ == "__main__":
    raise SystemExit(main())
