from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import yaml

from projectlore.mcp_server import create_server
from projectlore.refresh import RefreshingModelService

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"


def _copy_model(tmp_path: Path) -> Path:
    path = tmp_path / "model.yaml"
    shutil.copyfile(MODEL, path)
    return path


def _rewrite(path: Path, update: dict[str, object]) -> None:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document.update(update)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def test_valid_refresh_activates_without_reconstructing_service(
    tmp_path: Path,
) -> None:
    path = _copy_model(tmp_path)
    models = RefreshingModelService(path)
    before = models.refresh()

    _rewrite(path, {"model_version": "0.1.1"})
    after = models.refresh()

    assert before.service.project.digest != after.service.project.digest
    assert after.service.model.model_version == "0.1.1"
    assert after.state == "current"
    assert after.diagnostics == ()


def test_invalid_refresh_preserves_last_valid_snapshot_and_discloses_diagnostics(
    tmp_path: Path,
) -> None:
    path = _copy_model(tmp_path)
    models = RefreshingModelService(path)
    before = models.refresh()

    _rewrite(path, {"schema_version": "1.0.0"})
    after = models.refresh()

    assert after.state == "last_valid"
    assert after.service.project.digest == before.service.project.digest
    assert after.service.model.schema_version == "0.1.0"
    assert any(item["code"] == "PL2301" for item in after.diagnostics)
    decorated = after.decorate(after.service.model_status())
    assert decorated["freshness"]["refresh_state"] == "last_valid"
    assert decorated["freshness"]["refresh_diagnostics"]


def test_mcp_process_observes_valid_then_invalid_edits_without_restart(
    tmp_path: Path,
) -> None:
    path = _copy_model(tmp_path)
    server = create_server(path, _UnusedScopeAuthority())

    initial = asyncio.run(server.call_tool("model_status", {}))
    assert isinstance(initial, tuple)
    initial_payload = initial[1]

    _rewrite(path, {"model_version": "0.1.1"})
    refreshed = asyncio.run(server.call_tool("model_status", {}))
    assert isinstance(refreshed, tuple)
    refreshed_payload = refreshed[1]
    assert refreshed_payload["model_version"] == "0.1.1"
    assert refreshed_payload["model_digest"] != initial_payload["model_digest"]
    assert refreshed_payload["freshness"]["refresh_state"] == "current"

    _rewrite(path, {"schema_version": "1.0.0"})
    invalid = asyncio.run(server.call_tool("model_validate", {}))
    context = asyncio.run(
        server.call_tool(
            "context_for_task",
            {"task": "calibration evidence forecast"},
        )
    )
    assert isinstance(invalid, tuple)
    assert isinstance(context, tuple)
    invalid_payload = invalid[1]
    context_payload = context[1]
    assert invalid_payload["valid"] is False
    assert invalid_payload["freshness"]["refresh_state"] == "last_valid"
    assert invalid_payload["model_digest"] == refreshed_payload["model_digest"]
    assert context_payload["model_digest"] == refreshed_payload["model_digest"]
    assert context_payload["rules"]


class _UnusedScopeAuthority:
    async def current_scope(self, frame_id: str, space_id: str) -> object:
        raise AssertionError("Policy scope is not used by this test.")
