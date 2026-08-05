"""Preview-first initialization of a ProjectLore-enabled repository."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from projectlore.integration import instruction_previews

INIT_VERSION = "projectlore-init-preview/0.1.0"
TOML_BEGIN = "# PROJECTLORE_MANAGED_START"
TOML_END = "# PROJECTLORE_MANAGED_END"


@dataclass(frozen=True)
class FilePreview:
    path: Path
    before_digest: str | None
    after_digest: str
    changed: bool
    content: str
    conflict: str | None = None


def initialization_previews(
    root: Path,
    *,
    project_name: str,
    model_path: Path = Path("projectlore.yaml"),
) -> list[FilePreview]:
    """Return every proposed initialization file without writing."""
    resolved_root = root.resolve()
    relative_model = _relative_model_path(model_path)
    model = resolved_root / relative_model
    previews = [
        _new_file_preview(model, _starter_model(project_name)),
        _json_preview(
            resolved_root / ".mcp.json",
            lambda value: _merge_mcp(value, relative_model.as_posix()),
        ),
        _json_preview(
            resolved_root / ".claude" / "settings.json",
            lambda value: _merge_hooks(value, client="claude_code"),
        ),
        _toml_preview(
            resolved_root / ".codex" / "config.toml",
            _codex_mcp_block(relative_model.as_posix()),
        ),
        _json_preview(
            resolved_root / ".codex" / "hooks.json",
            lambda value: _merge_hooks(value, client="codex_cli"),
        ),
    ]
    previews.extend(
        FilePreview(
            path=item.path,
            before_digest=item.before_digest,
            after_digest=item.after_digest,
            changed=item.changed,
            content=item.content,
        )
        for item in instruction_previews(resolved_root)
    )
    return previews


def apply_initialization(previews: list[FilePreview]) -> None:
    """Apply an explicitly reviewed preview if no file changed or conflicts."""
    conflicts = [item for item in previews if item.conflict is not None]
    if conflicts:
        details = "; ".join(f"{item.path}: {item.conflict}" for item in conflicts)
        raise ValueError(f"Initialization conflicts must be resolved: {details}")
    for preview in previews:
        current = (
            preview.path.read_text(encoding="utf-8") if preview.path.is_file() else None
        )
        if _digest(current) != preview.before_digest:
            raise ValueError(f"Initialization drift detected: {preview.path}")
    changed = [item for item in previews if item.changed]
    if not changed:
        return
    roots = [
        item.path.parent for item in previews if item.path.name == "projectlore.yaml"
    ]
    root = (
        roots[0]
        if roots
        else Path(os.path.commonpath([item.path for item in previews]))
    )
    journal = root / ".projectlore" / "integration-journal.json"
    payload = {
        "contract_version": "projectlore-integration-journal/0.6.1",
        "entries": [
            {
                "path": item.path.relative_to(root).as_posix(),
                "before_digest": item.before_digest,
                "after_digest": item.after_digest,
                "content": item.content,
            }
            for item in changed
        ],
    }
    _atomic_text(journal, f"{json.dumps(payload, separators=(',', ':'))}\n")
    resume_initialization(root)


def resume_initialization(root: Path) -> None:
    """Idempotently finish a digest-bound interrupted integration write set."""

    resolved = root.resolve(strict=True)
    journal = resolved / ".projectlore" / "integration-journal.json"
    if not journal.is_file() or journal.is_symlink():
        return
    payload = json.loads(journal.read_text(encoding="utf-8"))
    if payload.get("contract_version") != "projectlore-integration-journal/0.6.1":
        raise ValueError("Unknown ProjectLore integration journal version.")
    for entry in payload["entries"]:
        path = resolved.joinpath(*Path(entry["path"]).parts)
        if not path.resolve(strict=False).is_relative_to(resolved) or path.is_symlink():
            raise ValueError("Integration journal path escapes repository.")
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        digest = _digest(current)
        if digest == entry["after_digest"]:
            continue
        if digest != entry["before_digest"]:
            raise ValueError(f"Integration journal drift detected: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_text(path, entry["content"])
    journal.unlink()


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _relative_model_path(path: Path) -> Path:
    if path.is_absolute() or ".." in path.parts or path.name == "":
        raise ValueError("Model path must be a repository-relative file path.")
    if path.as_posix() not in {
        "projectlore.yaml",
        ".projectlore/model.yaml",
    }:
        raise ValueError(
            "Model path must be projectlore.yaml or .projectlore/model.yaml."
        )
    return path


def _new_file_preview(path: Path, content: str) -> FilePreview:
    before = path.read_text(encoding="utf-8") if path.is_file() else None
    conflict = None
    if before is not None and before != content:
        conflict = "canonical model already exists with different content"
    return FilePreview(
        path=path,
        before_digest=_digest(before),
        after_digest=_digest(content) or "",
        changed=before != content,
        content=content,
        conflict=conflict,
    )


def _json_preview(path: Path, merge: Any) -> FilePreview:
    before = path.read_text(encoding="utf-8") if path.is_file() else None
    conflict = None
    try:
        value = json.loads(before) if before is not None else {}
        if not isinstance(value, dict):
            raise ValueError("top level must be an object")
        merged = merge(value)
        content = f"{json.dumps(merged, indent=2)}\n"
    except (json.JSONDecodeError, ValueError) as error:
        content = before or ""
        conflict = f"cannot safely merge JSON: {error}"
    return FilePreview(
        path=path,
        before_digest=_digest(before),
        after_digest=_digest(content) or "",
        changed=before != content,
        content=content,
        conflict=conflict,
    )


def _toml_preview(path: Path, block: str) -> FilePreview:
    before = path.read_text(encoding="utf-8") if path.is_file() else None
    base = before or ""
    conflict = None
    if TOML_BEGIN in base or TOML_END in base:
        if TOML_BEGIN not in base or TOML_END not in base:
            content = base
            conflict = "incomplete ProjectLore managed TOML block"
        else:
            start = base.index(TOML_BEGIN)
            end = base.index(TOML_END, start) + len(TOML_END)
            content = f"{base[:start]}{block}{base[end:]}"
    elif re.search(r"(?m)^\[mcp_servers\.projectlore(?:\.env)?\]\s*$", base):
        content = base
        conflict = "unmanaged mcp_servers.projectlore table already exists"
    else:
        separator = "" if not base or base.endswith("\n\n") else "\n"
        content = f"{base}{separator}{block}\n"
    return FilePreview(
        path=path,
        before_digest=_digest(before),
        after_digest=_digest(content) or "",
        changed=before != content,
        content=content,
        conflict=conflict,
    )


def _merge_mcp(value: dict[str, Any], model_path: str) -> dict[str, Any]:
    result = dict(value)
    servers = result.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcpServers must be an object")
    servers = dict(servers)
    existing = servers.get("projectlore")
    desired = {
        "type": "stdio",
        "command": "projectlore-mcp",
        "args": [],
        "env": {"PROJECTLORE_MODEL": model_path},
    }
    if existing is not None and existing != desired:
        raise ValueError("mcpServers.projectlore already has unmanaged content")
    servers["projectlore"] = desired
    acquisition_desired = {
        "type": "stdio",
        "command": "projectlore-acquisition-mcp",
        "args": [],
        "env": {"PROJECTLORE_ROOT": "."},
    }
    acquisition_existing = servers.get("projectlore-acquisition")
    if acquisition_existing is not None and acquisition_existing != acquisition_desired:
        raise ValueError(
            "mcpServers.projectlore-acquisition already has unmanaged content"
        )
    servers["projectlore-acquisition"] = acquisition_desired
    result["mcpServers"] = servers
    return result


def _merge_hooks(value: dict[str, Any], *, client: str) -> dict[str, Any]:
    result = dict(value)
    hooks = result.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks must be an object")
    hooks = dict(hooks)
    entries = hooks.get("PreToolUse", [])
    if not isinstance(entries, list):
        raise ValueError("hooks.PreToolUse must be an array")
    # A fresh Python policy process takes about one second on supported Windows
    # clients before concurrent load. Ten seconds remains fail-bounded while
    # avoiding false hook failures from ordinary cold-start variance.
    command = {
        "type": "command",
        "command": "projectlore-hook",
        "timeout": 10,
        "statusMessage": "Checking ProjectLore policy",
    }
    matcher = (
        "Bash|Write|Edit"
        if client == "claude_code"
        else ("Bash|apply_patch|Edit|Write")
    )
    desired = {"matcher": matcher, "hooks": [command]}
    legacy_command = {**command, "timeout": 3}
    legacy_desired = {"matcher": matcher, "hooks": [legacy_command]}
    entries = [item for item in entries if item != legacy_desired]
    if desired not in entries:
        entries = [*entries, desired]
    hooks["PreToolUse"] = entries
    session_entries = hooks.get("SessionStart", [])
    if not isinstance(session_entries, list):
        raise ValueError("hooks.SessionStart must be an array")
    scope_command = {
        "type": "command",
        "command": "projectlore-scope-hook",
        "timeout": 15,
        "statusMessage": "Refreshing ProjectLore workflow scope",
    }
    session_acquisition_command = {
        "type": "command",
        "command": f"projectlore-acquisition-hook --client {client} --root .",
        "timeout": 2,
        "statusMessage": "Refreshing ProjectLore knowledge evidence",
    }
    scope_desired = {"hooks": [scope_command, session_acquisition_command]}
    # Upgrade the exact legacy entry instead of leaving two SessionStart jobs.
    legacy_scope = {"hooks": [scope_command]}
    legacy_session_acquisition = {**session_acquisition_command, "timeout": 3}
    legacy_scope_with_acquisition = {
        "hooks": [scope_command, legacy_session_acquisition]
    }
    session_entries = [
        item
        for item in session_entries
        if item not in (legacy_scope, legacy_scope_with_acquisition)
    ]
    if scope_desired not in session_entries:
        session_entries = [*session_entries, scope_desired]
    hooks["SessionStart"] = session_entries
    stop_entries = hooks.get("Stop", [])
    if not isinstance(stop_entries, list):
        raise ValueError("hooks.Stop must be an array")
    stop_desired = {"hooks": [session_acquisition_command]}
    legacy_stops = (
        {"hooks": [{**session_acquisition_command, "timeout": 3}]},
        {"hooks": [{**session_acquisition_command, "timeout": 10}]},
    )
    stop_entries = [item for item in stop_entries if item not in legacy_stops]
    if stop_desired not in stop_entries:
        stop_entries = [*stop_entries, stop_desired]
    hooks["Stop"] = stop_entries
    result["hooks"] = hooks
    return result


def _codex_mcp_block(model_path: str) -> str:
    return f"""{TOML_BEGIN}
