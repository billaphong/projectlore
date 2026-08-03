"""Read-only recovery inspection and preview-bound workflow-root repair."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from projectlore.acquisition.digest import content_digest
from projectlore.acquisition.models import GenerationState, KnowledgeProposal
from projectlore.acquisition.onboarding import (
    canonical_model_digest,
    canonical_model_path,
)
from projectlore.acquisition.store import CorruptStore, KnowledgeStore
from projectlore.acquisition.transactions import CanonicalWorkflowTransaction
from projectlore.service import ModelService


def _bytes_digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _created_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _inventory(repository: Path) -> list[str]:
    knowledge = repository / ".projectlore" / "knowledge"
    if not knowledge.is_dir():
        return []
    return sorted(
        path.relative_to(repository).as_posix()
        for path in knowledge.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


def recovery_status(repository: Path) -> dict[str, Any]:
    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    try:
        generation = store.recover()
    except CorruptStore as error:
        return {
            "contract_version": "projectlore-recovery-status/0.6.1",
            "state": "corrupt",
            "generation": None,
            "diagnostics": [{"code": "PLKA6008", "message": str(error)}],
        }
    return {
        "contract_version": "projectlore-recovery-status/0.6.1",
        "state": "current",
        "generation": generation.model_dump(mode="json"),
        "diagnostics": [],
    }


def _branch_binding(store: KnowledgeStore, generation_id: str) -> str | None:
    root = store.root_for_generation(generation_id)
    packet_bases: set[str] = set()
    accepted: list[tuple[int, str, str]] = []
    for member in root.members:
        item = store.get_object(member)
        contract = item.get("contract_version")
        if contract == "projectlore-knowledge-packet/0.6.1":
            packet_bases.add(str(item["base_model_digest"]))
        elif (
            contract == "projectlore-knowledge-receipt/0.6.1"
            and item.get("result") == "accepted"
        ):
            review = store.get_object(str(item["review_id"]))
            proposal = KnowledgeProposal.model_validate(
                store.get_object(str(review["proposal_id"]))
            )
            if len(proposal.candidate.files) == 1:
                introduction = min(
                    generation.sequence
                    for generation in store.valid_generations()
                    if member
                    in store.root_for_generation(generation.generation_id).members
                )
                accepted.append(
                    (introduction, member, proposal.candidate.files[0].digest)
                )
    if accepted:
        return max(accepted)[2]
    return next(iter(packet_bases)) if len(packet_bases) == 1 else None


def _verify_generation(
    store: KnowledgeStore, generation_id: str, current_canonical: str
) -> tuple[list[dict[str, str]], str | None]:
    diagnostics: list[dict[str, str]] = []
    binding: str | None = None
    try:
        root = store.root_for_generation(generation_id)
        for member in root.members:
            item = store.get_object(member)
            if item.get("contract_version") == "projectlore-knowledge-proposal/0.6.1":
                proposal = KnowledgeProposal.model_validate(item)
                for candidate_file in proposal.candidate.files:
                    store.get_blob(candidate_file.digest)
        binding = _branch_binding(store, generation_id)
        if binding is None:
            raise CorruptStore("branch has no unique persisted canonical binding")
        if binding != current_canonical:
            raise CorruptStore("branch canonical binding differs from current YAML")
    except Exception as error:  # validation failures are branch evidence
        diagnostics.append({"code": "PLKA6008", "message": str(error)})
    return diagnostics, binding


def _query_outputs(repository: Path) -> list[tuple[str, str, str]]:
    """Execute the three deterministic reads used for repair equivalence."""

    service = ModelService(repository / canonical_model_path(repository))
    queries: tuple[tuple[str, str, dict[str, Any]], ...] = (
        ("homebrew-status", "model_status", {}),
        ("homebrew-context-empty", "context_for_task", {"task": ""}),
        ("forecast-status", "context_for_task", {"task": "forecast status"}),
    )
    results = []
    for fixture, command, arguments in queries:
        output = (
            service.model_status()
            if command == "model_status"
            else service.context_for_task(str(arguments["task"]))
        )
        results.append(
            (
                fixture,
                content_digest(
                    "projectlore:repair-query-command:0.6.1",
                    {"command": command, "arguments": arguments},
                ),
                content_digest(
                    "projectlore:repair-query-output:0.6.1", {"output": output}
                ),
            )
        )
    return results


def _has_contiguous_ancestry(
    store: KnowledgeStore, generation_id: str, sequence: int
) -> bool:
    """Verify a unique, contiguous monotonic-member path back to genesis."""

    members = set(store.root_for_generation(generation_id).members)
    generations = store.valid_generations()
    for expected_sequence in range(sequence - 1, -1, -1):
        predecessors = [
            item
            for item in generations
            if item.sequence == expected_sequence
            and set(store.root_for_generation(item.generation_id).members) <= members
        ]
        if len(predecessors) != 1:
            return False
        members = set(store.root_for_generation(predecessors[0].generation_id).members)
    return True


def repair_preview(repository: Path) -> dict[str, Any]:
    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    corrupt_bytes = (
        store.active_root.read_bytes() if store.active_root.is_file() else b""
    )
    corrupt_digest = _bytes_digest(corrupt_bytes)
    canonical_digest = canonical_model_digest(root)
    branches = store.valid_generations()
    evidence: list[dict[str, Any]] = []
    valid = []
    for generation in branches:
        generation_root = store.root_for_generation(generation.generation_id)
        diagnostics, binding = _verify_generation(
            store, generation.generation_id, canonical_digest
        )
        if not _has_contiguous_ancestry(
            store, generation.generation_id, generation.sequence
        ):
            diagnostics.append(
                {
                    "code": "PLKA6008",
                    "message": "branch ancestry is not contiguous and unique",
                }
            )
        root_path = store.generations / generation.generation_id[7:] / "root.json"
        evidence.append(
            {
                "sequence": generation.sequence,
                "root_digest": generation.root_digest,
                "bytes_digest": _bytes_digest(root_path.read_bytes()),
                "canonical_model_digest": binding or canonical_digest,
                "valid": not diagnostics,
                "diagnostics": diagnostics,
            }
        )
        if not diagnostics:
            valid.append((generation, generation_root))

    greatest = max((item[0].sequence for item in valid), default=None)
    candidates = (
        []
        if greatest is None
        else [item for item in valid if item[0].sequence == greatest]
    )
    selected = candidates[0] if len(candidates) == 1 else None
    selected_root = None if selected is None else selected[1].root_digest
    entries = (
        []
        if selected is None
        else [
            {
                "path": ".projectlore/knowledge/root.json",
                "action": "replace" if store.active_root.exists() else "create",
                "before_digest": corrupt_digest if store.active_root.exists() else None,
                "after_digest": _bytes_digest(
                    (
                        store.generations / selected[0].generation_id[7:] / "root.json"
                    ).read_bytes()
                ),
            }
        ]
    )
    conflicts: list[dict[str, Any]] = []
    if selected is None:
        code = "PLKA6007" if not candidates else "PLKA6010"
        message = (
            "No verified generation exists."
            if not candidates
            else "Multiple equally authoritative verified branches remain."
        )
        conflict_base = {
            "contract_version": "projectlore-knowledge-conflict/0.6.1",
            "kind": "malformed_state" if not candidates else "workflow_fork",
            "expected_digest": canonical_digest,
            "actual_digest": None,
            "paths": [".projectlore/knowledge/root.json"],
            "diagnostic": {"code": code, "message": message},
        }
        conflicts.append(
            {
                **conflict_base,
                "conflict_id": content_digest(
                    "projectlore:knowledge-conflict:0.6.1", conflict_base
                ),
            }
        )
    payload: dict[str, Any] = {
        "contract_version": "projectlore-repair-preview/0.6.1",
        "current_corrupt_digest": corrupt_digest,
        "selected_root": selected_root,
        "evidence": evidence,
        "applicable": selected is not None,
        "entries": entries,
        "conflicts": conflicts,
        "created_at": _created_at(),
    }
    preview_digest = content_digest(
        "projectlore:repair-preview:0.6.1", payload, exclude=("created_at",)
    )
    return {**payload, "preview_digest": preview_digest}


def apply_repair(repository: Path, preview_digest: str) -> dict[str, Any]:
    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    with CanonicalWorkflowTransaction(store):
        canonical_before = canonical_model_digest(root)
        queries_before = _query_outputs(root)
        before_inventory = _inventory(root)
        preview = repair_preview(root)
        if preview["preview_digest"] != preview_digest or not preview["applicable"]:
            raise ValueError("PLKA6009 repair preview no longer matches current state")
        selected_root_digest = preview["selected_root"]
        selected_evidence = max(
            (
                item
                for item in preview["evidence"]
                if item["valid"] and item["root_digest"] == selected_root_digest
            ),
            key=lambda item: int(item["sequence"]),
        )
        selected_generation = next(
            item
            for item in store.valid_generations()
            if item.root_digest == selected_root_digest
            and item.sequence == selected_evidence["sequence"]
        )
        selected_root = store.root_for_generation(selected_generation.generation_id)
        # A repair is a new auditable generation, never direct activation of history.
        generation = store.stage_after(
            selected_generation, selected_root.members, GenerationState.TERMINAL
        )
        store.activate(generation.generation_id)
        canonical_after = canonical_model_digest(root)
        queries_after = _query_outputs(root)
        if canonical_before != canonical_after:
            raise RuntimeError("PLKA6005 repair changed canonical project knowledge")
        after_inventory = _inventory(root)
        query_records = []
        for sequence, (before_query, after_query) in enumerate(
            zip(queries_before, queries_after, strict=True), start=1
        ):
            fixture, command_digest, before_digest = before_query
            after_fixture, after_command, after_digest = after_query
            if (fixture, command_digest) != (after_fixture, after_command):
                raise RuntimeError("PLKA6006 repair query suite changed during apply")
            query_records.append(
                {
                    "sequence": sequence,
                    "fixture_id": fixture,
                    "command_digest": command_digest,
                    "expected_digest": before_digest,
                    "before_digest": before_digest,
                    "after_digest": after_digest,
                    "equal": before_digest == after_digest,
                }
            )
        if not all(item["equal"] for item in query_records):
            raise RuntimeError("PLKA6006 repair changed core query results")
        query_equivalence = {
            "records": query_records,
            "suite_digest": content_digest(
                "projectlore:repair-query-suite:0.6.1", {"records": query_records}
            ),
        }
        receipt_base: dict[str, Any] = {
            "contract_version": "projectlore-knowledge-lifecycle-receipt/0.6.1",
            "operation": "repair",
            "preview_digest": preview_digest,
            "before_inventory": before_inventory,
            "after_inventory": after_inventory,
            "canonical_before": canonical_before,
            "canonical_after": canonical_after,
            "query_equivalence": query_equivalence,
            "created_at": _created_at(),
        }
        receipt_id = content_digest(
            "projectlore:knowledge-lifecycle-receipt:0.6.1",
            receipt_base,
            exclude=("created_at",),
        )
        receipt = {**receipt_base, "receipt_id": receipt_id}
        store.write_lifecycle_receipt(receipt_id, receipt)
    return {
        **preview,
        "applied": True,
        "generation": generation.model_dump(mode="json"),
        "receipt": receipt,
    }
