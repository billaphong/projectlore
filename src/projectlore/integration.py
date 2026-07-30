"""Preview-first compilation of project-local agent integration files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

BEGIN = "<!-- PROJECTLORE_MANAGED_START"
END = "<!-- PROJECTLORE_MANAGED_END -->"
MANAGED_VERSION = "projectlore-managed-instructions/0.1.0"


@dataclass(frozen=True)
class ManagedPreview:
    path: Path
    before_digest: str | None
    after_digest: str
    changed: bool
    content: str


def instruction_previews(root: Path) -> list[ManagedPreview]:
    """Return proposed AGENTS.md and CLAUDE.md contents without writing."""
    return [
        _preview(root / "AGENTS.md", _codex_body()),
        _preview(root / "CLAUDE.md", _claude_body()),
    ]


def apply_instruction_previews(previews: list[ManagedPreview]) -> None:
    """Apply an explicitly reviewed preview, rejecting intervening drift."""
    for preview in previews:
        current = (
            preview.path.read_text(encoding="utf-8") if preview.path.is_file() else None
        )
        if _digest(current) != preview.before_digest:
            raise ValueError(f"Managed instruction drift detected: {preview.path}")
    for preview in previews:
        if preview.changed:
            preview.path.write_text(preview.content, encoding="utf-8")


def capability_matrix(root: Path) -> dict[str, object]:
    path = root / "docs" / "client-capabilities.json"
    if not path.is_file():
        path = Path(__file__).with_name("client-capabilities.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Client capability matrix must be an object.")
    return value


def _preview(path: Path, body: str) -> ManagedPreview:
    before = path.read_text(encoding="utf-8") if path.is_file() else None
    managed_digest = _digest(body)
    block = f"{BEGIN} digest={managed_digest} -->\n{body}\n{END}"
    if before is None:
        after = f"{block}\n"
    elif BEGIN in before:
        start = before.index(BEGIN)
        end = before.index(END, start) + len(END)
        after = f"{before[:start]}{block}{before[end:]}"
    else:
        separator = "" if before.endswith("\n\n") else "\n"
        after = f"{before}{separator}\n{block}\n"
    return ManagedPreview(
        path=path,
        before_digest=_digest(before),
        after_digest=_digest(after) or "",
        changed=before != after,
        content=after,
    )


def _codex_body() -> str:
    return """## ProjectLore agent context

This repository's Git-tracked ProjectLore model is canonical project knowledge.
Use the project-scoped `projectlore` MCP tools for meaning, terminology,
relationships, provenance, and policy checks. A closer nested `AGENTS.md` or
`AGENTS.override.md` takes precedence for its subtree. MCP reads never mutate
canonical model files; proposed model changes require normal review."""


def _claude_body() -> str:
    return """## ProjectLore agent context

This repository's Git-tracked ProjectLore model is canonical project knowledge.
Use the project-scoped `projectlore` MCP tools for meaning, terminology,
relationships, provenance, and policy checks. Nested `CLAUDE.md` instructions
apply when Claude accesses their subtree. MCP reads never mutate canonical
model files; proposed model changes require normal review."""


def _digest(value: str | None) -> str | None:
    if value is None:
        return None
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"
