from __future__ import annotations

from pathlib import Path

import pytest

from projectlore.acquisition.compaction import (
    apply_compaction,
    compaction_preview,
)
from projectlore.acquisition.onboarding import start_onboarding
from projectlore.acquisition.store import KnowledgeStore
from projectlore.onboarding import apply_initialization, initialization_previews


def test_compaction_is_preview_bound_and_preserves_active_state(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    store = KnowledgeStore(tmp_path)
    canonical = (tmp_path / "projectlore.yaml").read_bytes()
    for index in range(40):
        evidence = store.put_object(f"example:{index}", {"index": index})
        current = store.current_root()
        generation = store.stage((*current.members, evidence))
        store.activate(generation.generation_id)
    active = store.current_generation()

    preview = compaction_preview(tmp_path)
    assert preview["applied"] is False
    assert preview["deletions"]
    result = apply_compaction(tmp_path, preview["preview_digest"])
    assert result["applied"] is True
    assert store.current_generation() == active
    assert (tmp_path / "projectlore.yaml").read_bytes() == canonical


def test_compaction_rejects_stale_preview(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    preview = compaction_preview(tmp_path)
    store = KnowledgeStore(tmp_path)
    evidence = store.put_object("example:new", {"new": True})
    current = store.current_root()
    staged = store.stage((*current.members, evidence))
    store.activate(staged.generation_id)
    with pytest.raises(ValueError, match="no longer matches"):
        apply_compaction(tmp_path, preview["preview_digest"])
