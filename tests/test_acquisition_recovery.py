from __future__ import annotations

import json
from pathlib import Path

import pytest

from projectlore.acquisition.onboarding import start_onboarding
from projectlore.acquisition.recovery import (
    apply_repair,
    recovery_status,
    repair_preview,
)
from projectlore.acquisition.store import KnowledgeStore
from projectlore.onboarding import apply_initialization, initialization_previews


def test_recovery_is_read_only_and_repair_preserves_canonical(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    store = KnowledgeStore(tmp_path)
    canonical = (tmp_path / "projectlore.yaml").read_bytes()
    selected = store.current_generation()
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert recovery_status(tmp_path)["state"] == "current"
    preview = repair_preview(tmp_path)
    assert preview["selected_root"] == selected.root_digest
    after_preview = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert before == after_preview
    result = apply_repair(tmp_path, preview["preview_digest"])
    assert result["receipt"]["canonical_before"] == result["receipt"]["canonical_after"]
    assert result["generation"]["generation_id"] != selected.generation_id
    assert result["generation"]["state"] == "terminal"
    assert (tmp_path / "projectlore.yaml").read_bytes() == canonical


def test_corrupt_root_reports_then_repairs_only_selected_generation(
    tmp_path: Path,
) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    store = KnowledgeStore(tmp_path)
    selected = store.current_generation()
    root = json.loads(store.active_root.read_text(encoding="utf-8"))
    root["members"] = []
    store.active_root.write_text(json.dumps(root), encoding="utf-8")

    assert recovery_status(tmp_path)["state"] == "corrupt"
    preview = repair_preview(tmp_path)
    assert preview["selected_root"] == selected.root_digest
    apply_repair(tmp_path, preview["preview_digest"])
    assert recovery_status(tmp_path)["state"] == "current"


def test_repair_rejects_stale_preview_without_activation(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    store = KnowledgeStore(tmp_path)
    preview = repair_preview(tmp_path)
    store.active_root.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="PLKA6009"):
        apply_repair(tmp_path, preview["preview_digest"])


def test_repair_binds_highest_generation_when_root_digest_repeats(
    tmp_path: Path,
) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    store = KnowledgeStore(tmp_path)
    repeated = store.stage(store.current_root().members)
    store.activate(repeated.generation_id)
    preview = repair_preview(tmp_path)
    result = apply_repair(tmp_path, preview["preview_digest"])
    assert result["generation"]["sequence"] == repeated.sequence + 1
    records = result["receipt"]["query_equivalence"]["records"]
    assert len(records) == 3
    assert all(record["equal"] for record in records)
    assert all(record["before_digest"] == record["after_digest"] for record in records)
