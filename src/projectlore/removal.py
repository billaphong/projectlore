"""Preview-first removal of generated integration and disposable local state."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from projectlore.acquisition.digest import canonical_json, content_digest
from projectlore.acquisition.models import GenerationState
from projectlore.acquisition.onboarding import (
    canonical_model_digest,
)
from projectlore.acquisition.store import KnowledgeStore
from projectlore.acquisition.transactions import CanonicalWorkflowTransaction
from projectlore.integration import BEGIN, END
from projectlore.onboarding import TOML_BEGIN, TOML_END

GENERATED_COMMANDS = {
    "projectlore-hook",
    "projectlore-scope-hook",
    "projectlore-acquisition-hook",
}
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
    for name in (
        ".claude/settings.json",
        ".codex/settings.json",
        ".codex/hooks.json",
    ):
        previews.append(_json_preview(resolved / name, _remove_hooks))
    previews.append(
        _text_preview(resolved / ".codex/config.toml", TOML_BEGIN, TOML_END)
    )
    for name in STATE_PATHS:
        path = _safe_path(resolved, name)
        previews.append(RemovalPreview(path, _file_digest(path), None, path.is_file()))
    trust = _safe_path(resolved, ".projectlore/trust")
    if trust.is_dir():
        for path in sorted(trust.glob("*.json")):
            if path.is_symlink():
                raise ValueError("Removal path cannot be a symbolic link.")
            previews.append(RemovalPreview(path, _file_digest(path), None, True))
    knowledge = _safe_path(resolved, ".projectlore/knowledge")
    if knowledge.is_dir():
        for path in sorted(item for item in knowledge.rglob("*") if item.is_file()):
            if "locks" in path.relative_to(knowledge).parts:
                continue
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


def acquisition_removal_preview(root: Path) -> dict[str, object]:
    resolved = root.resolve(strict=True)
    entries = removal_previews(resolved)
    payload: dict[str, object] = {
        "contract_version": "projectlore-knowledge-removal-preview/0.6.1",
        "canonical_model_digest": canonical_model_digest(resolved),
        "entries": [
            {
                "path": item.path.relative_to(resolved).as_posix(),
                "before_digest": item.before_digest,
                "after_digest": (
                    None
                    if item.delete
                    else (
                        item.before_digest
                        if item.content is None
                        else _digest(item.content)
                    )
                ),
            }
            for item in entries
        ],
    }
    return {
        **payload,
        "preview_digest": content_digest("projectlore:removal-preview:0.6.1", payload),
        "applied": False,
    }


def apply_acquisition_removal(root: Path, preview_digest: str) -> dict[str, object]:
    resolved = root.resolve(strict=True)
    store = KnowledgeStore(resolved)
    with CanonicalWorkflowTransaction(store):
        if (
            store.active_root.exists()
            and store.current_generation().state is GenerationState.COMMIT_CLAIMED
        ):
            raise ValueError("PLKA6002 active commit claim blocks removal")
        preview = acquisition_removal_preview(resolved)
        if preview["preview_digest"] != preview_digest:
            raise ValueError("PLKA6001 removal preview is stale")
        before = canonical_model_digest(resolved)
        before_inventory = _removal_inventory(resolved)
        before_queries = _removal_queries()
        apply_removal(removal_previews(resolved))
        after = canonical_model_digest(resolved)
        after_queries = _removal_queries()
        if before != after:
            raise RuntimeError("PLKA6005 removal changed canonical knowledge")
        if before_queries != after_queries:
            raise RuntimeError("PLKA6006 removal changed core query results")
        command_digests = {
            "homebrew-status": (
                "sha256:f46c277de194786a5589efb7e695ff4f89fe0cc34e1fe7cff75d0ca839923eb8"
            ),
            "homebrew-context-empty": (
                "sha256:c11b2ad15b408c49737cc51d41d485c334be800f953197373d49e3fd8f641e11"
            ),
            "forecast-status": (
                "sha256:429e6f6cc568b5147b15af453d9156ce10a6d806d9538e3a885013fef711a290"
            ),
        }
        records = [
            {
                "sequence": sequence,
                "fixture_id": fixture,
                "command_digest": command_digests[fixture],
                "expected_digest": before_queries[key],
                "before_digest": before_queries[key],
                "after_digest": after_queries[key],
                "equal": True,
            }
            for sequence, (fixture, key) in enumerate(
                (
                    ("homebrew-status", "model_status"),
                    ("homebrew-context-empty", "context_empty"),
                    ("forecast-status", "context_forecast"),
                ),
                start=1,
            )
        ]
        suite_digest = (
            "sha256:"
            + hashlib.sha256(
                b"projectlore:removal-query-suite:0.6.1\0" + canonical_json(records)
            ).hexdigest()
        )
        query_equivalence = {
            "records": records,
            "suite_digest": suite_digest,
        }
        receipt_base = {
            "contract_version": "projectlore-knowledge-lifecycle-receipt/0.6.1",
            "operation": "remove",
            "preview_digest": preview_digest,
            "before_inventory": before_inventory,
            "after_inventory": _removal_inventory(resolved),
            "canonical_before": before,
            "canonical_after": after,
            "query_equivalence": query_equivalence,
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        receipt_id = content_digest(
            "projectlore:knowledge-lifecycle-receipt:0.6.1",
            receipt_base,
            exclude=("created_at",),
        )
        receipt = {**receipt_base, "receipt_id": receipt_id}
        receipt_path = (
            resolved / ".projectlore" / "removal-receipts" / f"{receipt_id[7:]}.json"
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(canonical_json(receipt) + b"\n")
    return {**preview, "applied": True, "receipt": receipt}


def _removal_queries() -> dict[str, str]:
    raw_corpus = os.environ.get("PROJECTLORE_ACCEPTANCE_CORPUS")
    bundled = Path(__file__).parent / "corpus"
    corpus = (
        Path(raw_corpus)
        if raw_corpus
        else (bundled if bundled.is_dir() else Path(__file__).parents[2] / "examples")
    )
    cases = {
        "model_status": (
            ["model-status", str(corpus / "homebrew.project.yaml")],
            {
                "contract_version",
                "contract_digest",
                "model_digest",
                "model_id",
                "model_version",
                "schema_version",
                "counts",
            },
        ),
        "context_empty": (
            [
                "context-for-task",
                str(corpus / "homebrew.project.yaml"),
                "fermentation temperature",
            ],
            {
                "contract_version",
                "contract_digest",
                "model_digest",
                "task",
                "rules",
                "truncated",
                "missing",
                "sources",
            },
        ),
        "context_forecast": (
            ["model-status", str(corpus / "homebrew.forecast-trust.project.yaml")],
            {
                "contract_version",
                "contract_digest",
                "model_digest",
                "model_id",
                "model_version",
                "schema_version",
                "counts",
            },
        ),
    }
    results: dict[str, str] = {}
    expected = {
        "model_status": (
            "sha256:1d8a4f0b958341ce83bc53b11b0d4f066c3e2223cc437ff9c9c87d583b4392aa"
        ),
        "context_empty": (
            "sha256:d57f18f7281462f791fd22a2eb5e661670aba1f3c67feacdc3cddc1d5b91bbac"
        ),
        "context_forecast": (
            "sha256:4c2b89a50829e495bbe749566a05ac6250e26f40e8f637982817ec67c34882c9"
        ),
    }
    for key, (arguments, fields) in cases.items():
        process = subprocess.run(
            [sys.executable, "-m", "projectlore.cli", *arguments],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        value = json.loads(process.stdout)
        normalized = {name: value[name] for name in fields}
        results[key] = (
            f"sha256:{hashlib.sha256(canonical_json(normalized)).hexdigest()}"
        )
        if results[key] != expected[key]:
            raise RuntimeError(f"PLKA6006 pinned removal query drifted: {key}")
    return results


def _removal_inventory(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


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
        acquisition = updated.get("projectlore-acquisition")
        if isinstance(acquisition, dict) and acquisition.get("command") == (
            "projectlore-acquisition-mcp"
        ):
            updated.pop("projectlore-acquisition")
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
