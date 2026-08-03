"""Preview-bound deletion of unreachable disposable acquisition files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from projectlore.acquisition.digest import content_digest
from projectlore.acquisition.models import KnowledgeProposal
from projectlore.acquisition.store import KnowledgeStore
from projectlore.acquisition.transactions import FileLock

RETAIN_GENERATIONS = 32


def _bytes_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def compaction_preview(repository: Path) -> dict[str, Any]:
    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    if not store.active_root.exists():
        payload: dict[str, Any] = {
            "contract_version": "projectlore-compaction-preview/0.6.1",
            "active_root": None,
            "retained_generations": [],
            "deletions": [],
        }
    else:
        active = store.current_root()
        generations = store.valid_generations()
        retained = {item.generation_id for item in generations[-RETAIN_GENERATIONS:]}
        retained.add(active.generation_id)
        reachable_objects: set[str] = set()
        for generation in generations:
            if generation.generation_id not in retained:
                continue
            generation_root = store.root_for_generation(generation.generation_id)
            reachable_objects.update(generation_root.members)
        reachable_blobs: set[str] = set()
        for member in reachable_objects:
            item = store.get_object(member)
            if item.get("contract_version") == "projectlore-knowledge-proposal/0.6.1":
                proposal = KnowledgeProposal.model_validate(item)
                reachable_blobs.update(file.digest for file in proposal.candidate.files)
        deletions: list[dict[str, str]] = []
        if store.generations.is_dir():
            for directory in store.generations.iterdir():
                generation_id = f"sha256:{directory.name}"
                if directory.is_dir() and generation_id not in retained:
                    for path in directory.rglob("*"):
                        if path.is_file() and not path.is_symlink():
                            deletions.append(
                                {
                                    "path": path.relative_to(root).as_posix(),
                                    "digest": _bytes_digest(path),
                                }
                            )
        for directory, reachable, suffix in (
            (store.objects, reachable_objects, ".json"),
            (store.directory / "blobs", reachable_blobs, ""),
        ):
            if not directory.is_dir():
                continue
            for path in directory.rglob("*"):
                if not path.is_file() or path.is_symlink():
                    continue
                identity = f"sha256:{path.name.removesuffix(suffix)}"
                if identity not in reachable:
                    deletions.append(
                        {
                            "path": path.relative_to(root).as_posix(),
                            "digest": _bytes_digest(path),
                        }
                    )
        payload = {
            "contract_version": "projectlore-compaction-preview/0.6.1",
            "active_root": active.root_digest,
            "retained_generations": sorted(retained),
            "deletions": sorted(deletions, key=lambda item: item["path"]),
        }
    preview_digest = content_digest("projectlore:compaction-preview:0.6.1", payload)
    return {**payload, "preview_digest": preview_digest, "applied": False}


def apply_compaction(repository: Path, preview_digest: str) -> dict[str, Any]:
    root = repository.resolve(strict=True)
    store = KnowledgeStore(root)
    with FileLock(store.directory / "locks" / "workflow.lock"):
        preview = compaction_preview(root)
        if preview["preview_digest"] != preview_digest:
            raise ValueError("Compaction preview no longer matches current state.")
        for entry in preview["deletions"]:
            path = root.joinpath(*Path(entry["path"]).parts).resolve(strict=True)
            if not path.is_relative_to(root) or path.is_symlink():
                raise ValueError("Compaction target escapes the repository.")
            if _bytes_digest(path) != entry["digest"]:
                raise ValueError(f"Compaction target drifted: {path}")
        for entry in preview["deletions"]:
            root.joinpath(*Path(entry["path"]).parts).unlink()
    return {**preview, "applied": True}
