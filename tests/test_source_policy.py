from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from projectlore.scope import ScopeSnapshot
from projectlore.source_policy import (
    facts_from_tool_input,
    load_source_bindings,
)

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "examples" / "sienna.campaign-authority.project.yaml"
RULE_ID = "lore:merchant-pricing/rule/discount-cap"
SOURCE_RULE_ID = "lore:sienna/rule/authoritative-command-boundary"
SOURCE = '''from decimal import Decimal

DISCOUNT_RATES = {
    "STANDARD": Decimal("0.00"),
    "GOLD": Decimal("0.20"),
}
'''


def _scope() -> ScopeSnapshot:
    return ScopeSnapshot(
        authority="fraimed",
        frame_id="source-policy-enforcement",
        frame_title="Enforce policy on ordinary source edits",
        frame_status="in_progress",
        validation_open=5,
        observed_at=datetime.now(UTC),
        authority_ref="fraimed://frame/source-policy-enforcement",
    )


def _policy_binding(*, workflow: bool = False) -> dict[str, object]:
    return {
        "rule_id": RULE_ID,
        "left_fact": "discount_rate",
        "relation": "lte",
        "right_fact": None,
        "right_literal": "0.30",
        "value_type": "decimal",
        "failure_outcome": "discount_cap_exceeded",
        "failure_message": "Discount exceeds the approved cap.",
        "scope_requirement": "workflow" if workflow else "none",
    }


def _source_binding() -> dict[str, object]:
    return {
        "path": "pricing.py",
        "fact_name": "discount_rate",
        "selector": "mapping_item",
        "target": "DISCOUNT_RATES",
        "key": "GOLD",
        "value_syntax": "decimal_call",
    }


def _project(
    tmp_path: Path,
    *,
    scope: bool = True,
    workflow: bool = False,
) -> Path:
    model = tmp_path / "projectlore.yaml"
    model.write_text(
        MODEL.read_text(encoding="utf-8").replace(SOURCE_RULE_ID, RULE_ID),
        encoding="utf-8",
    )
    (tmp_path / "pricing.py").write_text(SOURCE, encoding="utf-8")
    registry = tmp_path / ".projectlore"
    registry.mkdir()
    (registry / "policy-bindings.json").write_text(
        json.dumps([_policy_binding(workflow=workflow)]),
        encoding="utf-8",
    )
    (registry / "source-policy-bindings.json").write_text(
        json.dumps([_source_binding()]),
        encoding="utf-8",
    )
    if scope:
        (registry / "scope.json").write_text(
            _scope().model_dump_json(),
            encoding="utf-8",
        )
    return tmp_path


