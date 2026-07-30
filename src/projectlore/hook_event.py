"""Vendor-neutral boundary contract for supported agent hook events."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from projectlore.models import StrictModel

HOOK_EVENT_VERSION: Literal["projectlore-hook-event/0.1.0"] = (
    "projectlore-hook-event/0.1.0"
)
ClientName = Literal["claude_code", "codex_cli"]


class NormalizedHookEvent(StrictModel):
    event_version: Literal["projectlore-hook-event/0.1.0"]
    client: ClientName
    event: Literal["PreToolUse"]
    cwd: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_input: dict[str, Any]


def normalize_hook_event(
    value: dict[str, Any],
    *,
    client: ClientName,
) -> NormalizedHookEvent:
    tool_name = value.get("tool_name")
    tool_input = value.get("tool_input")
    cwd = value.get("cwd")
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("Hook field 'tool_name' is required.")
    if not isinstance(tool_input, dict):
        raise ValueError("Hook field 'tool_input' is required.")
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("Hook field 'cwd' is required.")
    return NormalizedHookEvent(
        event_version=HOOK_EVENT_VERSION,
        client=client,
        event="PreToolUse",
        cwd=cwd,
        tool_name=tool_name,
        tool_input=tool_input,
    )
