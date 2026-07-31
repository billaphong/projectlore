"""Explicit adapters for frozen workflow payloads from ProjectLore 0.1.x."""

from __future__ import annotations

from projectlore.scope import ScopeReceipt, ScopeSnapshot
from projectlore.workflow import (
    WorkflowAssurance,
    WorkflowObservation,
    WorkflowReceipt,
    WorkflowTarget,
    make_observation,
)


def legacy_snapshot_to_observation(
    snapshot: ScopeSnapshot,
    target: WorkflowTarget,
) -> WorkflowObservation:
    """Normalize a legacy snapshot while enforcing configured identity."""
    if snapshot.authority != target.provider_id or snapshot.frame_id != target.scope_id:
        from projectlore.workflow import WorkflowTargetMismatch

        raise WorkflowTargetMismatch()
    assurance: WorkflowAssurance = (
        "declared" if snapshot.authority == "local" else "observed"
    )
    return make_observation(
        target,
        assurance=assurance,
        title=snapshot.frame_title,
        status=snapshot.frame_status,
        validation_open=snapshot.validation_open,
        observed_at=snapshot.observed_at,
        authority_ref=snapshot.authority_ref,
        provider_revision=(
            str(snapshot.closure_generation)
            if snapshot.closure_generation is not None
            else None
        ),
    )


def observation_to_legacy_snapshot(
    observation: WorkflowObservation,
) -> ScopeSnapshot:
    """Project a canonical observation for unchanged 0.1.x callers."""
    return ScopeSnapshot(
        authority=observation.provider_id,
        frame_id=observation.scope_id,
        frame_title=observation.title,
        frame_status=observation.status,
        validation_open=observation.validation_open,
        observed_at=observation.observed_at,
        authority_ref=observation.authority_ref,
        closure_generation=(
            int(observation.provider_revision)
            if observation.provider_revision is not None
            and observation.provider_revision.isdecimal()
            else None
        ),
    )


def receipt_to_legacy_receipt(
    receipt: WorkflowReceipt,
    *,
    obtained_via: str,
) -> ScopeReceipt:
    """Project canonical evidence into the frozen legacy receipt contract."""
    if obtained_via not in {"fraimed_mcp", "local_file", "provided_snapshot"}:
        raise ValueError("Unsupported legacy receipt transport.")
    return ScopeReceipt.model_validate(
        {
            "receipt_version": "scope-receipt/0.1.0",
            "authority": receipt.provider_id,
            "frame_id": receipt.scope_id,
            "authority_ref": receipt.authority_ref,
            "observed_at": receipt.observed_at,
            "evaluated_at": receipt.evaluated_at,
            "age_seconds": receipt.age_seconds,
            "scope_digest": receipt.observation_digest,
            "fresh": receipt.fresh,
            "claim": "scope_observed",
            "obtained_via": obtained_via,
            "confirmed_scope_version": None,
            "closure_generation": None,
            "maximum_age_seconds": receipt.maximum_age_seconds,
        }
    )


def legacy_receipt_to_receipt(
    legacy: ScopeReceipt,
    target: WorkflowTarget,
    *,
    model_digest: str,
) -> WorkflowReceipt:
    """Normalize frozen receipt evidence without weakening target binding."""
    if legacy.authority != target.provider_id or legacy.frame_id != target.scope_id:
        from projectlore.workflow import WorkflowTargetMismatch

        raise WorkflowTargetMismatch()
    assurance: WorkflowAssurance = (
        "declared" if legacy.authority == "local" else "observed"
    )
    return WorkflowReceipt(
        receipt_version="projectlore-workflow-receipt/1.0.0",
        project_id=target.project_id,
        model_entrypoint=target.model_entrypoint,
        model_digest=model_digest,
        provider_id=target.provider_id,
        scope_id=target.scope_id,
        container_id=target.container_id,
        target_digest=target.digest,
        observation_digest=legacy.scope_digest,
        assurance=assurance,
        authority_ref=legacy.authority_ref,
        observed_at=legacy.observed_at,
        evaluated_at=legacy.evaluated_at,
        age_seconds=legacy.age_seconds,
        fresh=legacy.fresh,
        maximum_age_seconds=legacy.maximum_age_seconds,
    )