def _run_hook(
    project: Path,
    tool_input: dict[str, Any],
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PROJECTLORE_MODEL"] = "projectlore.yaml"
    return subprocess.run(
        [sys.executable, "-m", "projectlore.hook"],
        cwd=project,
        input=json.dumps(
            {
                "cwd": str(project),
                "tool_name": "Write",
                "tool_input": tool_input,
            }
        ),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def test_full_source_write_allows_compliant_and_blocks_violation(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    compliant = _run_hook(
        project,
        {
            "file_path": "pricing.py",
            "content": SOURCE,
        },
    )
    violating = _run_hook(
        project,
        {
            "file_path": "pricing.py",
            "content": SOURCE.replace('Decimal("0.20")', 'Decimal("0.40")'),
        },
    )

    assert compliant.returncode == 0
    assert violating.returncode == 2
    assert f"{RULE_ID}=discount_cap_exceeded" in violating.stderr
    assert "provenance=" in violating.stderr


def test_edit_and_apply_patch_reconstruct_proposed_source(tmp_path: Path) -> None:
    project = _project(tmp_path)
    edit = _run_hook(
        project,
        {
            "file_path": "pricing.py",
            "old_string": 'Decimal("0.20")',
            "new_string": 'Decimal("0.40")',
        },
    )
    patch = _run_hook(
        project,
        {
            "command": (
                "*** Begin Patch\n"
                "*** Update File: pricing.py\n"
                "@@\n"
                '-    "GOLD": Decimal("0.20"),\n'
                '+    "GOLD": Decimal("0.40"),\n'
                "*** End Patch\n"
            )
        },
    )

    assert edit.returncode == 2
    assert patch.returncode == 2
    assert RULE_ID in edit.stderr
    assert RULE_ID in patch.stderr


def test_apply_patch_add_reconstructs_configured_source(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "pricing.py").unlink()
    result = _run_hook(
        project,
        {
            "command": (
                "*** Begin Patch\n"
                "*** Add File: pricing.py\n"
                + "\n".join(f"+{line}" for line in SOURCE.splitlines())
                + "\n*** End Patch\n"
            )
        },
    )

    assert result.returncode == 0


def test_irrelevant_edit_does_not_require_scope(tmp_path: Path) -> None:
    project = _project(tmp_path, scope=False)

    result = _run_hook(
        project,
        {"file_path": "notes.txt", "content": "not policy-relevant"},
    )

    assert result.returncode == 0


def test_relevant_edit_fails_closed_without_fresh_scope(tmp_path: Path) -> None:
    project = _project(tmp_path, scope=False, workflow=True)

    result = _run_hook(
        project,
        {"file_path": "pricing.py", "content": SOURCE},
    )

    assert result.returncode == 2
    assert "dependency_unavailable" in result.stderr


def test_relevant_edit_fails_closed_with_stale_scope(tmp_path: Path) -> None:
    project = _project(tmp_path, workflow=True)
    stale = _scope().model_copy(
        update={"observed_at": datetime(2020, 1, 1, tzinfo=UTC)}
    )
    (project / ".projectlore" / "scope.json").write_text(
        stale.model_dump_json(),
        encoding="utf-8",
    )

    result = _run_hook(
        project,
        {"file_path": "pricing.py", "content": SOURCE},
    )

    assert result.returncode == 2
    assert "stale_dependency" in result.stderr


def test_dynamic_or_missing_python_selector_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    dynamic = SOURCE.replace('Decimal("0.20")', "get_discount_rate()")
    missing = SOURCE.replace('"GOLD": Decimal("0.20"),\n', "")

    dynamic_result = _run_hook(
        project,
        {"file_path": "pricing.py", "content": dynamic},
    )
    missing_result = _run_hook(
        project,
        {"file_path": "pricing.py", "content": missing},
    )

    assert dynamic_result.returncode == 2
    assert "literal Decimal" in dynamic_result.stderr
    assert missing_result.returncode == 2
    assert "must match once" in missing_result.stderr


def test_source_registry_rejects_authority_and_path_escape(tmp_path: Path) -> None:
    registry = tmp_path / ".projectlore"
    registry.mkdir()
    binding = _source_binding()
    binding["command"] = ["python", "checker.py"]
    (registry / "source-policy-bindings.json").write_text(
        json.dumps([binding]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="registry is invalid"):
        load_source_bindings(tmp_path)

    binding = _source_binding()
    binding["path"] = "../pricing.py"
    (registry / "source-policy-bindings.json").write_text(
        json.dumps([binding]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="relative, confined Python"):
        load_source_bindings(tmp_path)


def test_fact_extraction_does_not_execute_python(tmp_path: Path) -> None:
    project = _project(tmp_path)
    marker = tmp_path / "executed.txt"
    malicious = (
        "from decimal import Decimal\n"
        f'open({str(marker)!r}, "w").write("executed")\n'
        'DISCOUNT_RATES = {"GOLD": Decimal("0.20")}\n'
    )

    facts = facts_from_tool_input(
        project,
        {"file_path": "pricing.py", "content": malicious},
    )

    assert facts == {"discount_rate": "0.20"}
    assert not marker.exists()


def test_configured_source_link_fails_closed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    target = project / "target.py"
    target.write_text(SOURCE, encoding="utf-8")
    (project / "pricing.py").unlink()
    try:
        (project / "pricing.py").symlink_to(target)
    except OSError:
        pytest.skip("Creating a test symlink is not permitted.")

    result = _run_hook(
        project,
        {"file_path": "pricing.py", "content": SOURCE},
    )

    assert result.returncode == 2
    assert "cannot traverse links" in result.stderr
