"""Optional, read-only ecosystem adapter contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, Protocol

from projectlore.compiler import ProjectModel
from projectlore.models import ImplementationAnchor, StrictModel

MAX_ADAPTER_ANCHORS = 1024
MAX_ADAPTER_MATCHES = 16


class AdapterError(RuntimeError):
    """Raised when an adapter registration violates the local boundary."""


class CodeGraphMatch(StrictModel):
    repository: str
    revision: str
    path: str
    symbol: str | None
    qualified_name: str


class CodeGraphLookup(StrictModel):
    dependency_state: Literal["present", "absent", "stale", "rebuilding"]
    repository_revision: str | None = None
    matches: tuple[CodeGraphMatch, ...] = ()
    detail: str | None = None


class ReadOnlyCodeGraphClient(Protocol):
    """Narrow lookup-only client; no mutation capability is exposed."""

    def lookup(self, anchor: ImplementationAnchor) -> CodeGraphLookup: ...


class AnchorObservation(StrictModel):
    observation_version: Literal["projectlore-anchor-observation/0.1.0"]
    owner_kind: Literal["concept", "rule"]
    owner_id: str
    repository: str | None
    requested_revision: str | None
    observed_revision: str | None
    path: str
    symbol: str | None
    state: Literal[
        "resolved",
        "broken",
        "stale",
        "ambiguous",
        "missing",
        "unavailable",
        "rebuilding",
    ]
    symbol_ref: str | None
    observed_at: datetime
    evidence_digest: str
    diagnostic: str | None


class AnchorResolution(StrictModel):
    resolution_version: Literal["projectlore-anchor-resolution/0.1.0"]
    adapter: Literal["codegraph"]
    required: bool
    result_state: Literal["complete", "partial", "indeterminate"]
    observations: tuple[AnchorObservation, ...]
    mirrored_graph: Literal[False] = False


class KnowledgeAdapter(Protocol):
    @property
    def name(self) -> str: ...

    def resolve_anchors(
        self, project: ProjectModel, *, required: bool = False
    ) -> AnchorResolution: ...


class AdapterRegistry:
    """Immutable registry that keeps optional adapters outside core semantics."""

    def __init__(self, adapters: Sequence[KnowledgeAdapter] = ()) -> None:
        entries = {adapter.name: adapter for adapter in adapters}
        if len(entries) != len(adapters):
            raise AdapterError("Adapter names must be unique.")
        self._entries = entries

    def get(self, name: str) -> KnowledgeAdapter | None:
        return self._entries.get(name)


class CodeGraphAdapter:
    """Resolve stable anchors through bounded read-only CodeGraph lookups."""

    name = "codegraph"

    def __init__(self, client: ReadOnlyCodeGraphClient) -> None:
        self._client = client

    def resolve_anchors(
        self, project: ProjectModel, *, required: bool = False
    ) -> AnchorResolution:
        owned: list[
            tuple[Literal["concept", "rule"], str, ImplementationAnchor]
        ] = [
            ("concept", concept.id, anchor)
            for concept in project.model.concepts
            for anchor in concept.implementation_anchors
        ] + [
            ("rule", rule.id, anchor)
            for rule in project.model.rules
            for anchor in rule.implementation_anchors
        ]
        if len(owned) > MAX_ADAPTER_ANCHORS:
            raise AdapterError(
                f"Anchor count exceeds adapter bound {MAX_ADAPTER_ANCHORS}."
            )
        observations = tuple(
            self._observe(owner_kind, owner_id, anchor)
            for owner_kind, owner_id, anchor in owned
        )
        unresolved = any(item.state != "resolved" for item in observations)
        dependency_failure = any(
            item.state in {"unavailable", "rebuilding"} for item in observations
        )
        if required and dependency_failure:
            result_state: Literal["complete", "partial", "indeterminate"] = (
                "indeterminate"
            )
        elif unresolved:
            result_state = "partial"
        else:
            result_state = "complete"
        return AnchorResolution(
            resolution_version="projectlore-anchor-resolution/0.1.0",
            adapter="codegraph",
            required=required,
            result_state=result_state,
            observations=observations,
            mirrored_graph=False,
        )

    def _observe(
        self,
        owner_kind: Literal["concept", "rule"],
        owner_id: str,
        anchor: ImplementationAnchor,
    ) -> AnchorObservation:
        try:
            lookup = self._client.lookup(anchor)
        except Exception as error:
            lookup = CodeGraphLookup(
                dependency_state="absent",
                detail=f"CodeGraph lookup failed: {type(error).__name__}",
            )
        matches = lookup.matches[: MAX_ADAPTER_MATCHES + 1]
        state, match, diagnostic = _classify(anchor, lookup, matches)
        symbol_ref = match.qualified_name if match is not None else None
        content = {
            "owner_kind": owner_kind,
            "owner_id": owner_id,
            "repository": anchor.repository,
            "requested_revision": anchor.revision,
            "observed_revision": lookup.repository_revision,
            "path": anchor.path,
            "symbol": anchor.symbol,
            "state": state,
            "symbol_ref": symbol_ref,
            "diagnostic": diagnostic,
        }
        encoded = json.dumps(
            content, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        return AnchorObservation(
            observation_version="projectlore-anchor-observation/0.1.0",
            owner_kind=owner_kind,
            owner_id=owner_id,
            repository=anchor.repository,
            requested_revision=anchor.revision,
            observed_revision=lookup.repository_revision,
            path=anchor.path,
            symbol=anchor.symbol,
            state=state,
            symbol_ref=symbol_ref,
            observed_at=datetime.now(UTC),
            evidence_digest=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
            diagnostic=diagnostic,
        )


def _classify(
    anchor: ImplementationAnchor,
    lookup: CodeGraphLookup,
    matches: tuple[CodeGraphMatch, ...],
) -> tuple[
    Literal[
        "resolved",
        "broken",
        "stale",
        "ambiguous",
        "missing",
        "unavailable",
        "rebuilding",
    ],
    CodeGraphMatch | None,
    str | None,
]:
    if lookup.dependency_state == "absent":
        return "unavailable", None, lookup.detail or "CodeGraph is unavailable."
    if lookup.dependency_state == "rebuilding":
        return "rebuilding", None, lookup.detail or "CodeGraph is rebuilding."
    if lookup.dependency_state == "stale":
        return "stale", None, lookup.detail or "CodeGraph index is stale."
    if len(matches) > 1:
        return "ambiguous", None, "Anchor resolves to multiple current symbols."
    if not matches:
        return (
            "broken" if anchor.symbol else "missing",
            None,
            "Anchor does not resolve to a current symbol.",
        )
    match = matches[0]
    if anchor.revision and match.revision != anchor.revision:
        return "stale", match, "Anchor revision differs from repository revision."
    return "resolved", match, None
