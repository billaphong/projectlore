"""Bounded passive evidence capture and deterministic packet leasing."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from projectlore.acquisition.digest import canonical_json, content_digest
from projectlore.acquisition.models import (
    KnowledgePacket,
    KnowledgeProposal,
    KnowledgeReview,
    KnowledgeSignal,
    Provenance,
    SourceKind,
)
from projectlore.acquisition.onboarding import (
    canonical_model_digest,
    file_digest,
    repository_digest,
)
from projectlore.acquisition.store import KnowledgeStore
from projectlore.acquisition.transactions import WorkflowTransaction

MAX_PATHS = 256


def _tracked_paths(repository: Path) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repository,
            capture_output=True,
            check=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return tuple(
            sorted(
                path.relative_to(repository).as_posix()
                for path in repository.iterdir()
                if path.is_file() and not path.is_symlink()
            )
        )
    return tuple(
        sorted(
            item.decode("utf-8")
            for item in result.stdout.split(b"\0")
            if item and b"\\" not in item
        )
    )


def capture_scan(repository: Path, *, lock_timeout: float = 5.0) -> KnowledgeSignal:
    """Persist hashes and paths only; never source text or provider output."""

    root = repository.resolve(strict=True)
    all_paths = _tracked_paths(root)
    selected = all_paths[:MAX_PATHS]
    overflow = len(all_paths) - len(selected)
    evidence: list[tuple[str, str]] = []
    for relative in selected:
        path = root / relative
        if path.is_file() and not path.is_symlink():
            evidence.append((relative, file_digest(path)))
    paths = tuple(path for path, _ in evidence)
    provenance = tuple(
        sorted(
            (
                Provenance(
                    source_kind=SourceKind.REPOSITORY_METADATA,
                    source_digest=digest,
                    path=path,
                )
                for path, digest in evidence
            ),
            key=lambda item: canonical_json(item.model_dump(mode="json")),
        )
    )
    if not provenance:
        raise ValueError("No bounded tracked-file metadata was available.")
    observation = {
        "repository_id": repository_digest(root),
        "paths": list(paths),
        "digests": [digest for _, digest in evidence],
        "complete": overflow == 0,
        "overflow_count": overflow,
    }
    observed_digest = content_digest("projectlore:scan-observation:0.6.1", observation)
    payload: dict[str, Any] = {
        "contract_version": "projectlore-knowledge-signal/0.6.1",
        "event": "overflow" if overflow else "scan",
        "repository_id": repository_digest(root),
        "observed_digest": observed_digest,
        "paths": list(paths),
        "provenance": [
            item.model_dump(mode="json", exclude_none=True) for item in provenance
        ],
        "complete": overflow == 0,
    }
    if overflow:
        payload["overflow_count"] = overflow
    signal_id = content_digest("projectlore:knowledge-signal:0.6.1", payload)
    signal = KnowledgeSignal(signal_id=signal_id, **payload)
    return _persist_signal(root, signal, lock_timeout=lock_timeout)


def capture_hook_event(
    repository: Path,
    *,
    client: str,
    session_id: str,
    changed_paths: tuple[str, ...] = (),
    lock_timeout: float = 5.0,
) -> KnowledgeSignal:
    """Persist one bounded metadata-only Stop observation without scanning files."""

    root = repository.resolve(strict=True)
    if client not in {"claude_code", "codex_cli"}:
        raise ValueError("unsupported acquisition hook client")
    if not session_id or len(session_id) > 256:
        raise ValueError("hook field 'session_id' must contain 1 to 256 characters")
    normalized_paths = tuple(sorted(set(changed_paths)))
    if len(normalized_paths) > MAX_PATHS:
        raise ValueError("hook changed_paths exceeds 256")
    for relative in normalized_paths:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(
                f"hook changed path is not repository-relative: {relative}"
            )
    repository_id = repository_digest(root)
    observation = {
        "client": client,
        "event": "Stop",
        "repository_id": repository_id,
        "session_id": session_id,
        "changed_paths": list(normalized_paths),
    }
    observed_digest = content_digest(
        "projectlore:hook-observation:0.6.1", observation
    )
    payload: dict[str, Any] = {
        "contract_version": "projectlore-knowledge-signal/0.6.1",
        "event": "stop",
        "repository_id": repository_id,
        "observed_digest": observed_digest,
        "paths": list(normalized_paths),
        "provenance": [
            Provenance(
                source_kind=SourceKind.HOOK_METADATA,
                source_digest=observed_digest,
            ).model_dump(mode="json", exclude_none=True)
        ],
        "complete": True,
    }
    signal_id = content_digest("projectlore:knowledge-signal:0.6.1", payload)
    signal = KnowledgeSignal(signal_id=signal_id, **payload)
    return _persist_signal(root, signal, lock_timeout=lock_timeout)


def _persist_signal(
    root: Path, signal: KnowledgeSignal, *, lock_timeout: float
) -> KnowledgeSignal:
    store = KnowledgeStore(root)
    store.initialize()
    stored = store.put_object(
        "projectlore:knowledge-signal:0.6.1",
        signal.model_dump(mode="json", exclude_none=True),
        exclude=("signal_id",),
    )
    if stored != signal.signal_id:
        raise RuntimeError("knowledge signal identity mismatch")
    current = store.current_root()
    if signal.signal_id not in current.members:
        WorkflowTransaction(store, timeout=lock_timeout).commit((signal.signal_id,))
    return signal


def _workflow_objects(store: KnowledgeStore) -> list[dict[str, Any]]:
    return [store.get_object(member) for member in store.current_root().members]


def _outstanding_packet(objects: list[dict[str, Any]]) -> KnowledgePacket | None:
    proposals = [
        KnowledgeProposal.model_validate(item)
        for item in objects
        if item.get("contract_version") == "projectlore-knowledge-proposal/0.6.1"
    ]
    reviewed_proposals = {
        KnowledgeReview.model_validate(item).proposal_id
        for item in objects
        if item.get("contract_version") == "projectlore-knowledge-review/0.6.1"
    }
    packets = [
        KnowledgePacket.model_validate(item)
        for item in objects
        if item.get("contract_version") == "projectlore-knowledge-packet/0.6.1"
    ]
    for packet in packets:
        packet_proposals = [p for p in proposals if packet.packet_id in p.evidence_ids]
        if not packet_proposals or any(
            proposal.proposal_id not in reviewed_proposals
            for proposal in packet_proposals
        ):
            return packet
    return None


def next_packet(
    repository: Path, *, lock_timeout: float = 5.0
) -> KnowledgePacket | None:
    """Return the one outstanding packet or lease all pending signals once."""

    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    store.initialize()
    objects = _workflow_objects(store)
    outstanding = _outstanding_packet(objects)
    if outstanding is not None:
        return outstanding
    packets = [
        KnowledgePacket.model_validate(item)
        for item in objects
        if item.get("contract_version") == "projectlore-knowledge-packet/0.6.1"
    ]
    leased = {signal for packet in packets for signal in packet.signal_ids}
    released_packets = {
        evidence
        for item in objects
        if item.get("contract_version") == "projectlore-knowledge-review/0.6.1"
        and item.get("disposition") == "revise"
        for evidence in item.get("released_evidence_ids", [])
    }
    released = {
        signal
        for packet in packets
        if packet.packet_id in released_packets
        for signal in packet.signal_ids
    }
    leased.difference_update(released)
    pending = sorted(
        item["signal_id"]
        for item in objects
        if item.get("contract_version") == "projectlore-knowledge-signal/0.6.1"
        and item["signal_id"] not in leased
    )
    if not pending:
        return None
    payload: dict[str, Any] = {
        "contract_version": "projectlore-knowledge-packet/0.6.1",
        "base_model_digest": canonical_model_digest(root),
        "signal_ids": pending[:MAX_PATHS],
        "state": "outstanding",
    }
    packet_id = content_digest("projectlore:knowledge-packet:0.6.1", payload)
    packet = KnowledgePacket(packet_id=packet_id, **payload)
    store.put_object(
        "projectlore:knowledge-packet:0.6.1",
        packet.model_dump(mode="json"),
        exclude=("packet_id",),
    )
    WorkflowTransaction(store, timeout=lock_timeout).commit((packet_id,))
    return packet


def knowledge_status(repository: Path) -> dict[str, Any]:
    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    if not store.active_root.exists():
        return {
            "contract_version": "projectlore-knowledge-status/0.6.1",
            "state": "not_initialized",
            "canonical_model_digest": canonical_model_digest(root),
            "counts": {},
        }
    objects = _workflow_objects(store)
    counts: dict[str, int] = {}
    for item in objects:
        kind = str(item.get("contract_version", "unknown"))
        counts[kind] = counts.get(kind, 0) + 1
    packet = _outstanding_packet(objects)
    return {
        "contract_version": "projectlore-knowledge-status/0.6.1",
        "state": "outstanding" if packet is not None else "current",
        "canonical_model_digest": canonical_model_digest(root),
        "outstanding_packet_id": None if packet is None else packet.packet_id,
        "counts": counts,
    }
