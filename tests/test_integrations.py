from __future__ import annotations

from pathlib import Path

import pytest

from projectlore.doctor import SUPPORTED_SCHEMA_VERSIONS, run_doctor
from projectlore.hook_event import normalize_hook_event
from projectlore.integration import (
    apply_instruction_previews,
    capability_matrix,
    instruction_previews,
)
from projectlore.onboarding import apply_initialization, initialization_previews
from projectlore.trust import issue_receipt, verify_receipt, write_receipt

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"


def test_capability_matrix_names_both_clients_and_degradation() -> None:
    matrix = capability_matrix(ROOT)

    assert matrix["matrix_version"] == "projectlore-client-capabilities/0.1.0"
    assert set(matrix["clients"]) == {"claude_code", "codex_cli"}
    assert "degradation" in matrix["equivalence"]
    assert "0.2.0" in SUPPORTED_SCHEMA_VERSIONS


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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_initialization(
        initialization_previews(tmp_path, project_name="Doctor Acceptance")
    )
    versions = {"claude": "2.1.220", "codex": "0.146.0"}
    monkeypatch.setattr(
        "projectlore.doctor._version",
        lambda command, argument: versions[command],
    )
    for client, version in (
        ("claude_code", "2.1.220"),
        ("codex_cli", "0.146.0"),
    ):
        write_receipt(tmp_path, issue_receipt(tmp_path, client, version))
    result = run_doctor(tmp_path, tmp_path / "projectlore.yaml")

    assert result["healthy"] is True
    assert result["ready"] is True
    assert result["operational"] is True
    assert all(result["checks"].values())
    assert result["hook_probe"]["returncode"] == 2
    assert Path(result["hook_probe"]["cwd"]) == tmp_path / ".claude"
    assert result["hook_probe"]["model_discovery"] == "ancestor"
    assert result["process_probe"]["initialized"] is True
    assert result["enforcement_state"] == "configured_executable_trust_verified"


def test_doctor_rejects_marker_only_config_and_unverified_trust(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_initialization(
        initialization_previews(tmp_path, project_name="Doctor Rejection")
    )
    (tmp_path / ".mcp.json").write_text(
        '{"note": "projectlore"}\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        "projectlore.doctor._version",
        lambda command, argument: (
            "2.1.220" if command == "claude" else "0.146.0"
        ),
    )

    result = run_doctor(tmp_path, tmp_path / "projectlore.yaml")

    assert result["checks"]["claude_mcp_configured"] is False
    assert result["operational"] is False
    assert result["healthy"] is False
    assert result["ready"] is False
    assert result["enforcement_state"] == "not_operational"


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
