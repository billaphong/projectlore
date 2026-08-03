from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from projectlore.acquisition.onboarding import start_onboarding
from projectlore.integration import apply_instruction_previews, instruction_previews
from projectlore.onboarding import apply_initialization, initialization_previews
from projectlore.removal import (
    acquisition_removal_preview,
    apply_acquisition_removal,
    apply_removal,
    removal_previews,
)


def test_removal_preserves_client_owned_content_and_deletes_generated_state(
    tmp_path: Path,
) -> None:
    (tmp_path / "AGENTS.md").write_text("Owner instructions\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("Claude owner text\n", encoding="utf-8")
    apply_instruction_previews(instruction_previews(tmp_path))
    (tmp_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "owner": {"command": "owner-server"},
                    "projectlore": {"command": "projectlore-mcp"},
                }
            }
        ),
        encoding="utf-8",
    )
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(
        json.dumps(
            {
                "owner": True,
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"command": "projectlore-scope-hook"}]},
                        {"hooks": [{"command": "owner-hook"}]},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    state = tmp_path / ".projectlore"
    state.mkdir()
    (state / "workflow-context.json").write_text("{}", encoding="utf-8")
    trust = state / "trust"
    trust.mkdir()
    (trust / "codex_cli.json").write_text("{}", encoding="utf-8")

    previews = removal_previews(tmp_path)
    assert "Owner instructions" in (tmp_path / "AGENTS.md").read_text()
    apply_removal(previews)

    assert (tmp_path / "AGENTS.md").read_text() == "Owner instructions\n"
    assert (tmp_path / "CLAUDE.md").read_text() == "Claude owner text\n"
    mcp = json.loads((tmp_path / ".mcp.json").read_text())
    assert set(mcp["mcpServers"]) == {"owner"}
    hooks = json.loads(settings.read_text())["hooks"]["SessionStart"]
    assert hooks == [{"hooks": [{"command": "owner-hook"}]}]
    assert not (state / "workflow-context.json").exists()
    assert not (trust / "codex_cli.json").exists()


def test_acquisition_removal_is_digest_bound_and_preserves_queries(
    tmp_path: Path,
) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    preview = acquisition_removal_preview(tmp_path)
    result = apply_acquisition_removal(tmp_path, str(preview["preview_digest"]))
    assert result["applied"] is True
    receipt = result["receipt"]
    assert receipt["canonical_before"] == receipt["canonical_after"]
    assert receipt["query_equivalence"]
    assert receipt["query_equivalence"]["suite_digest"] == (
        "sha256:13b074e029b517b862ac3210e472d1f4b30430aa884841819b0e4b5388680156"
    )
    schema = json.loads(
        Path("docs/contracts/knowledge-acquisition-v0.6.1/schemas.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator({**schema, "$ref": "#/$defs/lifecycle_receipt"}).validate(
        receipt
    )
    knowledge = tmp_path / ".projectlore" / "knowledge"
    assert not any(
        path.is_file() and "locks" not in path.relative_to(knowledge).parts
        for path in knowledge.rglob("*")
    )


def test_acquisition_removal_rejects_stale_preview(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    preview = acquisition_removal_preview(tmp_path)
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="PLKA6001"):
        apply_acquisition_removal(tmp_path, str(preview["preview_digest"]))
