"""Prepare a wheelhouse, then prove a fresh installation without index access."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def _run(argv: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(argv, check=True, env=env)


def verify(dist: Path, example: Path, schema: Path) -> None:
    wheels = sorted(dist.resolve().glob("projectlore-*.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected exactly one ProjectLore wheel.")
    with tempfile.TemporaryDirectory(prefix="projectlore-alpha-") as raw:
        root = Path(raw)
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--dest",
                str(wheelhouse),
                "--find-links",
                str(dist.resolve()),
                "projectlore==0.1.0a1",
            ]
        )
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = (
            environment / "Scripts" / "python.exe"
            if os.name == "nt"
            else environment / "bin" / "python"
        )
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                "projectlore==0.1.0a1",
            ]
        )
        _run(
            [
                str(python),
                "-m",
                "projectlore.cli",
                "validate",
                str(example.resolve()),
            ]
        )
        generated = root / "projectlore.schema.json"
        _run(
            [
                str(python),
                "-m",
                "projectlore.cli",
                "schema",
                str(generated),
            ]
        )
        if generated.read_bytes() != schema.resolve().read_bytes():
            raise ValueError("Installed package generated a different JSON Schema.")
        _run(
            [
                str(python),
                "-c",
                "from projectlore.mcp_server import create_server; "
                "from projectlore.adapters import AdapterRegistry; "
                "from projectlore.checker import CheckerRegistry; "
                "assert create_server and AdapterRegistry and CheckerRegistry",
            ]
        )
    print("Fresh offline installation smoke suite passed.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: offline_smoke.py DIST EXAMPLE COMMITTED_SCHEMA"
        )
    verify(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
