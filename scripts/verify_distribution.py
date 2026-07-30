"""Inspect alpha archives against the public distribution allow-list."""

from __future__ import annotations

import re
import sys
import tarfile
import zipfile
from pathlib import Path

FORBIDDEN_PARTS = (
    ".projectlore",
    ".claude",
    ".codex",
    ".mcp.json",
    "evaluations/",
    "homebrew",
    "sienna",
    "__pycache__",
    ".pyc",
)
REQUIRED_SDIST = {
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "README.md",
    "SECURITY.md",
    "docs/architecture.md",
    "docs/client-capabilities.json",
    "docs/compatibility.md",
    "docs/extension-sdk.md",
    "docs/getting-started.md",
    "docs/release-policy.md",
    "docs/versioning-and-migrations.md",
    "examples/contracts/portable.valid.yaml",
    "pyproject.toml",
    "schemas/projectlore.schema.json",
    "src/projectlore/py.typed",
}


def _relative_sdist_names(path: Path) -> set[str]:
    with tarfile.open(path, "r:gz") as archive:
        names = [item.name for item in archive.getmembers() if item.isfile()]
    roots = {name.split("/", 1)[0] for name in names}
    if len(roots) != 1:
        raise ValueError("Source archive must have exactly one root directory.")
    return {name.split("/", 1)[1] for name in names if "/" in name}


def _sdist_file(path: Path, relative_name: str) -> bytes:
    with tarfile.open(path, "r:gz") as archive:
        member = next(
            item
            for item in archive.getmembers()
            if item.isfile() and item.name.endswith(f"/{relative_name}")
        )
        extracted = archive.extractfile(member)
        if extracted is None:
            raise ValueError(f"Cannot read {relative_name} from source archive.")
        return extracted.read()


def _wheel_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return {item.filename for item in archive.infolist() if not item.is_dir()}


def verify(directory: Path) -> None:
    wheels = sorted(directory.glob("projectlore-*.whl"))
    sdists = sorted(directory.glob("projectlore-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Expected exactly one ProjectLore wheel and source archive.")

    wheel_names = _wheel_names(wheels[0])
    sdist_names = _relative_sdist_names(sdists[0])
    all_names = wheel_names | sdist_names
    forbidden = sorted(
        name
        for name in all_names
        if any(part in name.casefold() for part in FORBIDDEN_PARTS)
    )
    if forbidden:
        raise ValueError(
            f"Private or generated paths entered distribution: {forbidden}"
        )

    missing = sorted(REQUIRED_SDIST - sdist_names)
    if missing:
        raise ValueError(f"Source archive is missing intended files: {missing}")
    public_examples = sorted(
        name for name in sdist_names if name.startswith("examples/")
    )
    if public_examples != ["examples/contracts/portable.valid.yaml"]:
        raise ValueError(f"Unexpected public examples: {public_examples}")
    example_text = _sdist_file(sdists[0], public_examples[0]).decode("utf-8")
    credential_key = re.compile(
        r"(?im)^\s*(?:api[_-]?key|access[_-]?token|password|secret|credential)\s*:"
    )
    if credential_key.search(example_text):
        raise ValueError("Public example contains a credential-shaped field.")
    unexpected_wheel = sorted(
        name
        for name in wheel_names
        if not (name.startswith("projectlore/") or ".dist-info/" in name)
    )
    if unexpected_wheel:
        raise ValueError(f"Unexpected wheel paths: {unexpected_wheel}")

    print(
        f"Verified {wheels[0].name} ({len(wheel_names)} files) and "
        f"{sdists[0].name} ({len(sdist_names)} files)."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_distribution.py DIST_DIRECTORY")
    verify(Path(sys.argv[1]))
