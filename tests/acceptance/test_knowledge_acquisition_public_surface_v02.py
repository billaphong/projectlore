"""Challenge KAC-CH-001: independently derived public-surface probes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def _help(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "projectlore.cli", *arguments, "--help"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


PUBLIC_OPERATIONS = [
    ("KA-01", ("knowledge", "status")),
    ("KA-02", ("onboard", "start")),
    ("KA-03", ("knowledge", "review")),
    ("KA-04", ("knowledge", "apply")),
    ("KA-05", ("knowledge", "packet", "next")),
    ("KA-06", ("knowledge", "packet", "next")),
    ("KA-07", ("knowledge", "review")),
    ("KA-08", ("knowledge", "apply")),
    ("KA-09", ("knowledge", "recover")),
    ("KA-10", ("knowledge", "status")),
    ("KA-11", ("onboard", "status")),
    ("KA-12", ("remove",)),
    ("KA-13", ("knowledge", "propose")),
    ("KA-14", ("onboard", "start")),
    ("KO-01", ("onboard", "start")),
    ("KO-02", ("knowledge", "scan")),
    ("KO-03", ("knowledge", "packet", "next")),
    ("KO-04", ("knowledge", "review")),
    ("KO-05", ("knowledge", "apply")),
    ("KO-06", ("knowledge", "status")),
    ("KO-07", ("knowledge", "repair")),
    ("KR-01", ("knowledge", "recover")),
    ("KR-02", ("knowledge", "recover")),
    ("KR-03", ("knowledge", "recover")),
    ("KR-04", ("onboard", "status")),
    ("KR-05", ("knowledge", "repair")),
    ("KR-06", ("remove",)),
]


@pytest.mark.parametrize(("requirement_id", "arguments"), PUBLIC_OPERATIONS)
def test_contract_operation_is_publicly_discoverable(
    requirement_id: str, arguments: tuple[str, ...]
) -> None:
    result = _help(*arguments)
    assert result.returncode == 0, (
        f"{requirement_id}: public operation {' '.join(arguments)!r} is absent; "
        f"stderr={result.stderr!r}"
    )
