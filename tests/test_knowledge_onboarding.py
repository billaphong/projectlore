from __future__ import annotations

import json
from pathlib import Path

import pytest

from projectlore.acquisition.models import (
    GenerationState,
    ProposalClassification,
    ReviewDisposition,
)
from projectlore.acquisition.onboarding import onboarding_preview, start_onboarding
from projectlore.acquisition.passive import (
    capture_scan,
    knowledge_status,
    next_packet,
)
from projectlore.acquisition.proposal import submit_proposal
from projectlore.acquisition.review import (
    apply_review,
    recover_commit_claim,
    review_proposal,
)
from projectlore.acquisition.store import KnowledgeStore
from projectlore.cli import main
from projectlore.onboarding import apply_initialization, initialization_previews


def initialized_repository(tmp_path: Path) -> Path:
    (tmp_path / "AGENTS.md").write_text("# Agent rules\n", encoding="utf-8")
    previews = initialization_previews(tmp_path, project_name="Acme")
    apply_initialization(previews)
    return tmp_path


def test_onboarding_preview_is_no_write(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Acme\n", encoding="utf-8")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    preview = onboarding_preview(tmp_path)
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert preview["applied"] is False
    assert preview["base_model_digest"].startswith("sha256:")
    assert before == after


def test_proposal_requires_review_before_canonical_apply(tmp_path: Path) -> None:
    root = initialized_repository(tmp_path)
    original = (root / "projectlore.yaml").read_bytes()
    _, packet = start_onboarding(root)
    candidate = root / "candidate.yaml"
    candidate.write_bytes(original.replace(b"Shared project", b"Accepted project"))

    proposal = submit_proposal(root, candidate, packet.packet_id)
    assert (root / "projectlore.yaml").read_bytes() == original
    review = review_proposal(
        root,
        proposal.proposal_id,
        ReviewDisposition.ACCEPT,
        "billaphong",
    )
    assert (root / "projectlore.yaml").read_bytes() == original
    assert (
        review_proposal(
            root,
            proposal.proposal_id,
            ReviewDisposition.ACCEPT,
            "billaphong",
        )
        == review
    )

    applied = apply_review(root, review.review_id)
    assert applied == root / "projectlore.yaml"
    assert b"Accepted project" in applied.read_bytes()
    assert apply_review(root, review.review_id) == applied
    receipts = [
        KnowledgeStore(root).get_object(member)
        for member in KnowledgeStore(root).current_root().members
    ]
    assert any(
        item.get("contract_version") == "projectlore-knowledge-receipt/0.6.1"
        and item.get("result") == "accepted"
        for item in receipts
    )


def test_rejected_and_stale_proposals_cannot_apply(tmp_path: Path) -> None:
    root = initialized_repository(tmp_path)
    original = (root / "projectlore.yaml").read_bytes()
    _, packet = start_onboarding(root)
    candidate = root / "candidate.yaml"
    candidate.write_bytes(original)
    proposal = submit_proposal(root, candidate, packet.packet_id)
    rejected = review_proposal(
        root, proposal.proposal_id, ReviewDisposition.REJECT, "reviewer"
    )
    with pytest.raises(ValueError, match="accepted"):
        apply_review(root, rejected.review_id)

    with pytest.raises(ValueError, match="terminal review"):
        review_proposal(
            root, proposal.proposal_id, ReviewDisposition.ACCEPT, "reviewer"
        )

    _, second_packet = start_onboarding(root)
    second_proposal = submit_proposal(
        root,
        candidate,
        second_packet.packet_id,
        classification=ProposalClassification.INFERRED_SUGGESTION,
    )
    accepted = review_proposal(
        root, second_proposal.proposal_id, ReviewDisposition.ACCEPT, "reviewer"
    )
    (root / "projectlore.yaml").write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="PLKA2001"):
        apply_review(root, accepted.review_id)


