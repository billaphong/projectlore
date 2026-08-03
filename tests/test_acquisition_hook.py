from __future__ import annotations

import json
from pathlib import Path

import pytest

from projectlore.acquisition_hook import main, run
from projectlore.onboarding import apply_initialization, initialization_previews


def test_stop_hook_persists_no_prompt_or_transcript(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    private = "PRIVATE_CANARY_NEVER_PERSIST"
    result = run(
        {
            "hook_event_name": "Stop",
            "cwd": str(tmp_path),
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


def test_hook_malformed_input_is_advisory(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Entrypoint behavior is exercised through a tiny stdin replacement.
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"not-json")))
    assert main(["--client", "codex_cli", "--root", "."]) == 0
    assert "unavailable" in capsys.readouterr().err


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
            {"hook_event_name": "Stop", "cwd": str(outside)},
            client="codex_cli",
            repository=repository,
        )
    assert not (outside / ".projectlore").exists()
