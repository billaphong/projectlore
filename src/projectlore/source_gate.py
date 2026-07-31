"""Deterministic checkout gate for configured source-policy facts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

from projectlore.models import Source, StrictModel
from projectlore.policy import (
    Finding,
    PolicyDecision,
    PolicyRequest,
    load_policy_registry,
    policy_check,
)
from projectlore.scope import ScopeReceipt
from projectlore.service import ModelService
from projectlore.source_policy import facts_from_paths, load_scope_snapshot

MAX_SOURCE_GATE_EVIDENCE_BYTES = 1024 * 1024


class SourceGateEvidence(StrictModel):
    evidence_version: Literal["projectlore-source-gate/0.1.0"]
    evidence_id: str
    model_digest: str
    assurance_scope: Literal["local_advisory", "ci_job_result"]
    repository_certified: Literal[False] = False
    checked_files: tuple[str, ...]
    facts: dict[str, str]
    policy_decision: PolicyDecision
    decision: Literal["pass", "fail", "indeterminate"]
    findings: tuple[Finding, ...]
    provenance: tuple[Source, ...]
    scope_receipt: ScopeReceipt | None


def evaluate_source_gate(
    root: Path,
    service: ModelService,
    paths: tuple[str, ...],
    *,
    assurance_scope: Literal["local_advisory", "ci_job_result"],
) -> SourceGateEvidence:
    """Evaluate checked-out configured files through the canonical policy core."""
    checked = tuple(sorted(set(paths)))
    facts = facts_from_paths(root, checked)
    result = policy_check(
        service,
        PolicyRequest(
            facts=facts,
            scope=load_scope_snapshot(root, required=False),
        ),
        registry=load_policy_registry(root),
        scope_obtained_via="provided_snapshot",
    )
    policy_decision: PolicyDecision = result["decision"]
    decision: Literal["pass", "fail", "indeterminate"]
    if policy_decision == "pass":
        decision = "pass"
    elif policy_decision == "fail":
        decision = "fail"
    else:
        decision = "indeterminate"
    findings = tuple(Finding.model_validate(item) for item in result["findings"])
    provenance = tuple(
        Source.model_validate(item) for item in result["provenance"]
    )
    raw_receipt = result["scope_receipt"]
    receipt = (
        ScopeReceipt.model_validate(raw_receipt, strict=False)
        if raw_receipt is not None
        else None
    )
    content: dict[str, Any] = {
        "model_digest": service.project.digest,
        "assurance_scope": assurance_scope,
        "checked_files": checked,
        "facts": facts,
        "policy_decision": policy_decision,
        "decision": decision,
        "finding_ids": [
            (item.rule_id, item.decision, item.outcome) for item in findings
        ],
        "provenance_ids": [item.id for item in provenance],
        "scope_digest": receipt.scope_digest if receipt is not None else None,
    }
    encoded = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return SourceGateEvidence(
        evidence_version="projectlore-source-gate/0.1.0",
        evidence_id=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        model_digest=service.project.digest,
        assurance_scope=assurance_scope,
        repository_certified=False,
        checked_files=checked,
        facts=facts,
        policy_decision=policy_decision,
        decision=decision,
        findings=findings,
        provenance=provenance,
        scope_receipt=receipt,
    )


def source_gate_exit_code(evidence: SourceGateEvidence) -> int:
    return {"pass": 0, "fail": 1, "indeterminate": 2}[evidence.decision]


def write_source_gate_evidence(
    path: Path,
    evidence: SourceGateEvidence,
) -> None:
    """Atomically write bounded source-gate evidence."""
    payload = f"{evidence.model_dump_json(indent=2)}\n".encode()
    if len(payload) > MAX_SOURCE_GATE_EVIDENCE_BYTES:
        raise ValueError("Source-gate evidence exceeds 1 MiB.")
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
