"""Preview-first removal of generated integration and disposable local state."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from projectlore.integration import BEGIN, END
from projectlore.onboarding import TOML_BEGIN, TOML_END

GENERATED_COMMANDS = {"projectlore-hook", "projectlore-scope-hook"}
STATE_PATHS = (
    ".projectlore/workflow-target.json",
    ".projectlore/workflow-context.json",
    ".projectlore/scope-target.json",
    ".projectlore/scope.json",
)


@dataclass(frozen=True)
class RemovalPreview:
    path: Path
    before_digest: str | None
    content: str | None
    delete: bool


def removal_previews(root: Path) -> list[RemovalPreview]:
    resolved = root.resolve(strict=True)
    previews: list[RemovalPreview] = []
    for name in ("AGENTS.md", "CLAUDE.md"):
        previews.append(_text_preview(resolved / name, BEGIN, END))
    previews.append(_json_preview(resolved / ".mcp.json", _remove_mcp))
    for name in (".claude/settings.json", ".codex/settings.json"):
        previews.append(_json_preview(resolved / name, _remove_hooks))
    previews.append(
        _text_preview(resolved / ".codex/config.toml", TOML_BEGIN, TOML_END)
    )
    for name in STATE_PATHS:
        path = _safe_path(resolved, name)
        previews.append(
            RemovalPreview(path, _file_digest(path), None, path.is_file())
        )
    trust = _safe_path(resolved, ".projectlore/trust")
    if trust.is_dir():
        for path in sorted(trust.glob("*.json")):
            if path.is_symlink():
                raise ValueError("Removal path cannot be a symbolic link.")
            previews.append(RemovalPreview(path, _file_digest(path), None, True))
    return previews


def apply_removal(previews: list[RemovalPreview]) -> None:
    for preview in previews:
        if _file_digest(preview.path) != preview.before_digest:
            raise ValueError(f"Removal target drifted: {preview.path}")
    for preview in previews:
        if preview.delete:
            preview.path.unlink(missing_ok=True)
        elif preview.content is not None and _file_digest(preview.path) != _digest(
            preview.content
        ):
            preview.path.write_text(preview.content, encoding="utf-8")


def _text_preview(path: Path, begin: str, end: str) -> RemovalPreview:
    _reject_link(path)
    if not path.is_file():
        return RemovalPreview(path, None, None, False)
    before = path.read_text(encoding="utf-8")
    if begin not in before and end not in before:
        return RemovalPreview(path, _digest(before), before, False)
    if begin not in before or end not in before:
        raise ValueError(f"Incomplete managed block: {path}")
    start = before.index(begin)
    stop = before.index(end, start) + len(end)
    after = (before[:start] + before[stop:]).strip("\n")
    content = f"{after}\n" if after else ""
    return RemovalPreview(path, _digest(before), content, content == "")


def _json_preview(
    path: Path,
    transform: Callable[[dict[str, object]], dict[str, object]],
) -> RemovalPreview:
    _reject_link(path)
    if not path.is_file():
        return RemovalPreview(path, None, None, False)
    before = path.read_text(encoding="utf-8")
    value = json.loads(before)
    if not isinstance(value, dict):
        raise ValueError(f"Integration file must contain an object: {path}")
    after = transform(value)
    content = f"{json.dumps(after, indent=2)}\n"
    return RemovalPreview(path, _digest(before), content, False)


def _remove_mcp(value: dict[str, object]) -> dict[str, object]:
    result = dict(value)
    servers = result.get("mcpServers")
    if isinstance(servers, dict):
        updated = dict(servers)
        entry = updated.get("projectlore")
        if isinstance(entry, dict) and entry.get("command") == "projectlore-mcp":
            updated.pop("projectlore")
        result["mcpServers"] = updated
    return result


def _remove_hooks(value: dict[str, object]) -> dict[str, object]:
    result = dict(value)
    hooks = result.get("hooks")
    if not isinstance(hooks, dict):
        return result
    updated: dict[str, object] = {}
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            updated[event] = entries
            continue
        kept = []
        for entry in entries:
            serialized = json.dumps(entry, sort_keys=True)
            if not any(command in serialized for command in GENERATED_COMMANDS):
                kept.append(entry)
        updated[event] = kept
    result["hooks"] = updated
    return result


def _safe_path(root: Path, name: str) -> Path:
    path = root / name
    _reject_link(path)
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("Removal path escapes project root.")
    return resolved


def _reject_link(path: Path) -> None:
    cursor = Path(path.anchor) if path.is_absolute() else Path()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        cursor /= part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError("Removal path cannot contain symbolic links.")


def _file_digest(path: Path) -> str | None:
    return _digest(path.read_text(encoding="utf-8")) if path.is_file() else None


def _digest(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"
