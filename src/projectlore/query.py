"""Transport-independent queries over an immutable compiled model."""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from typing import Any, Literal

from projectlore.compiler import ProjectModel
from projectlore.models import Concept, Relationship, Rule, Source
from projectlore.tool_spec import TOOL_INPUT_SCHEMAS, TOOLS_CONTRACT_VERSION

CONTRACT_VERSION = TOOLS_CONTRACT_VERSION
_TOKEN = re.compile(r"[a-z0-9_]+")


class QueryService:
    """Pure, bounded query operations over one immutable ProjectModel."""

    def __init__(self, project: ProjectModel) -> None:
        self.project = project
        self.model = project.model
        self._concepts = {item.id: item for item in self.model.concepts}
        self._sources = {item.id: item for item in self.model.sources}
        self._contract_digest = _digest(
            {"contract_version": CONTRACT_VERSION, "tools": TOOL_INPUT_SCHEMAS}
        )

    def envelope(
        self,
        payload: dict[str, Any],
        *,
        result_state: Literal[
            "found", "not_found", "ambiguous", "empty", "complete"
        ] = "complete",
        provenance: list[Source] | None = None,
    ) -> dict[str, Any]:
        sources = provenance or []
        return {
            "contract_version": CONTRACT_VERSION,
            "contract_digest": self._contract_digest,
            "model_digest": self.project.digest,
            "freshness": {
                "state": "compiled",
                "model_version": self.model.model_version,
            },
            "authority": _authority_summary(sources),
            "result_state": result_state,
            "provenance": [item.model_dump(mode="json") for item in sources],
            **payload,
        }

    def model_status(self) -> dict[str, Any]:
        return self.envelope(
            {
                "model_id": self.model.id,
                "model_version": self.model.model_version,
                "schema_version": self.model.schema_version,
                "counts": {
                    "domains": len(self.model.domains),
                    "concepts": len(self.model.concepts),
                    "relationships": len(self.model.relationships),
                    "rules": len(self.model.rules),
                    "sources": len(self.model.sources),
                },
            }
        )

    def search(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        limit = _bounded(limit, 1, 100, "limit")
        query_tokens = _tokens(query)
        candidates: list[tuple[int, str, str, Any]] = []
        for kind, values in (
            ("concept", self.model.concepts),
            ("rule", self.model.rules),
            ("domain", self.model.domains),
        ):
            for item in values:
                text = json.dumps(item.model_dump(mode="json"), sort_keys=True)
                score = len(query_tokens & _tokens(text))
                if score:
                    candidates.append((score, kind, item.id, item))
        candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
        selected = candidates[:limit]
        sources = self._provenance(
            ref
            for _, _, _, item in selected
            for ref in getattr(item, "source_refs", [])
        )
        return self.envelope(
            {
                "query": query,
                "results": [
                    {
                        "kind": kind,
                        "score": score,
                        "item": item.model_dump(mode="json"),
                    }
                    for score, kind, _, item in selected
                ],
                "truncated": len(candidates) > limit,
            },
            result_state="found" if selected else "empty",
            provenance=sources,
        )

    def get_concept(self, concept_id: str) -> dict[str, Any]:
        concept = self._concepts.get(concept_id)
        if concept is None:
            return self.envelope(
                {"concept_id": concept_id, "concept": None},
                result_state="not_found",
            )
        return self.envelope(
            {"concept_id": concept_id, "concept": concept.model_dump(mode="json")},
            result_state="found",
            provenance=self._provenance(concept.source_refs),
        )

    def resolve_term(self, term: str) -> dict[str, Any]:
        folded = term.casefold().strip()
        matches: list[Concept] = []
        for concept in self.model.concepts:
            values = {concept.name.casefold(), concept.id.casefold()}
            values.update(item.value.casefold() for item in concept.terms)
            if folded in values:
                matches.append(concept)
        matches.sort(key=lambda item: item.id)
        state: Literal["found", "not_found", "ambiguous"]
        if not matches:
            state = "not_found"
        elif len(matches) == 1:
            state = "found"
        else:
            state = "ambiguous"
        return self.envelope(
            {
                "term": term,
                "matches": [item.model_dump(mode="json") for item in matches],
            },
            result_state=state,
            provenance=self._provenance(
                ref for item in matches for ref in item.source_refs
            ),
        )

    def get_relationships(
        self,
        concept_id: str,
        *,
        direction: Literal["incoming", "outgoing", "both"] = "both",
        max_depth: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        max_depth = _bounded(max_depth, 1, 5, "max_depth")
        limit = _bounded(limit, 1, 500, "limit")
        if concept_id not in self._concepts:
            return self.envelope(
                {"concept_id": concept_id, "relationships": [], "truncated": False},
                result_state="not_found",
            )
        queue: deque[tuple[str, int]] = deque([(concept_id, 0)])
        visited = {concept_id}
        selected: list[Relationship] = []
        seen_relationships: set[str] = set()
        while queue and len(selected) < limit:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            relationships = sorted(
                self.model.relationships, key=lambda item: item.id
            )
            for relationship in relationships:
                next_ids: list[str] = []
                if (
                    direction in {"outgoing", "both"}
                    and relationship.subject_ref == current
                ):
                    next_ids.append(relationship.object_ref)
                if (
                    direction in {"incoming", "both"}
                    and relationship.object_ref == current
                ):
                    next_ids.append(relationship.subject_ref)
                if not next_ids:
                    continue
                if relationship.id not in seen_relationships:
                    selected.append(relationship)
                    seen_relationships.add(relationship.id)
                    if len(selected) == limit:
                        break
                for next_id in next_ids:
                    if next_id not in visited:
                        visited.add(next_id)
                        queue.append((next_id, depth + 1))
        return self.envelope(
            {
                "concept_id": concept_id,
                "relationships": [
                    item.model_dump(mode="json") for item in selected
                ],
                "truncated": bool(queue) or len(selected) == limit,
                "max_depth": max_depth,
            },
            result_state="found" if selected else "empty",
            provenance=self._provenance(
                ref for item in selected for ref in item.source_refs
            ),
        )

    def context_for_task(self, task: str, *, limit: int = 20) -> dict[str, Any]:
        limit = _bounded(limit, 1, 100, "limit")
        task_tokens = _tokens(task)
        ranked: list[tuple[int, Rule]] = []
        for rule in self.model.rules:
            text = " ".join(
                (
                    rule.id,
                    rule.statement,
                    rule.rationale or "",
                    rule.remediation or "",
                )
            )
            score = len(task_tokens & _tokens(text))
            if score:
                ranked.append((score, rule))
        ranked.sort(key=lambda row: (-row[0], row[1].id))
        matched = [rule for _, rule in ranked[:limit]]
        sources = self._provenance(
            ref for rule in matched for ref in rule.source_refs
        )
        return self.envelope(
            {
                "task": task,
                "rules": [rule.model_dump(mode="json") for rule in matched],
                "truncated": len(ranked) > limit,
                "missing": not matched,
            },
            result_state="found" if matched else "empty",
            provenance=sources,
        )

    def _provenance(self, source_refs: Any) -> list[Source]:
        return [
            self._sources[source_id]
            for source_id in sorted(set(source_refs))
            if source_id in self._sources
        ]


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value.casefold()))


def _bounded(value: int, minimum: int, maximum: int, name: str) -> int:
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _digest(value: object) -> str:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _authority_summary(sources: list[Source]) -> dict[str, object]:
    return {
        "source_count": len(sources),
        "trust": sorted({source.trust.value for source in sources}),
        "kinds": sorted(
            {
                source.authority.kind.value
                for source in sources
                if source.authority is not None
            }
        ),
    }
