"""Fail-closed verification of immutable release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import zipfile
from pathlib import Path
from typing import Any

TAG_PATTERN = re.compile(r"v(?P<version>\d+\.\d+\.\d+(?:a\d+)?)\Z")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def verify_release(
    manifest_path: Path,
    dist: Path,
    *,
    tag: str,
    tag_commit: str,
) -> None:
    manifest = _read_manifest(manifest_path)
    match = TAG_PATTERN.fullmatch(tag)
    if match is None:
        raise ValueError(f"Invalid release tag: {tag}")
    version = match.group("version")
    if manifest.get("tag") != tag:
        raise ValueError("Release manifest tag does not match requested tag.")
    if manifest.get("version") != version:
        raise ValueError("Release manifest version does not match the tag.")
    expected_commit = manifest.get("commit")
    if not isinstance(expected_commit, str) or not COMMIT_PATTERN.fullmatch(
        expected_commit
    ):
        raise ValueError("Release manifest commit must be a full SHA-1.")
    if tag_commit != expected_commit:
        raise ValueError("Release tag target does not match the committed manifest.")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or len(artifacts) != 2:
        raise ValueError("Release manifest must name exactly two artifacts.")
    expected_names = {
        f"projectlore-{version}-py3-none-any.whl",
        f"projectlore-{version}.tar.gz",
    }
    if set(artifacts) != expected_names:
        raise ValueError("Release artifact names do not match the manifest version.")
    actual_names = {path.name for path in dist.iterdir() if path.is_file()}
    if actual_names != expected_names:
        raise ValueError("Downloaded release artifacts do not match the allow-list.")

    for name, expected_hash in artifacts.items():
        if not isinstance(expected_hash, str) or not HASH_PATTERN.fullmatch(
            expected_hash
        ):
            raise ValueError(f"Invalid SHA-256 for {name}.")
        path = dist / name
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"SHA-256 mismatch for {name}.")
        artifact_version = (
            _wheel_version(path) if name.endswith(".whl") else _sdist_version(path)
        )
        if artifact_version != version:
            raise ValueError(f"Embedded version mismatch for {name}.")


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read release manifest: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Release manifest must be a JSON object.")
    return value


def _wheel_version(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError("Wheel must contain exactly one METADATA file.")
        metadata = archive.read(metadata_names[0]).decode("utf-8")
    versions = [
        line.removeprefix("Version: ").strip()
        for line in metadata.splitlines()
        if line.startswith("Version: ")
    ]
    if len(versions) != 1:
        raise ValueError("Wheel METADATA must contain exactly one version.")
    return versions[0]


def _sdist_version(path: Path) -> str:
    with tarfile.open(path, "r:gz") as archive:
        roots = {item.name.split("/", 1)[0] for item in archive.getmembers()}
    if len(roots) != 1:
        raise ValueError("Source archive must contain exactly one root.")
    root = next(iter(roots))
    prefix = "projectlore-"
    if not root.startswith(prefix):
        raise ValueError("Source archive root does not identify ProjectLore.")
    return root.removeprefix(prefix)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--tag-commit", required=True)
    args = parser.parse_args()
    verify_release(
        args.manifest,
        args.dist,
        tag=args.tag,
        tag_commit=args.tag_commit,
    )


if __name__ == "__main__":
    main()
