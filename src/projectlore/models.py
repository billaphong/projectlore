"""Canonical ProjectLore model contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base contract for canonical model content."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class KnowledgeStatus(StrEnum):
    ASSERTED = "asserted"
    DEPRECATED = "deprecated"
    INFERRED = "inferred"
    SUGGESTED = "suggested"


class LifecycleStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DRAFT = "draft"
    SUPERSEDED = "superseded"


class AuthorityKind(StrEnum):
    PROJECT = "project"
    DOMAIN = "domain"
    EXTERNAL = "external"
    WORKFLOW = "workflow"


class TrustLabel(StrEnum):
    AUTHORITATIVE = "authoritative"
    CORROBORATED = "corroborated"
    UNVERIFIED = "unverified"


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


class Authority(StrictModel):
    kind: AuthorityKind = Field(strict=False)
    reference: str = Field(min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=8192)


class Term(StrictModel):
    id: str | None = Field(default=None, min_length=1)
    value: str = Field(min_length=1, max_length=256)
    meaning: str | None = Field(default=None, max_length=8192)
    preferred: bool = False
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ASSERTED, strict=False)
    lifecycle: LifecycleStatus = Field(default=LifecycleStatus.ACTIVE, strict=False)
    source_refs: list[str] = Field(default_factory=list)


class Source(StrictModel):
    id: str = Field(min_length=1)
    kind: SourceKind = Field(strict=False)
    uri: str | None = Field(default=None, max_length=2048)
    title: str | None = Field(default=None, max_length=512)
    revision: str | None = None
    observed_at: str | None = None
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ASSERTED, strict=False)
    lifecycle: LifecycleStatus = Field(default=LifecycleStatus.ACTIVE, strict=False)
    authority: Authority | None = None
    trust: TrustLabel = Field(default=TrustLabel.UNVERIFIED, strict=False)
    effective_from: str | None = None
    supersedes: str | None = None


class ImplementationAnchor(StrictModel):
    id: str | None = Field(default=None, min_length=1)
    repository: str | None = None
    path: str = Field(min_length=1, max_length=2048)
    symbol: str | None = Field(default=None, max_length=1024)
    revision: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    trust: TrustLabel = Field(default=TrustLabel.UNVERIFIED, strict=False)


class Rule(StrictModel):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1, max_length=16_384)
    kind: RuleKind = Field(strict=False)
    severity: RuleSeverity = Field(strict=False)
    source_refs: list[str] = Field(default_factory=list)
    rationale: str | None = Field(default=None, max_length=16_384)
    remediation: str | None = Field(default=None, max_length=16_384)
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ASSERTED, strict=False)
    lifecycle: LifecycleStatus = Field(default=LifecycleStatus.ACTIVE, strict=False)
    authority: Authority | None = None
    trust: TrustLabel = Field(default=TrustLabel.UNVERIFIED, strict=False)
    effective_from: str | None = None
    superseded_by: str | None = None


class Domain(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=16_384)
    terms: list[Term] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ASSERTED, strict=False)
    lifecycle: LifecycleStatus = Field(default=LifecycleStatus.ACTIVE, strict=False)
    authority: Authority | None = None
    trust: TrustLabel = Field(default=TrustLabel.UNVERIFIED, strict=False)


class Concept(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=512)
    description: str = Field(min_length=1, max_length=16_384)
    domain_ref: str
    terms: list[Term] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)
    implementation_anchors: list[ImplementationAnchor] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ASSERTED, strict=False)
    lifecycle: LifecycleStatus = Field(default=LifecycleStatus.ACTIVE, strict=False)
    authority: Authority | None = None
    trust: TrustLabel = Field(default=TrustLabel.UNVERIFIED, strict=False)
    effective_from: str | None = None
    superseded_by: str | None = None


class Relationship(StrictModel):
    id: str = Field(min_length=1)
    subject_ref: str
    predicate: RelationshipKind = Field(strict=False)
    object_ref: str
    description: str | None = Field(default=None, max_length=16_384)
    source_refs: list[str] = Field(default_factory=list)
    status: KnowledgeStatus = Field(default=KnowledgeStatus.ASSERTED, strict=False)
    lifecycle: LifecycleStatus = Field(default=LifecycleStatus.ACTIVE, strict=False)
    authority: Authority | None = None
    trust: TrustLabel = Field(default=TrustLabel.UNVERIFIED, strict=False)
    effective_from: str | None = None
    superseded_by: str | None = None


class CheckerBinding(StrictModel):
    id: str = Field(min_length=1)
    rule_refs: list[str] = Field(min_length=1)
    checker: str = Field(min_length=1, max_length=1024)
    timeout_seconds: int = Field(default=3, ge=1, le=60)
    source_refs: list[str] = Field(default_factory=list)
    trust: TrustLabel = Field(default=TrustLabel.UNVERIFIED, strict=False)


class ContextProfile(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=16_384)
    domain_refs: list[str] = Field(default_factory=list)
    concept_refs: list[str] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    token_budget: int | None = Field(default=None, ge=1)


class IntegrationManifest(StrictModel):
    manifest_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    checker_bindings: list[CheckerBinding] = Field(default_factory=list)
    context_profiles: list[ContextProfile] = Field(default_factory=list)


class ProjectKnowledgeModel(StrictModel):
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    model_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=16_384)
    domains: list[Domain] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    integration_manifest: IntegrationManifest | None = None
