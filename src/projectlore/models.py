"""Canonical ProjectLore model contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base contract for canonical model content."""

    model_config = ConfigDict(extra="forbid", strict=True)


class KnowledgeStatus(StrEnum):
    ASSERTED = "asserted"
    DEPRECATED = "deprecated"
    INFERRED = "inferred"
    SUGGESTED = "suggested"


class SourceKind(StrEnum):
    ASSERTION = "assertion"
    CODE = "code"
    DECISION = "decision"
    DOCUMENTATION = "documentation"
    EXTERNAL = "external"
    INFERENCE = "inference"
    SPECIFICATION = "specification"
    WORK = "work"


class RuleKind(StrEnum):
    ADVISORY = "advisory"
    CONVENTION = "convention"
    INVARIANT = "invariant"
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"


class RuleSeverity(StrEnum):
    BLOCKER = "blocker"
    ERROR = "error"
    INFO = "info"
    WARNING = "warning"


class RelationshipKind(StrEnum):
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    GOVERNS = "governs"
    IMPLEMENTS = "implements"
    IS_A = "is_a"
    RELATES_TO = "relates_to"
    SUPERSEDES = "supersedes"
    VALIDATES = "validates"


class Term(StrictModel):
    value: str = Field(min_length=1)
    meaning: str | None = None
    preferred: bool = False
    status: KnowledgeStatus = KnowledgeStatus.ASSERTED


class Source(StrictModel):
    id: str = Field(min_length=1)
    kind: SourceKind = Field(strict=False)
    uri: str | None = None
    title: str | None = None
    revision: str | None = None
    observed_at: str | None = None
    status: KnowledgeStatus = KnowledgeStatus.ASSERTED
    supersedes: str | None = None


class ImplementationAnchor(StrictModel):
    repository: str | None = None
    path: str = Field(min_length=1)
    symbol: str | None = None
    revision: str | None = None


class Rule(StrictModel):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    kind: RuleKind = Field(strict=False)
    severity: RuleSeverity = Field(strict=False)
    source_refs: list[str] = Field(default_factory=list)
    rationale: str | None = None
    remediation: str | None = None
    status: KnowledgeStatus = KnowledgeStatus.ASSERTED


class Domain(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    terms: list[Term] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class Concept(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    domain_ref: str
    terms: list[Term] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)
    implementation_anchors: list[ImplementationAnchor] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    status: KnowledgeStatus = KnowledgeStatus.ASSERTED


class Relationship(StrictModel):
    id: str = Field(min_length=1)
    subject_ref: str
    predicate: RelationshipKind = Field(strict=False)
    object_ref: str
    description: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    status: KnowledgeStatus = KnowledgeStatus.ASSERTED


class ProjectKnowledgeModel(StrictModel):
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    model_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    domains: list[Domain] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
