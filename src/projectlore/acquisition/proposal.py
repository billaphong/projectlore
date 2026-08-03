"""Agent-authored, provenance-bound candidate proposal intake."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from projectlore.acquisition.digest import content_digest
from projectlore.acquisition.models import (
    CandidateFile,
    KnowledgeCandidate,
    KnowledgePacket,
    KnowledgeProposal,
    ProposalClassification,
)
from projectlore.acquisition.onboarding import (
    canonical_model_digest,
    canonical_model_path,
)
from projectlore.acquisition.store import KnowledgeStore
from projectlore.acquisition.transactions import WorkflowTransaction
from projectlore.validation import validate_path


def submit_proposal(
    repository: Path,
    candidate_path: Path,
    packet_id: str,
    *,
    classification: ProposalClassification = ProposalClassification.ASSERTED,
) -> KnowledgeProposal:
    """Validate and retain a complete candidate without changing canonical YAML."""

    root = repository.resolve(strict=True)
    candidate_path = candidate_path.resolve(strict=True)
    model, report = validate_path(candidate_path)
    if model is None or not report.valid:
        details = "; ".join(item.message for item in report.diagnostics)
        raise ValueError(f"Candidate ProjectLore model is invalid: {details}")
    store = KnowledgeStore(root)
    packet = KnowledgePacket.model_validate(store.get_object(packet_id))
    if packet.base_model_digest != canonical_model_digest(root):
        raise ValueError("PLKA2001 stale onboarding packet base model")
    candidate_bytes = candidate_path.read_bytes()
    blob_digest = store.put_blob(candidate_bytes)
    file_entry = CandidateFile(path=canonical_model_path(root), digest=blob_digest)
    candidate_payload: dict[str, Any] = {
        "contract_version": "projectlore-knowledge-candidate/0.6.1",
        "files": [file_entry.model_dump(mode="json")],
    }
    candidate_digest = content_digest(
        "projectlore:knowledge-candidate:0.6.1", candidate_payload
    )
    candidate = KnowledgeCandidate(
        candidate_digest=candidate_digest, files=(file_entry,)
    )
    proposal_payload: dict[str, Any] = {
        "contract_version": "projectlore-knowledge-proposal/0.6.1",
        "base_model_digest": packet.base_model_digest,
        "candidate": candidate.model_dump(mode="json"),
        "evidence_ids": [packet_id],
        "classification": classification.value,
    }
    proposal_id = content_digest(
        "projectlore:knowledge-proposal:0.6.1", proposal_payload
    )
    proposal = KnowledgeProposal(proposal_id=proposal_id, **proposal_payload)
    stored = store.put_object(
        "projectlore:knowledge-proposal:0.6.1",
        proposal.model_dump(mode="json"),
        exclude=("proposal_id",),
    )
    if stored != proposal_id:
        raise RuntimeError("proposal identity mismatch")
    current = store.current_root()
    WorkflowTransaction(store).commit((*current.members, proposal_id))
    return proposal
