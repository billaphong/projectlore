from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import projectlore.acquisition.passive as passive
import projectlore.acquisition_hook as acquisition_hook
from projectlore.acquisition.digest import content_digest
from projectlore.acquisition.onboarding import repository_digest
from projectlore.acquisition.store import KnowledgeStore
from projectlore.acquisition.transactions import FileLock, LockTimeout
from projectlore.acquisition_hook import main, run
from projectlore.onboarding import apply_initialization, initialization_previews


def test_stop_hook_persists_no_prompt_or_transcript(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    private = "PRIVATE_CANARY_NEVER_PERSIST"
    result = run(
        {
            "hook_event_name": "Stop",
            "cwd": str(tmp_path),
            "session_id": "session-private-canary",
            "prompt": private,
            "transcript_path": f"C:/private/{private}",
            "last_assistant_message": private,
        },
        client="claude_code",
    )
    assert result["captured"] is True
    persisted = b"".join(
        path.read_bytes()
        for path in (tmp_path / ".projectlore").rglob("*")
        if path.is_file()
    )
    assert private.encode() not in persisted


def test_stop_hook_persists_only_normalized_metadata_without_scanning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))

    def unexpected_scan(*args: object, **kwargs: object) -> object:
        raise AssertionError("Stop hook entered the repository scanner")

    monkeypatch.setattr(passive, "_tracked_paths", unexpected_scan)
    monkeypatch.setattr(passive, "file_digest", unexpected_scan)
    result = run(
        {
            "hook_event_name": "Stop",
            "cwd": str(tmp_path),
            "session_id": "session-metadata-only",
            "last_assistant_message": "PRIVATE_NOT_PERSISTED",
        },
        client="codex_cli",
    )

    signal = KnowledgeStore(tmp_path).get_object(result["signal_id"])
    observation = {
        "client": "codex_cli",
        "event": "Stop",
        "repository_id": repository_digest(tmp_path),
        "session_id": "session-metadata-only",
        "changed_paths": [],
    }
    assert signal["event"] == "stop"
    assert signal["paths"] == []
    assert signal["observed_digest"] == content_digest(
        "projectlore:hook-observation:0.6.1", observation
    )


def test_session_start_leases_without_scanning(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    result = run(
        {"hook_event_name": "SessionStart", "cwd": str(tmp_path)},
        client="codex_cli",
    )
    assert result == {
        "captured": False,
        "client": "codex_cli",
        "event": "SessionStart",
        "packet_id": None,
    }


def test_session_start_defers_quickly_when_workflow_is_busy(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    run(
        {
            "hook_event_name": "Stop",
            "cwd": str(tmp_path),
            "session_id": "session-contention",
        },
        client="codex_cli",
    )
    store = KnowledgeStore(tmp_path)
    before = store.current_root()
    workflow_lock = store.directory / "locks" / "workflow.lock"

    with FileLock(workflow_lock):
        started = time.monotonic()
        with pytest.raises(LockTimeout, match="workflow.lock"):
            run(
                {"hook_event_name": "SessionStart", "cwd": str(tmp_path)},
                client="codex_cli",
            )
        elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert store.current_root() == before
    assert not (store.directory / "locks" / "canonical.lock").exists()


def test_session_start_skips_locks_when_no_recovery_is_needed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))

    def fail_if_entered(self: FileLock) -> FileLock:
        raise AssertionError(f"unexpected lock acquisition: {self.path}")

    monkeypatch.setattr(FileLock, "__enter__", fail_if_entered)
    result = run(
        {"hook_event_name": "SessionStart", "cwd": str(tmp_path)},
        client="codex_cli",
    )
    assert result["packet_id"] is None


def test_hook_malformed_input_is_advisory(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Entrypoint behavior is exercised through a tiny stdin replacement.
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"not-json")))
    assert main(["--client", "codex_cli", "--root", "."]) == 0
    captured = capsys.readouterr()
    assert "unavailable" in captured.err
    assert json.loads(captured.out) == {"continue": True}


def test_hook_lock_timeout_is_coded_advisory(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    import io
    import sys

    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))

    def timeout(_repository: Path, *, lock_timeout: float = 5.0) -> str:
        raise LockTimeout(f"injected after {lock_timeout}")

    monkeypatch.setattr(acquisition_hook, "recover_commit_claim", timeout)
    payload = json.dumps(
        {"hook_event_name": "SessionStart", "cwd": str(tmp_path)}
    ).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload)))
    assert main(["--client", "codex_cli", "--root", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert "PLKA3003" in captured.err
    assert json.loads(captured.out) == {"continue": True}


def test_codex_stop_entrypoint_emits_valid_continue_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    import io
    import sys

    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "cwd": str(tmp_path),
            "session_id": "session-entrypoint",
        }
    ).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload)))

    assert main(["--client", "codex_cli", "--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"continue": True}


def test_initialization_wires_acquisition_hooks(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    claude = json.loads(
        (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    codex = json.loads((tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    assert (
        "projectlore-acquisition-hook --client claude_code --root ."
        in json.dumps(claude)
    )
    assert (
        "projectlore-acquisition-hook --client codex_cli --root ."
        in json.dumps(codex)
    )


def test_hook_rejects_cwd_outside_configured_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    outside = tmp_path / "outside"
    repository.mkdir()
    outside.mkdir()
    with pytest.raises(ValueError, match="outside"):
        run(
            {
                "hook_event_name": "Stop",
                "cwd": str(outside),
                "session_id": "session-outside",
            },
            client="codex_cli",
            repository=repository,
        )
    assert not (outside / ".projectlore").exists()
