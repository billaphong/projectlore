from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from projectlore.onboarding import (
    apply_initialization,
    initialization_previews,
)
from projectlore.validation import validate_path


def test_initialization_is_preview_first_and_creates_valid_project(
    tmp_path: Path,
) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Existing instructions\n\nKeep this.\n", encoding="utf-8")

    previews = initialization_previews(tmp_path, project_name="Acme Tools")

    assert list(tmp_path.iterdir()) == [agents]
    assert all(item.conflict is None for item in previews)
    apply_initialization(previews)

    _, report = validate_path(tmp_path / "projectlore.yaml")
    assert report.valid is True
    assert "review-knowledge-changes" in (tmp_path / "projectlore.yaml").read_text(
        encoding="utf-8"
    )
    assert "Keep this." in agents.read_text(encoding="utf-8")
    assert (tmp_path / "CLAUDE.md").is_file()
    assert (tmp_path / ".mcp.json").is_file()
    assert (tmp_path / ".claude" / "settings.json").is_file()
    assert (tmp_path / ".codex" / "config.toml").is_file()
    assert (tmp_path / ".codex" / "hooks.json").is_file()

    repeated = initialization_previews(tmp_path, project_name="Acme Tools")
    assert all(item.changed is False for item in repeated)


def test_initialization_preserves_unrelated_client_configuration(
    tmp_path: Path,
) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"existing": {"command": "other"}}}),
        encoding="utf-8",
    )
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Read"]}}),
        encoding="utf-8",
    )
    (tmp_path / ".codex" / "config.toml").write_text(
        'model = "gpt-test"\n',
        encoding="utf-8",
    )
    (tmp_path / ".codex" / "hooks.json").write_text(
        json.dumps({"custom": True}),
        encoding="utf-8",
    )

    previews = initialization_previews(tmp_path, project_name="Acme")
    apply_initialization(previews)

    mcp = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    claude = json.loads(
        (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    codex_hooks = json.loads(
        (tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8")
    )
    codex_config = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert mcp["mcpServers"]["existing"]["command"] == "other"
    assert mcp["mcpServers"]["projectlore"]["command"] == "projectlore-mcp"
    assert claude["permissions"] == {"allow": ["Read"]}
    assert codex_hooks["custom"] is True
    assert 'model = "gpt-test"' in codex_config
    assert 'command = "projectlore-mcp"' in codex_config


def test_initialization_rejects_conflicts_and_intervening_drift(
    tmp_path: Path,
) -> None:
    model = tmp_path / "projectlore.yaml"
    model.write_text("user-owned: true\n", encoding="utf-8")
    previews = initialization_previews(tmp_path, project_name="Acme")

    with pytest.raises(ValueError, match="conflicts"):
        apply_initialization(previews)
    assert model.read_text(encoding="utf-8") == "user-owned: true\n"

    model.unlink()
    previews = initialization_previews(tmp_path, project_name="Acme")
    (tmp_path / "AGENTS.md").write_text("# Intervening edit\n", encoding="utf-8")
    with pytest.raises(ValueError, match="drift"):
        apply_initialization(previews)


def test_installed_hook_entrypoint_discovers_canonical_model(
    tmp_path: Path,
) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    event = {
        "cwd": str(tmp_path),
        "tool_name": "Write",
        "tool_input": {"file_path": "ordinary.txt", "content": "allowed"},
    }
    environment = dict(os.environ)
    environment.pop("PROJECTLORE_MODEL", None)
    result = subprocess.run(
        [sys.executable, "-m", "projectlore.hook"],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0
