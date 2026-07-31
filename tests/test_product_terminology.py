from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "docs" / "fraimed-terminology-allowlist.txt"


def test_adapter_name_occurs_only_in_reviewed_paths() -> None:
    allowed = {
        line
        for line in ALLOWLIST.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    candidates = [ROOT / "README.md"]
    candidates.extend((ROOT / "src").rglob("*.py"))
    candidates.extend((ROOT / "docs").rglob("*.md"))
    actual = {
        path.relative_to(ROOT).as_posix()
        for path in candidates
        if "fraimed" in path.read_text(encoding="utf-8").casefold()
    }

    assert actual == allowed
