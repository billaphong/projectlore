from __future__ import annotations

import ast
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from projectlore.provider_dispatch import build_workflow_provider
from projectlore.scope import ScopeSnapshot
from projectlore.workflow import (
    LocalScopeProvider,
    WorkflowAuthenticationRequired,
    WorkflowObservation,
    WorkflowProviderFailure,
    WorkflowResponseInvalid,
    WorkflowTarget,
    WorkflowTargetMismatch,
    WorkflowTimeout,
    WorkflowUnavailable,
    issue_workflow_receipt,
    make_observation,
)
from projectlore.workflow_compat import (
    legacy_receipt_to_receipt,
    legacy_snapshot_to_observation,
    observation_to_legacy_snapshot,
    receipt_to_legacy_receipt,
)

ROOT = Path(__file__).resolve().parents[1]


def _target(**changes: str | None) -> WorkflowTarget:
    values: dict[str, str | None] = {
        "target_version": "projectlore-workflow-target/1.0.0",
        "project_id": "lore:projectlore/project",
        "model_entrypoint": "projectlore.yaml",
        "provider_id": "local",
        "scope_id": "phase-2",
        "container_id": None,
    }
    values.update(changes)
    return WorkflowTarget.model_validate(values)


def _observation(target: WorkflowTarget) -> WorkflowObservation:
    return make_observation(
        target,
        assurance="declared",
        title="Provider kernel",
        status="active",
        validation_open=3,
        observed_at=datetime(2026, 7, 31, 12, tzinfo=UTC),
        authority_ref="local://scope/phase-2",
    )


def test_target_identity_and_receipt_bind_every_replay_boundary() -> None:
    target = _target()
    observation = _observation(target)
    receipt = issue_workflow_receipt(
        observation,
        target,
        model_digest="sha256:" + "a" * 64,
        now=observation.observed_at + timedelta(seconds=30),
    )

    assert receipt.assurance == "declared"
    assert receipt.project_id == target.project_id
    assert receipt.model_entrypoint == target.model_entrypoint
    assert receipt.target_digest == target.digest
    assert receipt.observation_digest == observation.content_digest
    assert receipt.fresh is True

    moved = _target(project_id="lore:another/project")
    with pytest.raises(WorkflowTargetMismatch):
        observation.validate_target(moved)


def test_local_provider_cannot_relabel_declared_context() -> None:
    target = _target()
    declared = _observation(target)
    provider = LocalScopeProvider(declared)

    assert asyncio.run(provider.observe(target)).assurance == "declared"

    observed = declared.model_copy(update={"assurance": "observed"})
    with pytest.raises(ValueError, match="local declaration"):
        LocalScopeProvider(observed)


def test_legacy_snapshot_uses_explicit_lossless_adapter() -> None:
    target = _target()
    legacy = ScopeSnapshot(
        authority="local",
        frame_id=target.scope_id,
        frame_title="Provider kernel",
        frame_status="active",
        validation_open=3,
        observed_at=datetime(2026, 7, 31, 12, tzinfo=UTC),
        authority_ref="local://scope/phase-2",
    )

    canonical = legacy_snapshot_to_observation(legacy, target)
    projected = observation_to_legacy_snapshot(canonical)

    assert projected.model_dump(mode="json") == legacy.model_dump(mode="json")


def test_canonical_receipt_projects_to_frozen_legacy_shape() -> None:
    target = _target()
    observation = _observation(target)
    receipt = issue_workflow_receipt(
        observation,
        target,
        model_digest="sha256:" + "b" * 64,
        now=observation.observed_at,
    )

    legacy = receipt_to_legacy_receipt(receipt, obtained_via="local_file")

    assert legacy.receipt_version == "scope-receipt/0.1.0"
    assert legacy.frame_id == target.scope_id
    assert legacy.obtained_via == "local_file"
    restored = legacy_receipt_to_receipt(
        legacy, target, model_digest=receipt.model_digest
    )
    assert restored == receipt


def test_dispatch_is_explicit_and_unknown_provider_fails_safely() -> None:
    target = _target()
    provider = build_workflow_provider(
        "local", local_observation=_observation(target)
    )
    assert asyncio.run(provider.observe(target)).scope_id == target.scope_id

    with pytest.raises(WorkflowUnavailable) as raised:
        build_workflow_provider("unknown")
    assert str(raised.value) == "Workflow provider is unavailable."

    with pytest.raises(WorkflowAuthenticationRequired):
        build_workflow_provider("fraimed", fraimed_url="https://example.test")


def test_provider_failures_have_stable_bounded_sanitized_contracts() -> None:
    failures: tuple[type[WorkflowProviderFailure], ...] = (
        WorkflowUnavailable,
        WorkflowTimeout,
        WorkflowAuthenticationRequired,
        WorkflowResponseInvalid,
        WorkflowTargetMismatch,
    )
    assert len({failure.code for failure in failures}) == len(failures)
    for failure_type in failures:
        failure = failure_type()
        assert len(str(failure)) <= 80
        assert "token" not in str(failure).lower()
        assert "http" not in str(failure).lower()


def test_core_imports_never_point_toward_provider_adapters() -> None:
    core_modules = (
        "compiler.py",
        "loader.py",
        "models.py",
        "query.py",
        "policy.py",
        "workflow.py",
    )
    forbidden = {"projectlore.fraimed", "projectlore.provider_dispatch"}
    for filename in core_modules:
        tree = ast.parse(
            (ROOT / "src" / "projectlore" / filename).read_text(encoding="utf-8")
        )
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert imports.isdisjoint(forbidden), filename


def test_canonical_kernel_contains_no_fraimed_shaped_fields() -> None:
    fields = (
        set(WorkflowTarget.model_fields)
        | set(WorkflowObservation.model_fields)
    )
    assert fields.isdisjoint({"frame_id", "frame_title", "frame_status", "space_id"})
