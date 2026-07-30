"""Bounded vendor-neutral contracts for supported agent lifecycle events."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import Field, field_validator

from projectlore.models import StrictModel

AGENT_EVENT_VERSION: Literal["projectlore-agent-event/0.1.0"] = (
    "projectlore-agent-event/0.1.0"
)
ClientName = Literal["claude_code", "codex_cli"]
EventName = Literal[
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
]
MAX_EVENT_BYTES = 65_536
MAX_FIELD_BYTES = 16_384
_SUPPORTED_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
}


class UnsupportedEventError(ValueError):
    pass


class ProjectLoreAgentEvent(StrictModel):
    event_version: Literal["projectlore-agent-event/0.1.0"]
    event_id: str = Field(pattern=r"^sha256:")
    client: ClientName
    event: EventName
    cwd: str = Field(min_length=1, max_length=2048)
    tool_name: str | None = Field(default=None, max_length=256)
    tool_input: dict[str, Any] = Field(default_factory=dict)
    prompt: str | None = Field(default=None, max_length=16_384)
    session_id: str | None = Field(default=None, max_length=256)
    agent_id: str | None = Field(default=None, max_length=256)
    is_subagent: bool = False

    @field_validator("tool_input")
    @classmethod
    def tool_input_is_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(_encoded(value)) > MAX_FIELD_BYTES:
            raise ValueError("Hook tool_input exceeds 16 KiB.")
        return value


def normalize_hook_event(
    value: dict[str, Any],
    *,
    client: ClientName,
    event_name: str | None = None,
) -> ProjectLoreAgentEvent:
    if len(_encoded(value)) > MAX_EVENT_BYTES:
        raise ValueError("Hook event exceeds 64 KiB.")
    native_event = event_name or value.get("hook_event_name") or "PreToolUse"
    if native_event not in _SUPPORTED_EVENTS:
        raise UnsupportedEventError(f"Unsupported hook event: {native_event}")
    cwd = _required_string(value, "cwd")
    tool_input = value.get("tool_input", {})
    if not isinstance(tool_input, dict):
        raise ValueError("Hook field 'tool_input' must be an object.")
    tool_name = value.get("tool_name")
    prompt = value.get("prompt")
    session_id = value.get("session_id")
    agent_id = value.get("agent_id")
    for name, item in (
        ("tool_name", tool_name),
        ("prompt", prompt),
        ("session_id", session_id),
        ("agent_id", agent_id),
    ):
        if item is not None and not isinstance(item, str):
            raise ValueError(f"Hook field {name!r} must be a string.")
    normalized = {
        "event_version": AGENT_EVENT_VERSION,
        "client": client,
        "event": native_event,
        "cwd": cwd,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "prompt": prompt,
        "session_id": session_id,
        "agent_id": agent_id,
        "is_subagent": bool(value.get("is_subagent", agent_id is not None)),
    }
    return ProjectLoreAgentEvent(
        event_id=f"sha256:{hashlib.sha256(_encoded(normalized)).hexdigest()}",
        **normalized,  # type: ignore[arg-type]
    )


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"Hook field {key!r} is required.")
    return item


def _encoded(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except (TypeError, ValueError) as error:
        raise ValueError("Hook event must contain JSON values only.") from error
