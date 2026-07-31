"""Bounded blocking PreToolUse hook for ProjectLore policy request files."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from projectlore.loader import discover_model
from projectlore.policy import (
    PolicyRequest,
    load_policy_registry,
    policy_check,
)
from projectlore.service import ModelService
from projectlore.source_policy import (
    facts_from_tool_input,
    load_scope_snapshot,
)

MAX_INPUT_BYTES = 65_536
MAX_REQUEST_BYTES = 16_384
REQUEST_SUFFIX = ".projectlore-policy.json"
_CHECK_COMMAND = re.compile(
    r"^lore check-policy (?P<path>[A-Za-z0-9_./\\-]+\.projectlore-policy\.json)$"
)


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return _block("ProjectLore hook input exceeds 64 KiB.")
    try:
        event = json.loads(raw)
        cwd = Path(_required_string(event, "cwd")).resolve(strict=True)
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0
        candidate = _candidate_request(cwd, tool_input)
        model_path = _model_setting(cwd)
        service = ModelService(model_path)
        if candidate is not None:
            request = PolicyRequest.model_validate_json(candidate)
        else:
            facts = facts_from_tool_input(cwd, tool_input)
            if facts is None:
                return 0
            request = PolicyRequest(
                facts=facts,
                scope=load_scope_snapshot(cwd, required=False),
            )
        result = policy_check(
            service,
            request,
            registry=load_policy_registry(cwd),
            scope_obtained_via="provided_snapshot",
        )
    except (json.JSONDecodeError, OSError, ValueError) as error:
        return _block(f"ProjectLore policy input rejected: {error}")
    finally:
        _sanitize_environment()

    if result["decision"] in {"fail", "indeterminate"}:
        outcomes = ", ".join(
            f"{item['rule_id']}={item['outcome']}" for item in result["findings"]
        )
        source_ids = ", ".join(
            item["id"]
            for item in result["provenance"]
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        )
        provenance = f"; provenance={source_ids}" if source_ids else ""
        return _block(f"ProjectLore blocked the action: {outcomes}{provenance}")
    return 0


def _candidate_request(cwd: Path, tool_input: dict[str, Any]) -> str | None:
    content = tool_input.get("content")
    file_path = tool_input.get("file_path")
    if (
        isinstance(content, str)
        and isinstance(file_path, str)
        and file_path.endswith(REQUEST_SUFFIX)
    ):
        _confined_path(cwd, file_path)
        return _bounded(content)

    command = tool_input.get("command")
    if not isinstance(command, str):
        return None
    match = _CHECK_COMMAND.fullmatch(command.strip())
    if match:
        request_path = _confined_path(cwd, match.group("path"))
        return _bounded(request_path.read_text(encoding="utf-8"))
    if command.startswith("*** Begin Patch"):
        return _request_from_patch(command)
    return None


def _request_from_patch(patch: str) -> str | None:
    lines = patch.splitlines()
    collecting = False
    added: list[str] = []
    for line in lines:
        if line.startswith("*** Add File: "):
            path = line.removeprefix("*** Add File: ").strip()
            collecting = path.endswith(REQUEST_SUFFIX)
            added = []
            continue
        if collecting and line.startswith("*** "):
            break
        if collecting:
            if not line.startswith("+"):
                return None
            added.append(line[1:])
    return _bounded("\n".join(added)) if added else None


def _confined_path(root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    resolved = (
        (root / candidate).resolve()
        if not candidate.is_absolute()
        else candidate.resolve()
    )
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path escapes project root: {raw_path}")
    return resolved


def _model_setting(cwd: Path) -> Path:
    value = os.environ.get("PROJECTLORE_MODEL")
    if value:
        return _confined_path(cwd, value)
    return discover_model(cwd)


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"Hook field {key!r} is required.")
    return item


def _bounded(value: str) -> str:
    if len(value.encode()) > MAX_REQUEST_BYTES:
        raise ValueError("Policy request exceeds 16 KiB.")
    return value


def _sanitize_environment() -> None:
    for key in tuple(os.environ):
        if key not in {"PROJECTLORE_MODEL", "SYSTEMROOT", "WINDIR"}:
            os.environ.pop(key, None)


def _block(reason: str) -> int:
    print(reason[:1000], file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
