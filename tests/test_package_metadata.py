from importlib.metadata import version

import projectlore


def test_runtime_version_matches_distribution_metadata() -> None:
    assert projectlore.__version__ == version("projectlore")
