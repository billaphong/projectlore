from importlib.metadata import version
from pathlib import Path

import projectlore


def test_runtime_version_matches_distribution_metadata() -> None:
    assert projectlore.__version__ == version("projectlore")


def test_unpublished_candidate_guidance_uses_a_local_artifact() -> None:
    root = Path(__file__).parents[1]
    release_policy = (root / "docs" / "release-policy.md").read_text(
        encoding="utf-8"
    )
    assert (
        "`0.1.0a4` is a prepared release candidate, not an authorized "
        "package-index\npublication"
    ) in release_policy

    impossible_command = "python -m pip install projectlore==0.1.0a4"
    for relative_path in ("README.md", "docs/getting-started.md"):
        guidance = (root / relative_path).read_text(encoding="utf-8")
        assert "projectlore-0.1.0a4-py3-none-any.whl" in guidance
        assert guidance.count(impossible_command) == 1
        assert "only after" in guidance[guidance.index(impossible_command) :]
