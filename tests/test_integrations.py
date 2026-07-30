from __future__ import annotations

from pathlib import Path

import pytest

from projectlore.doctor import run_doctor
from projectlore.hook_event import normalize_hook_event
from projectlore.integration import (
    apply_instruction_previews,
    capability_matrix,
    instruction_previews,
)
from projectlore.trust import issue_receipt, verify_receipt, write_receipt

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"


def test_capability_matrix_names_both_clients_and_degradation() -> None:
    matrix = capability_matrix(ROOT)

    assert matrix["matrix_version"] == "projectlore-client-capabilities/0.1.0"
    assert set(matrix["clients"]) == {"claude_code", "codex_cli"}
    assert "degradation" in matrix["equivalence"]


def test_packaged_capability_matrix_matches_documentation(
    tmp_path: Path,
) -> None:
    packaged = capability_matrix(tmp_path)
    documented = capability_matrix(ROOT)

    assert packaged == documented


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


def test_doctor_proves_versions_mcp_identity_and_blocking_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions = {"claude": "2.1.220", "codex": "0.146.0"}
    monkeypatch.setattr(
        "projectlore.doctor._version",
        lambda command, argument: versions[command],
    )
    monkeypatch.setattr(
        "projectlore.doctor._contains",
        lambda path, value: True,
    )
    result = run_doctor(ROOT, MODEL)

    assert result["healthy"] is True
    assert all(result["checks"].values())
    assert result["hook_probe"]["returncode"] == 2
    trust_verified = all(item["verified"] for item in result["trust"].values())
    expected_state = (
        "configured_executable_trust_verified"
        if trust_verified
        else "configured_executable_trust_unverified"
    )
    assert result["enforcement_state"] == expected_state


def test_trust_receipt_is_bound_to_exact_configuration(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# Instructions\n", encoding="utf-8")
    receipt = issue_receipt(tmp_path, "claude_code", "2.1.220")
    write_receipt(tmp_path, receipt)

    assert verify_receipt(tmp_path, "claude_code", "2.1.220")["verified"] is True

    (tmp_path / "CLAUDE.md").write_text("# Changed\n", encoding="utf-8")
    result = verify_receipt(tmp_path, "claude_code", "2.1.220")
    assert result["verified"] is False
    assert result["state"] == "configuration_drift"


def test_both_client_events_normalize_to_equivalent_semantics() -> None:
    raw = {
        "cwd": str(ROOT),
        "tool_name": "Write",
        "tool_input": {"file_path": "policy.json", "content": "{}"},
    }
    claude = normalize_hook_event(raw, client="claude_code")
    codex = normalize_hook_event(raw, client="codex_cli")

    assert claude.event == codex.event == "PreToolUse"
    assert claude.cwd == codex.cwd
    assert claude.tool_name == codex.tool_name
    assert claude.tool_input == codex.tool_input
