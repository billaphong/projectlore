"""Frozen public-boundary acceptance probes for knowledge acquisition v1.

These tests deliberately depend only on the installed ``lore`` command.  They
are an initial executable gate, not a substitute for the fault, concurrency,
and real-client evidence required by the governing contract.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def _lore(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "projectlore.cli", *args],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


@pytest.mark.parametrize(
    ("case_id", "command"),
    [
        ("KA02", "onboard"),
        ("KA03", "knowledge"),
        ("KA06", "knowledge"),
        ("KA11", "onboard"),
        ("KA12", "knowledge"),
    ],
    ids=lambda value: value,
)
def test_required_public_workflow_is_reachable(case_id: str, command: str) -> None:
    """The contract cannot be accepted while its public command groups are absent."""
    result = _lore(command, "--help")
    assert result.returncode == 0, (
        f"{case_id}: required public command group {command!r} is not discoverable; "
        f"stderr={result.stderr!r}"
    )


def test_core_mcp_contract_remains_frozen() -> None:
    """KA-10: acquisition must not alter the frozen core MCP 0.4 contract."""
    from projectlore.tool_spec import TOOLS_CONTRACT_VERSION

    assert TOOLS_CONTRACT_VERSION == "projectlore-tools/0.4.0"
    assert (
        hashlib.sha256(
            (ROOT / "src/projectlore/tool_spec.py")
            .read_text(encoding="utf-8")
            .encode("utf-8")
        ).hexdigest()
        == "74264d4a44d49ff35e25de1223c81a1ef58a4d5e2005a13f5a900290acc8f782"
    )


def test_core_read_does_not_create_acquisition_state(tmp_path: Path) -> None:
    """KA-01/KA-10: an existing read path must not create workflow state."""
    model = ROOT / "examples" / "homebrew.project.yaml"
    result = _lore("model-status", str(model), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".projectlore" / "knowledge").exists()