[mcp_servers.projectlore]
command = "projectlore-mcp"
args = []
cwd = "."
required = true
default_tools_approval_mode = "approve"

[mcp_servers.projectlore.env]
PROJECTLORE_MODEL = "{model_path}"

[mcp_servers.projectlore-acquisition]
command = "projectlore-acquisition-mcp"
args = []
cwd = "."
required = false
default_tools_approval_mode = "approve"

[mcp_servers.projectlore-acquisition.env]
PROJECTLORE_ROOT = "."
{TOML_END}"""


def _starter_model(project_name: str) -> str:
    clean_name = project_name.strip()
    if not clean_name or len(clean_name) > 512:
        raise ValueError("Project name must contain 1 to 512 characters.")
    slug = re.sub(r"[^a-z0-9]+", "-", clean_name.casefold()).strip("-")
    if not slug:
        raise ValueError("Project name must contain a letter or number.")
    quoted_name = json.dumps(clean_name)
    return f"""schema_version: 0.2.0
model_version: 0.1.0
id: lore:{slug}
name: {quoted_name}
description: Shared project knowledge for {quoted_name}.
domains:
  - id: lore:{slug}/domain/project
    name: Project
    description: The initial project domain; replace this with accepted meaning.
    source_refs: [lore:{slug}/source/agents]
    authority:
      kind: project
      reference: file:AGENTS.md
    trust: authoritative
concepts:
  - id: lore:{slug}/concept/project
    name: {quoted_name}
    description: The project represented by this knowledge model.
    domain_ref: lore:{slug}/domain/project
    rule_refs: [lore:{slug}/rule/review-knowledge-changes]
    source_refs: [lore:{slug}/source/agents]
    authority:
      kind: project
      reference: file:AGENTS.md
    trust: authoritative
relationships: []
rules:
  - id: lore:{slug}/rule/review-knowledge-changes
    statement: Changes to canonical project knowledge require normal Git review.
    kind: obligation
    severity: warning
    source_refs: [lore:{slug}/source/agents]
    rationale: ProjectLore reads never silently mutate accepted project meaning.
    authority:
      kind: project
      reference: file:AGENTS.md
    trust: authoritative
sources:
  - id: lore:{slug}/source/agents
    kind: specification
    uri: file:AGENTS.md
    title: Repository agent instructions
    authority:
      kind: project
      reference: file:AGENTS.md
    trust: authoritative
"""


def _digest(value: str | None) -> str | None:
    if value is None:
        return None
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"
