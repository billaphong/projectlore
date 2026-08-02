"""Strict acquisition workflow contracts used by the storage kernel."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class AcquisitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class GenerationState(StrEnum):
    PENDING = "pending"
    OUTSTANDING = "outstanding"
    REVIEWED = "reviewed"
    COMMIT_CLAIMED = "commit_claimed"
    TERMINAL = "terminal"
    CLAIM_FAILED = "claim_failed"
    CORRUPT = "corrupt"


class KnowledgeRoot(AcquisitionModel):
    contract_version: Literal["projectlore-knowledge-root/0.6.1"] = (
        "projectlore-knowledge-root/0.6.1"
    )
    root_digest: Digest
    generation_id: Digest
    members: tuple[Digest, ...] = Field(default=(), max_length=1024, strict=False)

    @model_validator(mode="after")
    def members_are_canonical(self) -> KnowledgeRoot:
        if tuple(sorted(set(self.members))) != self.members:
            raise ValueError("members must be unique and ascending")
        return self


class Generation(AcquisitionModel):
    contract_version: Literal["projectlore-knowledge-generation/0.6.1"] = (
        "projectlore-knowledge-generation/0.6.1"
    )
    generation_id: Digest
    sequence: int = Field(ge=0, le=9_223_372_036_854_776_000)
    state: GenerationState = Field(strict=False)
    root_digest: Digest


class Diagnostic(AcquisitionModel):
    code: str = Field(pattern=r"^PLKA[1-7][0-9]{3}$")
    message: str = Field(min_length=1, max_length=1024)
    path: str | None = Field(default=None, min_length=1, max_length=1024)


class SourceKind(StrEnum):
    GIT_YAML = "git_yaml"
    REPOSITORY_METADATA = "repository_metadata"
    HOOK_METADATA = "hook_metadata"
    REVIEW = "review"
    DERIVED = "derived"


class Provenance(AcquisitionModel):
    source_kind: SourceKind = Field(strict=False)
    source_digest: Digest
    path: str | None = Field(default=None, min_length=1, max_length=1024)
    revision: str | None = Field(default=None, min_length=1, max_length=256)


class SignalEvent(StrEnum):
    BOOTSTRAP = "bootstrap"
    STOP = "stop"
    SCAN = "scan"
    OVERFLOW = "overflow"


class KnowledgeSignal(AcquisitionModel):
    contract_version: Literal["projectlore-knowledge-signal/0.6.1"] = (
        "projectlore-knowledge-signal/0.6.1"
    )
    signal_id: Digest
    event: SignalEvent = Field(strict=False)
    repository_id: Digest
    observed_digest: Digest
    paths: tuple[str, ...] = Field(default=(), max_length=256, strict=False)
    provenance: tuple[Provenance, ...] = Field(
        min_length=1, max_length=256, strict=False
    )
    complete: bool
    overflow_count: int | None = Field(default=None, ge=1, le=2_147_483_647)

    @model_validator(mode="after")
    def validate_event_and_ordering(self) -> KnowledgeSignal:
        if tuple(sorted(set(self.paths))) != self.paths:
            raise ValueError("paths must be unique and ascending")
        if self.event is SignalEvent.OVERFLOW:
            if self.complete or self.overflow_count is None:
                raise ValueError("overflow requires incomplete signal and count")
        elif self.overflow_count is not None:
            raise ValueError("overflow_count is only valid for overflow")
        return self


class KnowledgePacket(AcquisitionModel):
    contract_version: Literal["projectlore-knowledge-packet/0.6.1"] = (
        "projectlore-knowledge-packet/0.6.1"
    )
    packet_id: Digest
    base_model_digest: Digest
    signal_ids: tuple[Digest, ...] = Field(min_length=1, max_length=256, strict=False)
    state: Literal["outstanding"] = "outstanding"

    @model_validator(mode="after")
    def signals_are_canonical(self) -> KnowledgePacket:
        if tuple(sorted(set(self.signal_ids))) != self.signal_ids:
            raise ValueError("signal_ids must be unique and ascending")
        return self


class CandidateFile(AcquisitionModel):
    path: str = Field(min_length=1, max_length=1024)
    digest: Digest


class KnowledgeCandidate(AcquisitionModel):
    contract_version: Literal["projectlore-knowledge-candidate/0.6.1"] = (
        "projectlore-knowledge-candidate/0.6.1"
    )
    candidate_digest: Digest
    files: tuple[CandidateFile, ...] = Field(min_length=1, max_length=256, strict=False)

    @model_validator(mode="after")
    def files_are_canonical(self) -> KnowledgeCandidate:
        paths = tuple(item.path for item in self.files)
        if tuple(sorted(set(paths))) != paths:
            raise ValueError("candidate files must use unique ascending paths")
        return self


class ProposalClassification(StrEnum):
    ASSERTED = "asserted"
    INFERRED_SUGGESTION = "inferred_suggestion"


class KnowledgeProposal(AcquisitionModel):
    contract_version: Literal["projectlore-knowledge-proposal/0.6.1"] = (
        "projectlore-knowledge-proposal/0.6.1"
    )
    proposal_id: Digest
    base_model_digest: Digest
    candidate: KnowledgeCandidate
    evidence_ids: tuple[Digest, ...] = Field(min_length=1, max_length=256, strict=False)
    classification: ProposalClassification = Field(strict=False)

    @model_validator(mode="after")
    def evidence_is_canonical(self) -> KnowledgeProposal:
        if tuple(sorted(set(self.evidence_ids))) != self.evidence_ids:
            raise ValueError("evidence_ids must be unique and ascending")
        return self


class ReviewDisposition(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    REVISE = "revise"


class KnowledgeReview(AcquisitionModel):
    contract_version: Literal["projectlore-knowledge-review/0.6.1"] = (
        "projectlore-knowledge-review/0.6.1"
    )
    review_id: Digest
    proposal_id: Digest
    proposal_digest: Digest
    disposition: ReviewDisposition = Field(strict=False)
    actor: str = Field(min_length=1, max_length=256)
    decided_at: datetime = Field(strict=False)
    revision_note: str | None = Field(default=None, min_length=1, max_length=4096)
    released_evidence_ids: tuple[Digest, ...] | None = Field(
        default=None, min_length=1, max_length=256, strict=False
    )

    @model_validator(mode="after")
    def revision_fields_match_disposition(self) -> KnowledgeReview:
        revision = self.disposition is ReviewDisposition.REVISE
        if revision != (
            self.revision_note is not None and self.released_evidence_ids is not None
        ):
            raise ValueError("revise requires note and released evidence only")
        return self


class ReceiptResult(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVISION_RELEASED = "revision_released"
    CLAIM_FAILED = "claim_failed"


class KnowledgeReceipt(AcquisitionModel):
    contract_version: Literal["projectlore-knowledge-receipt/0.6.1"] = (
        "projectlore-knowledge-receipt/0.6.1"
    )
    receipt_id: Digest
    review_id: Digest
    result: ReceiptResult = Field(strict=False)
    before_root: Digest
    after_root: Digest
    transition_id: Digest
    created_at: datetime = Field(strict=False)