def test_cli_runs_complete_reviewed_onboarding_lifecycle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = initialized_repository(tmp_path)
    candidate = root / "candidate.yaml"
    candidate.write_bytes((root / "projectlore.yaml").read_bytes())

    assert main(["onboard", "start", "--root", str(root), "--apply"]) == 0
    packet_id = json.loads(capsys.readouterr().out)["packet"]["packet_id"]
    assert (
        main(
            [
                "knowledge",
                "propose",
                str(candidate),
                "--packet-id",
                packet_id,
                "--root",
                str(root),
            ]
        )
        == 0
    )
    proposal_id = json.loads(capsys.readouterr().out)["proposal_id"]
    assert (
        main(
            [
                "knowledge",
                "review",
                proposal_id,
                "--disposition",
                "accept",
                "--actor",
                "reviewer",
                "--root",
                str(root),
            ]
        )
        == 0
    )
    review_id = json.loads(capsys.readouterr().out)["review_id"]
    assert main(["knowledge", "apply", review_id, "--root", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["applied"] is True


def test_apply_rolls_workflow_forward_after_canonical_only_commit(
    tmp_path: Path,
) -> None:
    root = initialized_repository(tmp_path)
    _, packet = start_onboarding(root)
    candidate = root / "candidate.yaml"
    candidate.write_bytes(
        (root / "projectlore.yaml")
        .read_bytes()
        .replace(b"Shared project", b"Recovered project")
    )
    proposal = submit_proposal(root, candidate, packet.packet_id)
    review = review_proposal(
        root, proposal.proposal_id, ReviewDisposition.ACCEPT, "reviewer"
    )

    # Represents interruption after canonical replacement but before workflow root.
    (root / "projectlore.yaml").write_bytes(candidate.read_bytes())
    assert apply_review(root, review.review_id) == root / "projectlore.yaml"
    assert review.review_id in KnowledgeStore(root).current_root().members


def test_recovery_rolls_forward_persisted_commit_claim(tmp_path: Path) -> None:
    root = initialized_repository(tmp_path)
    _, packet = start_onboarding(root)
    candidate = root / "candidate.yaml"
    candidate.write_bytes(
        (root / "projectlore.yaml")
        .read_bytes()
        .replace(b"Shared project", b"Recovered claim project")
    )
    proposal = submit_proposal(root, candidate, packet.packet_id)
    review = review_proposal(
        root, proposal.proposal_id, ReviewDisposition.ACCEPT, "reviewer"
    )
    store = KnowledgeStore(root)
    claim = store.stage(
        (*store.current_root().members, review.review_id),
        GenerationState.COMMIT_CLAIMED,
    )
    store.activate(claim.generation_id)
    (root / "projectlore.yaml").write_bytes(candidate.read_bytes())

    assert recover_commit_claim(root) == "rolled_forward"
    assert store.current_generation().state is GenerationState.TERMINAL
    assert any(
        store.get_object(member).get("result") == "accepted"
        for member in store.current_root().members
    )


def test_revise_releases_evidence_for_a_new_packet(tmp_path: Path) -> None:
    root = initialized_repository(tmp_path)
    _, packet = start_onboarding(root)
    candidate = root / "candidate.yaml"
    candidate.write_bytes((root / "projectlore.yaml").read_bytes())
    proposal = submit_proposal(root, candidate, packet.packet_id)
    review_proposal(
        root,
        proposal.proposal_id,
        ReviewDisposition.REVISE,
        "reviewer",
        revision_note="Add missing provenance",
    )
    replacement = next_packet(root)
    assert replacement is not None
    assert replacement.signal_ids == packet.signal_ids


def test_passive_scan_is_deduplicated_and_leased_after_terminal_packet(
    tmp_path: Path,
) -> None:
    root = initialized_repository(tmp_path)
    _, bootstrap = start_onboarding(root)
    candidate = root / "candidate.yaml"
    candidate.write_bytes((root / "projectlore.yaml").read_bytes())
    proposal = submit_proposal(root, candidate, bootstrap.packet_id)
    review_proposal(root, proposal.proposal_id, ReviewDisposition.REJECT, "reviewer")

    first = capture_scan(root)
    sequence = KnowledgeStore(root).current_generation().sequence
    second = capture_scan(root)
    assert second.signal_id == first.signal_id
    assert KnowledgeStore(root).current_generation().sequence == sequence

    packet = next_packet(root)
    assert packet is not None
    assert packet.signal_ids == (first.signal_id,)
    assert next_packet(root) == packet


def test_status_is_read_only(tmp_path: Path) -> None:
    root = initialized_repository(tmp_path)
    start_onboarding(root)
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    status = knowledge_status(root)
    after = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert status["state"] == "outstanding"
    assert before == after
