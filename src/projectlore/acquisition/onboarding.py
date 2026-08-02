"""Immediate, repository-grounded onboarding evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from projectlore.acquisition.digest import content_digest
from projectlore.acquisition.models import (
    KnowledgePacket,
    KnowledgeSignal,
    Provenance,
    SourceKind,
)
from projectlore.acquisition.store import ZERO_DIGEST, KnowledgeStore
from projectlore.acquisition.transactions import WorkflowTransaction

EVIDENCE_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "docs/architecture.md",
    "pyproject.toml",
    "projectlore.yaml",
    ".projectlore/model.yaml",
)


def file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def canonical_model_digest(repository: Path) -> str:
    for relative in (".projectlore/model.yaml", "projectlore.yaml"):
        candidate = repository / relative
        if candidate.is_file():
            return file_digest(candidate)
    return ZERO_DIGEST


def canonical_model_path(repository: Path) -> str:
    for relative in (".projectlore/model.yaml", "projectlore.yaml"):
        if (repository / relative).is_file():
            return relative
    return "projectlore.yaml"


def repository_digest(repository: Path) -> str:
    normalized = repository.resolve(strict=True).as_posix().casefold()
    return content_digest("projectlore:repository:0.6.1", {"root": normalized})


def onboarding_preview(repository: Path) -> dict[str, Any]:
    """Describe bounded evidence collection without creating workflow state."""

    root = repository.resolve(strict=True)
    evidence = []
    for relative in EVIDENCE_PATHS:
        path = root / relative
        if path.is_file() and not path.is_symlink():
            evidence.append({"path": relative, "digest": file_digest(path)})
    evidence.sort(key=lambda item: item["path"])
    return {
        "contract_version": "projectlore-onboarding-preview/0.6.1",
        "applied": False,
        "base_model_digest": canonical_model_digest(root),
        "evidence": evidence,
        "instructions": {
            "purpose": (
                "Create a project knowledge baseline from cited repository files."
            ),
            "agent_action": (
                "Read the cited files, author a complete valid ProjectLore YAML "
                "candidate, "
                "and submit it with `lore knowledge propose`."
            ),
            "automatic_acceptance": False,
        },
    }


def start_onboarding(repository: Path) -> tuple[KnowledgeSignal, KnowledgePacket]:
    root = repository.resolve(strict=True)
    preview = onboarding_preview(root)
    paths = tuple(item["path"] for item in preview["evidence"])
    evidence_digests = tuple(item["digest"] for item in preview["evidence"])
    if not paths:
        raise ValueError("No supported repository evidence files were found.")
    repository_id = repository_digest(root)
    observation = {
        "repository_id": repository_id,
        "paths": list(paths),
        "digests": list(evidence_digests),
    }
    observed_digest = content_digest(
        "projectlore:onboarding-observation:0.6.1", observation
    )
    provenance = tuple(
        Provenance(
            source_kind=SourceKind.REPOSITORY_METADATA,
            source_digest=digest,
            path=path,
        )
        for path, digest in zip(paths, evidence_digests, strict=True)
    )
    signal_payload: dict[str, Any] = {
        "contract_version": "projectlore-knowledge-signal/0.6.1",
        "event": "bootstrap",
        "repository_id": repository_id,
        "observed_digest": observed_digest,
        "paths": list(paths),
        "provenance": [
            item.model_dump(mode="json", exclude_none=True) for item in provenance
        ],
        "complete": True,
    }
    signal_id = content_digest("projectlore:knowledge-signal:0.6.1", signal_payload)
    signal = KnowledgeSignal(signal_id=signal_id, **signal_payload)
    packet_payload = {
        "contract_version": "projectlore-knowledge-packet/0.6.1",
        "base_model_digest": preview["base_model_digest"],
        "signal_ids": [signal_id],
        "state": "outstanding",
    }
    packet_id = content_digest("projectlore:knowledge-packet:0.6.1", packet_payload)
    packet = KnowledgePacket(packet_id=packet_id, **packet_payload)
    store = KnowledgeStore(root)
    store.initialize()
    stored_signal = store.put_object(
        "projectlore:knowledge-signal:0.6.1",
        signal.model_dump(mode="json", exclude_none=True),
        exclude=("signal_id",),
    )
    stored_packet = store.put_object(
        "projectlore:knowledge-packet:0.6.1",
        packet.model_dump(mode="json"),
        exclude=("packet_id",),
    )
    if (stored_signal, stored_packet) != (signal_id, packet_id):
        raise RuntimeError("onboarding object identity mismatch")
    current = store.current_root()
    WorkflowTransaction(store).commit((*current.members, signal_id, packet_id))
    return signal, packet
