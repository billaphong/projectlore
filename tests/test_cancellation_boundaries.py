from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest

import projectlore.cli as cli_module
import projectlore.hook as hook_module
import projectlore.scope_hook as scope_hook_module
import projectlore.source_gate as source_gate_module
from projectlore.evaluation import evaluate_once
from projectlore.service import ModelService
from projectlore.workflow import WorkflowTarget
from projectlore.workflow_target import configure_workflow_target

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "examples" / "homebrew.forecast-trust.project.yaml"
CORPUS = ROOT / "evaluations" / "homebrew-forecast-trust" / "corpus.yaml"


class CancellingAuthority:
    async def current_scope(self, frame_id: str, space_id: str | None) -> object:
        raise asyncio.CancelledError


def _stdin(payload: dict[str, object]) -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode()))


def test_evaluation_propagates_cancellation(tmp_path: Path) -> None:
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            evaluate_once(
                CORPUS,
                tmp_path / "evidence.json",
                provider="fraimed",
                scope_id="work",
                container_id="workspace",
                scope_authority=CancellingAuthority(),
            )
        )


def test_cli_propagates_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def cancel(*args: object, **kwargs: object) -> dict[str, object]:
        raise asyncio.CancelledError

    monkeypatch.setattr(cli_module, "evaluate_once", cancel)
    with pytest.raises(asyncio.CancelledError):
        cli_module.main(["evaluate", str(CORPUS), "evidence.json"])


def test_session_start_propagates_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_workflow_target(
        tmp_path,
        WorkflowTarget(
            target_version="projectlore-workflow-target/1.0.0",
            project_id="lore:test/project",
            model_entrypoint="projectlore.yaml",
            provider_id="fraimed",
            scope_id="work",
            container_id="workspace",
        ),
    )

    async def cancel(root: Path) -> object:
        raise asyncio.CancelledError

    monkeypatch.setattr(scope_hook_module, "refresh_scope_from_environment", cancel)
    monkeypatch.setattr(
        scope_hook_module.sys, "stdin", _stdin({"cwd": str(tmp_path)})
    )
    with pytest.raises(asyncio.CancelledError):
        scope_hook_module.main()


def test_pre_action_hook_propagates_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "projectlore.yaml"
    model.write_text(MODEL.read_text(encoding="utf-8"), encoding="utf-8")

    def shutdown(*args: object, **kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(hook_module, "facts_from_tool_input", shutdown)
    monkeypatch.setattr(
        hook_module.sys,
        "stdin",
        _stdin({"cwd": str(tmp_path), "tool_input": {"command": "true"}}),
    )
    with pytest.raises(KeyboardInterrupt):
        hook_module.main()


def test_pre_action_hook_does_not_compile_model_for_irrelevant_tool_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "projectlore.yaml"
    model.write_text(MODEL.read_text(encoding="utf-8"), encoding="utf-8")

    def unexpected_compile(*args: object, **kwargs: object) -> object:
        raise AssertionError("irrelevant tool input compiled the project model")

    monkeypatch.setattr(hook_module, "ModelService", unexpected_compile)
    monkeypatch.setattr(
        hook_module.sys,
        "stdin",
        _stdin({"cwd": str(tmp_path), "tool_input": {"command": "node app.mjs"}}),
    )
    assert hook_module.main() == 0


def test_source_gate_propagates_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def shutdown(*args: object, **kwargs: object) -> dict[str, str]:
        raise KeyboardInterrupt

    monkeypatch.setattr(source_gate_module, "facts_from_paths", shutdown)
    with pytest.raises(KeyboardInterrupt):
        source_gate_module.evaluate_source_gate(
            ROOT,
            ModelService(MODEL),
            ("anything.py",),
            assurance_scope="local_advisory",
        )
