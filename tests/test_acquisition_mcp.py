from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from projectlore.acquisition.onboarding import start_onboarding
from projectlore.acquisition.store import KnowledgeStore
from projectlore.acquisition_mcp import create_server
from projectlore.onboarding import apply_initialization, initialization_previews
from projectlore.removal import apply_removal, removal_previews


def _files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_sidecar_has_exact_read_only_tool_names(tmp_path: Path) -> None:
    tools = asyncio.run(create_server(tmp_path).list_tools())
    assert {tool.name for tool in tools} == {
        "knowledge_status",
        "knowledge_get_packet",
        "knowledge_get_proposal",
        "knowledge_get_review",
        "knowledge_get_receipt",
    }
    assert all(tool.annotations.readOnlyHint for tool in tools)


def test_sidecar_reads_do_not_mutate_repository(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    _, packet = start_onboarding(tmp_path)
    server = create_server(tmp_path)
    before = _files(tmp_path)

    status = asyncio.run(server.call_tool("knowledge_status", {}))
    page = asyncio.run(
        server.call_tool("knowledge_get_packet", {"id": packet.packet_id})
    )

    assert isinstance(status, tuple)
    assert status[1]["state"] == "outstanding"
    assert isinstance(page, tuple)
    assert page[1]["items"][0]["packet_id"] == packet.packet_id
    assert _files(tmp_path) == before


def test_sidecar_distinguishes_missing_from_empty(tmp_path: Path) -> None:
    server = create_server(tmp_path)
    status = asyncio.run(server.call_tool("knowledge_status", {}))
    packets = asyncio.run(server.call_tool("knowledge_get_packet", {}))
    assert isinstance(status, tuple)
    assert status[1]["state"] == "missing"
    assert isinstance(packets, tuple)
    assert packets[1]["state"] == "missing"
    assert packets[1]["items"] == []

    KnowledgeStore(tmp_path).initialize()
    initialized = asyncio.run(server.call_tool("knowledge_get_packet", {}))
    assert isinstance(initialized, tuple)
    assert initialized[1]["state"] == "present"
    assert initialized[1]["items"] == []


def test_sidecar_cursor_is_stable_and_selector_is_exclusive(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    server = create_server(tmp_path)
    first = asyncio.run(server.call_tool("knowledge_get_packet", {"limit": 1}))
    assert isinstance(first, tuple)
    with pytest.raises(Exception, match="mutually exclusive"):
        asyncio.run(
            server.call_tool(
                "knowledge_get_packet",
                {
                    "id": first[1]["items"][0]["packet_id"],
                    "cursor": "sha256:" + "0" * 64,
                },
            )
        )
    stale = asyncio.run(
        server.call_tool("knowledge_get_packet", {"cursor": "sha256:" + "0" * 64})
    )
    assert stale.isError is True
    assert stale.structuredContent == {
        "code": "PLKA4004",
        "message": "PLKA4004 stale or invalid acquisition cursor",
        "retryable": True,
    }
    assert stale.content[0].text == (
        '{"code":"PLKA4004","message":"PLKA4004 stale or invalid acquisition '
        'cursor","retryable":true}'
    )


def test_removal_cleans_sidecar_hooks_and_disposable_state(tmp_path: Path) -> None:
    apply_initialization(initialization_previews(tmp_path, project_name="Acme"))
    start_onboarding(tmp_path)
    canonical = (tmp_path / "projectlore.yaml").read_bytes()
    previews = removal_previews(tmp_path)
    apply_removal(previews)
    assert (tmp_path / "projectlore.yaml").read_bytes() == canonical
    assert not any(
        path.is_file() for path in (tmp_path / ".projectlore" / "knowledge").rglob("*")
    )
    assert "projectlore-acquisition" not in (tmp_path / ".mcp.json").read_text(
        encoding="utf-8"
    )
