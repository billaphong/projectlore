from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.verify_release import verify_release


def _artifacts(root: Path, version: str) -> tuple[Path, Path]:
    root.mkdir()
    wheel = root / f"projectlore-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"projectlore-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: projectlore\nVersion: {version}\n",
        )
    sdist = root / f"projectlore-{version}.tar.gz"
    payload = b"source"
    info = tarfile.TarInfo(f"projectlore-{version}/README.md")
    info.size = len(payload)
    with tarfile.open(sdist, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(payload))
    return wheel, sdist


def _manifest(
    path: Path,
    *,
    tag: str,
    commit: str,
    wheel: Path,
    sdist: Path,
) -> None:
    path.write_text(
        json.dumps(
            {
                "tag": tag,
                "version": tag.removeprefix("v"),
                "commit": commit,
                "artifacts": {
                    wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    sdist.name: hashlib.sha256(sdist.read_bytes()).hexdigest(),
                },
            }
        ),
        encoding="utf-8",
    )


def test_release_manifest_binds_tag_commit_version_names_and_hashes(
    tmp_path: Path,
) -> None:
    commit = "a" * 40
    tag = "v0.1.0a2"
    wheel, sdist = _artifacts(tmp_path / "dist", "0.1.0a2")
    manifest = tmp_path / "manifest.json"
    _manifest(
        manifest,
        tag=tag,
        commit=commit,
        wheel=wheel,
        sdist=sdist,
    )

    verify_release(manifest, wheel.parent, tag=tag, tag_commit=commit)

    wheel.write_bytes(wheel.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_release(manifest, wheel.parent, tag=tag, tag_commit=commit)


def test_release_manifest_rejects_unbound_tag_or_commit(tmp_path: Path) -> None:
    commit = "b" * 40
    wheel, sdist = _artifacts(tmp_path / "dist", "0.1.0a2")
    manifest = tmp_path / "manifest.json"
    _manifest(
        manifest,
        tag="v0.1.0a2",
        commit=commit,
        wheel=wheel,
        sdist=sdist,
    )

    with pytest.raises(ValueError, match="tag does not match"):
        verify_release(
            manifest,
            wheel.parent,
            tag="v0.1.0a3",
            tag_commit=commit,
        )
    with pytest.raises(ValueError, match="tag target"):
        verify_release(
            manifest,
            wheel.parent,
            tag="v0.1.0a2",
            tag_commit="c" * 40,
        )


def test_publication_workflows_never_skip_release_verification() -> None:
    root = Path(__file__).parents[1]
    for name in ("publish-pypi.yml", "publish-testpypi.yml"):
        workflow = (root / ".github" / "workflows" / name).read_text(
            encoding="utf-8"
        )
        assert "scripts/verify_release.py" in workflow
        assert "if: inputs.tag" not in workflow
        assert 'test -f ".github/releases/${RELEASE_TAG}.json"' in workflow
