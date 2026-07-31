from __future__ import annotations

import json
from pathlib import Path

from projectlore.integration import apply_instruction_previews, instruction_previews
from projectlore.removal import apply_removal, removal_previews


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
