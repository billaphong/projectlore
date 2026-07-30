from __future__ import annotations

from pathlib import Path

import pytest

from projectlore.doctor import run_doctor
from projectlore.integration import (
    apply_instruction_previews,
    capability_matrix,
    instruction_previews,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"


def test_capability_matrix_names_both_clients_and_degradation() -> None:
    matrix = capability_matrix(ROOT)

    assert matrix["matrix_version"] == "projectlore-client-capabilities/0.1.0"
    assert set(matrix["clients"]) == {"claude_code", "codex_cli"}
    assert "degradation" in matrix["equivalence"]


def test_managed_instruction_preview_preserves_user_content(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# User instructions\n\nKeep this.\n", encoding="utf-8")

    previews = instruction_previews(tmp_path)

    assert agents.read_text(encoding="utf-8") == "# User instructions\n\nKeep this.\n"
    agents_preview = next(item for item in previews if item.path == agents)
    assert "Keep this." in agents_preview.content
    assert "PROJECTLORE_MANAGED_START digest=sha256:" in agents_preview.content


def test_managed_instruction_apply_rejects_intervening_drift(
    tmp_path: Path,
) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# User instructions\n", encoding="utf-8")
    previews = instruction_previews(tmp_path)
    agents.write_text("# Changed after preview\n", encoding="utf-8")

    with pytest.raises(ValueError, match="drift"):
        apply_instruction_previews(previews)


def test_doctor_proves_versions_mcp_identity_and_blocking_hook() -> None:
    result = run_doctor(ROOT, MODEL)

    assert result["healthy"] is True
    assert all(result["checks"].values())
    assert result["hook_probe"]["returncode"] == 2
    assert result["trust"]["verified"] is False
    assert result["enforcement_state"] == "configured_executable_trust_unverified"
