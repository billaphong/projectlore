"""Explicit review and canonical promotion of knowledge proposals."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from projectlore.acquisition.digest import content_digest
from projectlore.acquisition.models import (
    GenerationState,
    KnowledgeProposal,
    KnowledgeReceipt,
    KnowledgeReview,
    ReceiptResult,
    ReviewDisposition,
)
from projectlore.acquisition.onboarding import canonical_model_digest
from projectlore.acquisition.store import KnowledgeStore
from projectlore.acquisition.transactions import (
    CanonicalWorkflowTransaction,
    FileLock,
    WorkflowTransaction,
)
from projectlore.validation import validate_path


def review_proposal(
    repository: Path,
    proposal_id: str,
    disposition: ReviewDisposition,
    actor: str,
    *,
    revision_note: str | None = None,
) -> KnowledgeReview:
    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    proposal_data = store.get_object(proposal_id)
    proposal = KnowledgeProposal.model_validate(proposal_data)
    for member in store.current_root().members:
        existing = store.get_object(member)
        if (
            existing.get("contract_version") == "projectlore-knowledge-review/0.6.1"
            and existing.get("proposal_id") == proposal_id
        ):
            previous = KnowledgeReview.model_validate(existing)
            if (
                previous.disposition is disposition
                and previous.actor == actor
                and previous.revision_note == revision_note
            ):
                return previous
            raise ValueError("PLKA2002 proposal already has a terminal review")
    proposal_digest = content_digest(
        "projectlore:knowledge-proposal:0.6.1",
        proposal.model_dump(mode="json"),
        exclude=("proposal_id",),
    )
    released = (
        proposal.evidence_ids if disposition is ReviewDisposition.REVISE else None
    )
    review_payload: dict[str, Any] = {
        "contract_version": "projectlore-knowledge-review/0.6.1",
        "proposal_id": proposal_id,
        "proposal_digest": proposal_digest,
        "disposition": disposition.value,
        "actor": actor,
        "decided_at": datetime.now(UTC),
        "revision_note": revision_note,
        "released_evidence_ids": released,
    }
    review_payload = {
        key: value for key, value in review_payload.items() if value is not None
    }
    digest_payload = {
        **review_payload,
        "decided_at": review_payload["decided_at"].isoformat().replace("+00:00", "Z"),
        "released_evidence_ids": list(released) if released is not None else None,
    }
    digest_payload = {
        key: value for key, value in digest_payload.items() if value is not None
    }
    review_id = content_digest(
        "projectlore:knowledge-review:0.6.1",
        digest_payload,
        exclude=("decided_at",),
    )
    if store.has_object(review_id):
        return KnowledgeReview.model_validate(store.get_object(review_id))
    review = KnowledgeReview(review_id=review_id, **review_payload)
    stored = store.put_object(
        "projectlore:knowledge-review:0.6.1",
        review.model_dump(mode="json", exclude_none=True),
        exclude=("review_id", "decided_at"),
    )
    if stored != review_id:
        raise RuntimeError("review identity mismatch")
    review = _activate_review(store, review)
    if disposition is ReviewDisposition.REJECT:
        _issue_receipt(store, review_id, ReceiptResult.REJECTED)
    elif disposition is ReviewDisposition.REVISE:
        _issue_receipt(store, review_id, ReceiptResult.REVISION_RELEASED)
    return review


def _activate_review(store: KnowledgeStore, review: KnowledgeReview) -> KnowledgeReview:
    lock = store.directory / "locks" / "workflow.lock"
    with FileLock(lock):
        current = store.current_root()
        for member in current.members:
            existing = store.get_object(member)
            if (
                existing.get("contract_version") == "projectlore-knowledge-review/0.6.1"
                and existing.get("proposal_id") == review.proposal_id
            ):
                previous = KnowledgeReview.model_validate(existing)
                if (
                    previous.disposition is review.disposition
                    and previous.actor == review.actor
                    and previous.revision_note == review.revision_note
                ):
                    return previous
                raise ValueError("PLKA2002 proposal already has a terminal review")
        staged = store.stage((*current.members, review.review_id))
        store.activate(staged.generation_id)
    return review


def apply_review(repository: Path, review_id: str) -> Path:
    """Apply only an accepted, current-base, digest-bound candidate."""

    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    review = KnowledgeReview.model_validate(store.get_object(review_id))
    if review.disposition is not ReviewDisposition.ACCEPT:
        raise ValueError("Only an accepted review can change canonical knowledge.")
    proposal = KnowledgeProposal.model_validate(store.get_object(review.proposal_id))
    actual_proposal_digest = content_digest(
        "projectlore:knowledge-proposal:0.6.1",
        proposal.model_dump(mode="json"),
        exclude=("proposal_id",),
    )
    if actual_proposal_digest != review.proposal_digest:
        raise ValueError("PLKA2002 review does not bind the stored proposal")
    with CanonicalWorkflowTransaction(store):
        if len(proposal.candidate.files) != 1:
            raise ValueError("v0.6.1 supports one canonical candidate file")
        candidate_file = proposal.candidate.files[0]
        content = store.get_blob(candidate_file.digest)
        target = root / candidate_file.path
        current_digest = canonical_model_digest(root)
        if current_digest == candidate_file.digest:
            current = store.current_root()
            if review_id not in current.members:
                staged = store.stage((*current.members, review_id))
                store.activate(staged.generation_id)
            _issue_receipt(store, review_id, ReceiptResult.ACCEPTED, lock_held=True)
            return target
        if proposal.base_model_digest != current_digest:
            raise ValueError("PLKA2001 canonical model changed after proposal")
        current = store.current_root()
        claim = store.stage(
            (*current.members, review_id), GenerationState.COMMIT_CLAIMED
        )
        store.activate(claim.generation_id)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            _, report = validate_path(temporary)
            if not report.valid:
                raise ValueError("Candidate became invalid before apply")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        current = store.current_root()
        staged = store.stage((*current.members, review_id), GenerationState.TERMINAL)
        store.activate(staged.generation_id)
        _issue_receipt(store, review_id, ReceiptResult.ACCEPTED, lock_held=True)
    return target


def recover_commit_claim(repository: Path) -> str:
    """Resolve an interrupted canonical apply from persisted digest-bound evidence."""

    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    with CanonicalWorkflowTransaction(store):
        generation = store.current_generation()
        if generation.state is not GenerationState.COMMIT_CLAIMED:
            return "unchanged"
        accepted = []
        receipted_reviews = set()
        for member in store.current_root().members:
            item = store.get_object(member)
            if item.get("contract_version") == "projectlore-knowledge-receipt/0.6.1":
                receipted_reviews.add(str(item["review_id"]))
        for member in store.current_root().members:
            item = store.get_object(member)
            if (
                item.get("contract_version") == "projectlore-knowledge-review/0.6.1"
                and item.get("disposition") == "accept"
                and str(item["review_id"]) not in receipted_reviews
            ):
                accepted.append(KnowledgeReview.model_validate(item))
        if len(accepted) != 1:
            raise ValueError("PLKA7002 commit claim has no unique accepted review")
        review = accepted[0]
        proposal = KnowledgeProposal.model_validate(
            store.get_object(review.proposal_id)
        )
        candidate = proposal.candidate.files[0]
        current_digest = canonical_model_digest(root)
        if current_digest == proposal.base_model_digest:
            failed = store.stage(
                store.current_root().members, GenerationState.CLAIM_FAILED
            )
            store.activate(failed.generation_id)
            return "claim_failed"
        if current_digest != candidate.digest:
            raise ValueError("PLKA7002 canonical state matches neither claim boundary")
        terminal = store.stage(store.current_root().members, GenerationState.TERMINAL)
        store.activate(terminal.generation_id)
        _issue_receipt(store, review.review_id, ReceiptResult.ACCEPTED, lock_held=True)
        return "rolled_forward"


def _issue_receipt(
    store: KnowledgeStore,
    review_id: str,
    result: ReceiptResult,
    *,
    lock_held: bool = False,
) -> KnowledgeReceipt:
    current = store.current_root()
    transition_id = content_digest(
        "projectlore:knowledge-transition:0.6.1",
        {
            "from_generation": current.generation_id,
            "to_generation": current.generation_id,
            "kind": "committed" if result is ReceiptResult.ACCEPTED else "reviewed",
            "causes": [review_id],
        },
    )
    payload: dict[str, Any] = {
        "contract_version": "projectlore-knowledge-receipt/0.6.1",
        "review_id": review_id,
        "result": result.value,
        "before_root": current.root_digest,
        "after_root": current.root_digest,
        "transition_id": transition_id,
        "created_at": datetime.now(UTC),
    }
    digest_payload = {
        **payload,
        "created_at": payload["created_at"].isoformat().replace("+00:00", "Z"),
    }
    receipt_id = content_digest(
        "projectlore:knowledge-receipt:0.6.1",
        digest_payload,
        exclude=("created_at",),
    )
    if store.has_object(receipt_id):
        return KnowledgeReceipt.model_validate(store.get_object(receipt_id))
    receipt = KnowledgeReceipt(receipt_id=receipt_id, **payload)
    store.put_object(
        "projectlore:knowledge-receipt:0.6.1",
        receipt.model_dump(mode="json"),
        exclude=("receipt_id", "created_at"),
    )
    current = store.current_root()
    if lock_held:
        staged = store.stage((*current.members, receipt_id), GenerationState.TERMINAL)
        store.activate(staged.generation_id)
    else:
        WorkflowTransaction(store).commit(
            (*current.members, receipt_id), state=GenerationState.TERMINAL
        )
    return receipt
