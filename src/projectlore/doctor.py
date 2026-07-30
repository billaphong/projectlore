"""Executable diagnostics for ProjectLore client integrations."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from projectlore.integration import capability_matrix
from projectlore.mcp_server import create_server
from projectlore.scope import ScopeSnapshot
from projectlore.service import ModelService
from projectlore.trust import ClientName, verify_receipt


class _ScopeAuthority:
    async def current_scope(self, frame_id: str, space_id: str) -> ScopeSnapshot:
        return ScopeSnapshot(
            authority="fraimed",
            frame_id=frame_id,
            frame_title="ProjectLore doctor",
            frame_status="in_progress",
            validation_open=0,
            observed_at=datetime.now(UTC),
            authority_ref=f"fraimed://frame/{frame_id}",
        )


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
    status_result = asyncio.run(
        create_server(model_path, _ScopeAuthority()).call_tool("model_status", {})
    )
    if not isinstance(status_result, tuple):
        raise RuntimeError("MCP model_status did not return structured output.")
    mcp_status = status_result[1]
    config_checks = {
        "claude_mcp_configured": _contains(root / ".mcp.json", "projectlore"),
        "codex_mcp_configured": _contains(
            root / ".codex" / "config.toml", "mcp_servers.projectlore"
        ),
        "claude_hook_configured": _contains(
            root / ".claude" / "settings.json", "PreToolUse"
        ),
        "codex_hook_configured": _contains(
            root / ".codex" / "hooks.json", "PreToolUse"
        ),
    }
    hook_probe = _probe_hook(root, model_path)
    process_probe = _probe_process_identity(root, model_path)
    checks = {
        "model_valid": True,
        "schema_version_supported": (
            service.model.schema_version in SUPPORTED_SCHEMA_VERSIONS
        ),
        "canonical_model_read_only": True,
        "mcp_startup": mcp_status["model_digest"] == service.project.digest,
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
    return {
        **service.model_status(),
        "capability_matrix_version": matrix["matrix_version"],
        "client_versions": versions,
        "checks": checks,
        "trust": trust_checks,
        "enforcement_state": (
            "configured_executable_trust_verified"
            if all(bool(item["verified"]) for item in trust_checks.values())
            else "configured_executable_trust_unverified"
        ),
        "hook_probe": hook_probe,
        "process_probe": process_probe,
        "healthy": all(checks.values()),
    }


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


def _contains(path: Path, value: str) -> bool:
    try:
        return value in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _probe_hook(root: Path, model_path: Path) -> dict[str, object]:
    event = {
        "cwd": str(root),
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(root / "doctor.projectlore-policy.json"),
            "content": "{invalid-json",
        },
    }
    environment = {
        "PROJECTLORE_MODEL": str(model_path.resolve()),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
    }
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-m", "projectlore.hook"],
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


def _probe_process_identity(root: Path, model_path: Path) -> dict[str, object]:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "projectlore.cli",
                "status",
                str(model_path.resolve()),
                "--json",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        value = json.loads(result.stdout)
    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as error:
        return {"error": str(error)}
    if not isinstance(value, dict):
        return {"error": "Subprocess status was not an object."}
    return {
        "model_digest": value.get("model_digest"),
        "contract_version": value.get("contract_version"),
    }
