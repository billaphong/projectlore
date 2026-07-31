"""Verify implementation-ready artifact hashes without claiming a release tag."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def verify(manifest_path: Path, dist: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("Local artifact manifest has no artifacts.")
    actual_names = {path.name for path in dist.iterdir() if path.is_file()}
    if actual_names != set(artifacts):
        raise ValueError("Artifact directory does not match the manifest allow-list.")
    for name, expected in artifacts.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise ValueError("Artifact manifest entries must be strings.")
        actual = hashlib.sha256((dist / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Artifact hash mismatch: {name}")
    print(f"Verified {len(artifacts)} implementation-ready artifacts.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_local_artifacts.py MANIFEST DIST")
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
