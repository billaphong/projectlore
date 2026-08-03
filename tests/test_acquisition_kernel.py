from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from projectlore.acquisition.digest import CanonicalizationError, content_digest
from projectlore.acquisition.models import GenerationState, KnowledgeRoot
from projectlore.acquisition.schema import render_acquisition_schema
from projectlore.acquisition.store import CorruptStore, KnowledgeStore
from projectlore.acquisition.transactions import (
    CanonicalWorkflowTransaction,
    FileLock,
    LockTimeout,
    WorkflowTransaction,
)
from projectlore.acquisition.validation import UnsafePathError, confined_path
from projectlore.cli import main


def test_domain_separated_digest_matches_frozen_vector() -> None:
    value = {
        "client": "codex_cli",
        "event": "Stop",
        "repository_id": "sha256:" + "a" * 64,
        "session_id": "s",
        "changed_paths": [],
    }
    assert content_digest("projectlore:hook-observation:0.6.1", value) == (
        "sha256:aca9f1e36de4fcbdceb1d745eab42072344f1a6da1ec7620ca9d316487dad57f"
    )
    with pytest.raises(CanonicalizationError):
        content_digest("test", {"value": 0.5})


def test_kernel_schema_is_versioned_and_machine_readable() -> None:
    schema = json.loads(render_acquisition_schema())
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("acquisition-kernel-0.6.1.json")
    assert {
        "KnowledgeSignal",
        "KnowledgePacket",
        "KnowledgeProposal",
        "KnowledgeReview",
        "Generation",
        "KnowledgeRoot",
    } <= set(schema["x-projectlore-public-contracts"])


def test_acquisition_schema_cli_detects_drift(tmp_path: Path) -> None:
    output = tmp_path / "acquisition.schema.json"
    assert main(["acquisition-schema", str(output)]) == 0
    assert main(["acquisition-schema", str(output), "--check"]) == 0
    output.write_text("{}\n", encoding="utf-8")
    assert main(["acquisition-schema", str(output), "--check"]) == 1


def test_strict_root_rejects_unknown_and_unsorted_members() -> None:
    digest = "sha256:" + "a" * 64
    with pytest.raises(ValidationError):
        KnowledgeRoot(
            root_digest=digest,
            generation_id=digest,
            members=("sha256:" + "b" * 64, digest),
        )
    with pytest.raises(ValidationError):
        KnowledgeRoot.model_validate(
            {"root_digest": digest, "generation_id": digest, "surprise": True}
        )


def test_transaction_stages_and_atomically_activates_generation(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path)
    initial = store.initialize()
    evidence = store.put_object("example:evidence:1", {"path": "README.md"})
    staged = store.stage((evidence,))
    assert store.current_generation() == initial

    store.activate(staged.generation_id)

    assert store.current_generation() == staged
    assert store.current_root().members == (evidence,)
    assert store.recover() == staged


def test_transaction_commit_is_a_complete_generation(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path)
    store.initialize()
    evidence = store.put_object("example:evidence:1", {"path": "AGENTS.md"})
    committed = WorkflowTransaction(store).commit(
        [evidence], state=GenerationState.OUTSTANDING
    )
    assert committed.sequence == 1
    assert store.current_generation().state is GenerationState.OUTSTANDING


def test_concurrent_commits_preserve_both_members(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path)
    store.initialize()
    members = [
        store.put_object(f"example:{index}", {"index": index}) for index in range(2)
    ]
    barrier = threading.Barrier(2)

    def commit(member: str) -> None:
        barrier.wait()
        WorkflowTransaction(store).commit([member])

    threads = [threading.Thread(target=commit, args=(member,)) for member in members]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)
    assert set(store.current_root().members) == set(members)


def test_dead_owner_lock_is_reclaimed(tmp_path: Path) -> None:
    lock = tmp_path / "locks" / "workflow.lock"
    lock.parent.mkdir()
    lock.write_text("pid=2147483647\n", encoding="ascii")
    with FileLock(lock, timeout=0.1):
        assert lock.exists()
    assert not lock.exists()


def test_object_lookup_rejects_traversal_and_tampering(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path)
    with pytest.raises(CorruptStore, match="invalid"):
        store.get_object("../../outside")
    identity = store.put_object(
        "projectlore:knowledge-packet:0.6.1",
        {
            "contract_version": "projectlore-knowledge-packet/0.6.1",
            "packet_id": "sha256:" + "0" * 64,
            "base_model_digest": "sha256:" + "1" * 64,
            "signal_ids": ["sha256:" + "2" * 64],
            "state": "outstanding",
        },
        exclude=("packet_id",),
    )
    object_path = store.objects / identity[7:9] / f"{identity[7:]}.json"
    value = json.loads(object_path.read_text(encoding="utf-8"))
    value["state"] = "changed"
    object_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(CorruptStore, match="mismatch"):
        store.get_object(identity)

    unknown = store.put_object(
        "example:unknown:1",
        {"contract_version": "projectlore-unknown/9.9.9", "value": True},
    )
    with pytest.raises(CorruptStore, match="unknown immutable object contract"):
        store.get_object(unknown)


def test_active_generation_identity_is_recomputed(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path)
    generation = store.initialize()
    path = store.generations / generation.generation_id[7:] / "generation.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["state"] = "terminal"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(CorruptStore, match="generation identity"):
        store.current_generation()


def test_corrupt_active_root_fails_closed(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path)
    store.initialize()
    root = json.loads(store.active_root.read_text(encoding="utf-8"))
    root["members"] = ["sha256:" + "f" * 64]
    store.active_root.write_text(json.dumps(root), encoding="utf-8")
    with pytest.raises(CorruptStore, match="digest"):
        store.recover()


def test_lock_is_exclusive_and_canonical_precedes_workflow(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path)
    workflow_path = store.directory / "locks" / "workflow.lock"
    started = threading.Event()
    result: list[type[BaseException]] = []

    def contender() -> None:
        started.set()
        try:
            with FileLock(workflow_path, timeout=0.05):
                pass
        except BaseException as error:
            result.append(type(error))

    with CanonicalWorkflowTransaction(store):
        assert (store.directory / "locks" / "canonical.lock").exists()
        assert workflow_path.exists()
        thread = threading.Thread(target=contender)
        thread.start()
        started.wait(timeout=1)
        thread.join(timeout=1)
    assert result == [LockTimeout]


def test_confined_path_rejects_escape_and_symlink(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        confined_path(tmp_path, "../escape")
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(UnsafePathError, match="symlink"):
        confined_path(tmp_path, "link/file")


def test_store_rejects_symlinked_knowledge_ancestor(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    projectlore = tmp_path / ".projectlore"
    projectlore.mkdir()
    knowledge = projectlore / "knowledge"
    try:
        knowledge.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(CorruptStore, match="symlink or reparse"):
        KnowledgeStore(tmp_path)
