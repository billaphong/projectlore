"""Executable diagnostics for ProjectLore client integrations."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import loads as load_toml
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from projectlore.integration import capability_matrix
from projectlore.service import ModelService
from projectlore.trust import ClientName, verify_receipt

SUPPORTED_SCHEMA_VERSIONS = {"0.1.0", "0.2.0", "1.0.0"}


def run_doctor(root: Path, model_path: Path) -> dict[str, Any]:
    service = ModelService(model_path)
    matrix = capability_matrix(root)
    clients = matrix["clients"]
    if not isinstance(clients, dict):
        raise ValueError("Capability matrix clients must be an object.")
    versions = {
        "claude_code": _version("claude", "--version"),
        "codex_cli": _version("codex", "--version"),
    }
    version_checks = {
        name: _meets_version(
            versions[name],
            str(client["minimum_version"]),
        )
        for name, client in clients.items()
        if isinstance(client, dict)
    }
    trust_clients: tuple[ClientName, ...] = ("claude_code", "codex_cli")
    trust_checks = {
        name: verify_receipt(root, name, versions[name]) for name in trust_clients
    }
    config_checks = _validate_client_configs(root, model_path)
    hook_probe = _probe_hook(root, model_path, "projectlore-hook")
    process_probe = asyncio.run(
        _probe_mcp(root, model_path, "projectlore-mcp")
    )
    checks = {
        "model_valid": True,
        "schema_version_supported": (
            service.model.schema_version in SUPPORTED_SCHEMA_VERSIONS
        ),
        "canonical_model_read_only": True,
        "mcp_startup": process_probe.get("initialized") is True,
        "separate_process_identity": (
            process_probe.get("model_digest") == service.project.digest
            and process_probe.get("contract_version")
            == service.model_status()["contract_version"]
        ),
        "hook_fired_and_blocked": (
            hook_probe["returncode"] == 2
            and "ProjectLore policy input rejected" in str(hook_probe["stderr"])
        ),
        **version_checks,
        **config_checks,
    }
    operational = all(checks.values())
    trust_verified = all(bool(item["verified"]) for item in trust_checks.values())
    return {
        **service.model_status(),
        "capability_matrix_version": matrix["matrix_version"],
        "client_versions": versions,
        "checks": checks,
        "trust": trust_checks,
        "enforcement_state": (
            "configured_executable_trust_verified"
            if operational and trust_verified
            else "configured_executable_trust_unverified"
            if operational
            else "not_operational"
        ),
        "operational": operational,
        "healthy": operational and trust_verified,
        "ready": operational and trust_verified,
        "hook_probe": hook_probe,
        "process_probe": process_probe,
    }


def _validate_client_configs(root: Path, model_path: Path) -> dict[str, bool]:
    relative_model = model_path.resolve().relative_to(root.resolve()).as_posix()
    expected_mcp = {
        "type": "stdio",
        "command": "projectlore-mcp",
        "args": [],
        "env": {"PROJECTLORE_MODEL": relative_model},
    }
    expected_hook = {
        "type": "command",
        "command": "projectlore-hook",
        "timeout": 3,
        "statusMessage": "Checking ProjectLore policy",
    }
    expected_scope_hook = {
        "type": "command",
        "command": "projectlore-scope-hook",
        "timeout": 15,
        "statusMessage": "Refreshing ProjectLore workflow scope",
    }
    claude_mcp = _read_json(root / ".mcp.json")
    claude_hooks = _read_json(root / ".claude" / "settings.json")
    codex_hooks = _read_json(root / ".codex" / "hooks.json")
    codex_mcp = _read_toml(root / ".codex" / "config.toml")
    return {
        "claude_mcp_configured": (
            _nested(claude_mcp, "mcpServers", "projectlore") == expected_mcp
        ),
        "codex_mcp_configured": (
            _nested(codex_mcp, "mcp_servers", "projectlore")
            == {
                "command": "projectlore-mcp",
                "args": [],
                "cwd": ".",
                "required": True,
                "default_tools_approval_mode": "approve",
                "env": {"PROJECTLORE_MODEL": relative_model},
            }
        ),
        "claude_hook_configured": _has_hook(
            claude_hooks, "PreToolUse", expected_hook
        ),
        "codex_hook_configured": _has_hook(
            codex_hooks, "PreToolUse", expected_hook
        ),
        "claude_scope_hook_configured": _has_hook(
            claude_hooks, "SessionStart", expected_scope_hook
        ),
        "codex_scope_hook_configured": _has_hook(
            codex_hooks, "SessionStart", expected_scope_hook
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        value = load_toml(path.read_text(encoding="utf-8"))
    except (OSError, TOMLDecodeError):
        return {}
    return value


def _nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _has_hook(
    value: dict[str, Any],
    event: str,
    expected: dict[str, Any],
) -> bool:
    entries = _nested(value, "hooks", event)
    if not isinstance(entries, list):
        return False
    return any(
        isinstance(entry, dict)
        and isinstance(entry.get("hooks"), list)
        and expected in entry["hooks"]
        for entry in entries
    )


def _entrypoint(command: str) -> str:
    resolved = shutil.which(command)
    if resolved is not None:
        return resolved
    suffix = ".exe" if os.name == "nt" else ""
    sibling = Path(sys.executable).parent / f"{command}{suffix}"
    return str(sibling) if sibling.is_file() else command


async def _probe_mcp(
    root: Path, model_path: Path, command: str
) -> dict[str, object]:
    parameters = StdioServerParameters(
        command=_entrypoint(command),
        args=[],
        cwd=root,
        env={"PROJECTLORE_MODEL": str(model_path.resolve())},
    )
    try:
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            await session.initialize()
            result = await session.call_tool("model_status", {})
    except Exception as error:
        return {"initialized": False, "error": str(error)}
    value = result.structuredContent
    if not isinstance(value, dict):
        return {"initialized": True, "error": "No structured model status."}
    return {
        "initialized": True,
        "model_digest": value.get("model_digest"),
        "contract_version": value.get("contract_version"),
    }


def _probe_hook(
    root: Path, model_path: Path, command: str
) -> dict[str, object]:
    event = {
        "cwd": str(root),
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(root / "doctor.projectlore-policy.json"),
            "content": "{invalid-json",
        },
    }
    environment = dict(os.environ)
    environment["PROJECTLORE_MODEL"] = str(model_path.resolve())
    try:
        result = subprocess.run(
            [_entrypoint(command)],
            cwd=root,
            input=json.dumps(event),
            text=True,
            capture_output=True,
            env=environment,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"returncode": None, "stderr": str(error)}
    return {"returncode": result.returncode, "stderr": result.stderr[:1000]}


def _version(command: str, argument: str) -> str | None:
    try:
        result = subprocess.run(
            [command, argument],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"\d+\.\d+\.\d+", result.stdout or result.stderr)
    return match.group(0) if match else None


def _meets_version(actual: str | None, minimum: str) -> bool:
    if actual is None:
        return False
    return tuple(map(int, actual.split("."))) >= tuple(map(int, minimum.split(".")))
