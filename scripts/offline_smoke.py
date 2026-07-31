"""Prepare a wheelhouse, then prove a fresh installation without index access."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    expected_returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        check=False,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
    )
    if result.returncode != expected_returncode:
        raise RuntimeError(
            f"{argv!r} returned {result.returncode}, expected "
            f"{expected_returncode}.\nstdout:\n{result.stdout}\nstderr:\n"
            f"{result.stderr}"
        )
    return result


async def _mcp_smoke(command: Path, project: Path) -> None:
    model = project / "projectlore.yaml"
    parameters = StdioServerParameters(
        command=str(command),
        args=[],
        cwd=project,
        env={"PROJECTLORE_MODEL": "projectlore.yaml"},
    )
    async with (
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        required = {
            "model_status",
            "model_search",
            "model_get_concept",
            "model_resolve_term",
            "model_get_relationships",
            "model_validate",
            "context_for_task",
            "policy_check",
        }
        if not required <= names:
            raise ValueError(f"Installed MCP tools are incomplete: {names}")
        first = await session.call_tool("model_status", {})
        first_status = first.structuredContent
        if not isinstance(first_status, dict):
            raise ValueError("MCP model_status returned no structured content.")
        first_digest = first_status["model_digest"]

        original = model.read_text(encoding="utf-8")
        valid = original.replace(
            'name: "ProjectLore Acceptance"',
            'name: "ProjectLore Acceptance Updated"',
            1,
        )
        model.write_text(valid, encoding="utf-8")
        refreshed = await session.call_tool("model_status", {})
        refreshed_status = refreshed.structuredContent
        if (
            not isinstance(refreshed_status, dict)
            or refreshed_status["model_digest"] == first_digest
            or refreshed_status["freshness"]["refresh_state"] != "current"
        ):
            raise ValueError("Valid MCP refresh did not activate atomically.")

        model.write_text(f"{valid}unknown_root_field: true\n", encoding="utf-8")
        invalid = await session.call_tool("model_validate", {})
        invalid_status = invalid.structuredContent
        if (
            not isinstance(invalid_status, dict)
            or invalid_status["freshness"]["refresh_state"] != "last_valid"
            or invalid_status["valid"] is not False
        ):
            raise ValueError("Malformed edit did not preserve last-known-good.")
        model.write_text(valid, encoding="utf-8")


def verify(dist: Path, example: Path, schema: Path) -> None:
    wheels = sorted(dist.resolve().glob("projectlore-*.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected exactly one ProjectLore wheel.")
    with tempfile.TemporaryDirectory(prefix="projectlore-alpha-") as raw:
        root = Path(raw)
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--dest",
                str(wheelhouse),
                "--find-links",
                str(dist.resolve()),
                "projectlore==0.1.0a2",
            ]
        )
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = (
            environment / "Scripts" / "python.exe"
            if os.name == "nt"
            else environment / "bin" / "python"
        )
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        lore = scripts / ("lore.exe" if os.name == "nt" else "lore")
        mcp = scripts / (
            "projectlore-mcp.exe" if os.name == "nt" else "projectlore-mcp"
        )
        hook = scripts / (
            "projectlore-hook.exe" if os.name == "nt" else "projectlore-hook"
        )
        scope_hook = scripts / (
            "projectlore-scope-hook.exe"
            if os.name == "nt"
            else "projectlore-scope-hook"
        )
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                "projectlore==0.1.0a2",
            ]
        )
        _run(
            [
                str(python),
                "-m",
                "projectlore.cli",
                "validate",
                str(example.resolve()),
            ]
        )
        generated = root / "projectlore.schema.json"
        _run(
            [
                str(python),
                "-m",
                "projectlore.cli",
                "schema",
                str(generated),
            ]
        )
        if generated.read_bytes() != schema.resolve().read_bytes():
            raise ValueError("Installed package generated a different JSON Schema.")
        _run(
            [
                str(python),
                "-c",
                "from projectlore.mcp_server import create_server; "
                "from projectlore.adapters import AdapterRegistry; "
                "from projectlore.checker import CheckerRegistry; "
                "from projectlore.integration import capability_matrix; "
                "from pathlib import Path; "
                "assert create_server and AdapterRegistry and CheckerRegistry; "
                "assert capability_matrix(Path.cwd())['matrix_version'] == "
                "'projectlore-client-capabilities/0.1.0'",
            ],
            cwd=root,
        )
        project = root / "fresh-project"
        project.mkdir()
        preview = _run(
            [str(lore), "init", "--name", "ProjectLore Acceptance"],
            cwd=project,
        )
        if list(project.iterdir()):
            raise ValueError("Initialization preview modified the repository.")
        preview_value = json.loads(preview.stdout)
        if preview_value["applied"] is not False:
            raise ValueError("Initialization preview falsely claimed application.")
        _run(
            [
                str(lore),
                "init",
                "--apply",
                "--name",
                "ProjectLore Acceptance",
            ],
            cwd=project,
        )
        _run([str(lore), "validate", "projectlore.yaml"], cwd=project)
        _run(
            [str(scope_hook)],
            cwd=project,
            input_text=json.dumps({"cwd": str(project)}),
        )
        _run(
            [
                str(lore),
                "context",
                "projectlore.yaml",
                "review project knowledge changes",
            ],
            cwd=project,
        )
        asyncio.run(_mcp_smoke(mcp, project))

        allowed_event = {
            "cwd": str(project),
            "tool_name": "Write",
            "tool_input": {"file_path": "ordinary.txt", "content": "allowed"},
        }
        _run(
            [str(hook)],
            cwd=project,
            input_text=json.dumps(allowed_event),
        )
        blocked_event = {
            "cwd": str(project),
            "tool_name": "Write",
            "tool_input": {
                "file_path": "bad.projectlore-policy.json",
                "content": "{not-json",
            },
        }
        blocked = _run(
            [str(hook)],
            cwd=project,
            input_text=json.dumps(blocked_event),
            expected_returncode=2,
        )
        if "ProjectLore policy input rejected" not in blocked.stderr:
            raise ValueError("Installed hook did not explain its blocking decision.")
    print("Fresh offline installation smoke suite passed.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: offline_smoke.py DIST EXAMPLE COMMITTED_SCHEMA")
    verify(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
