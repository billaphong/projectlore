"""Deterministic facts extracted from bounded proposed Python source."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import Field, TypeAdapter, ValidationError

from projectlore.models import StrictModel
from projectlore.scope import ScopeSnapshot
from projectlore.scope_cache import load_scope_target
from projectlore.workflow import (
    DeclaredWorkflowContext,
    LocalScopeProvider,
    WorkflowTarget,
    WorkflowTargetMismatch,
)
from projectlore.workflow_compat import observation_to_legacy_snapshot
from projectlore.workflow_state import CONTEXT_PATH, load_workflow_context
from projectlore.workflow_target import load_workflow_target

SOURCE_BINDINGS_PATH = Path(".projectlore/source-policy-bindings.json")
SCOPE_SNAPSHOT_PATH = Path(".projectlore/scope.json")
MAX_SOURCE_BINDINGS_BYTES = 64 * 1024
MAX_SCOPE_SNAPSHOT_BYTES = 16 * 1024
MAX_PROPOSED_SOURCE_BYTES = 256 * 1024


class SourceFactBinding(StrictModel):
    """One operator-reviewed mapping from Python syntax to a policy fact."""

    path: str = Field(min_length=1, max_length=1024)
    fact_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")
    selector: Literal["assignment", "mapping_item"]
    target: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    key: str | None = Field(default=None, min_length=1, max_length=256)
    value_syntax: Literal["decimal_call"] = "decimal_call"


_BINDINGS_ADAPTER = TypeAdapter(tuple[SourceFactBinding, ...])


@dataclass(frozen=True)
class ProposedSource:
    path: Path
    content: str


def load_source_bindings(root: Path) -> tuple[SourceFactBinding, ...]:
    """Load a strict bounded project-local source-fact registry."""
    path = _configured_path(root, SOURCE_BINDINGS_PATH)
    if not path.is_file():
        return ()
    raw = path.read_bytes()
    if len(raw) > MAX_SOURCE_BINDINGS_BYTES:
        raise ValueError("Source-policy registry exceeds 64 KiB.")
    try:
        bindings = _BINDINGS_ADAPTER.validate_json(raw, strict=True)
    except ValidationError as error:
        raise ValueError(f"Source-policy registry is invalid: {error}") from error
    seen: set[tuple[str, str]] = set()
    for binding in bindings:
        relative = _binding_path(binding.path)
        key = (relative.as_posix(), binding.fact_name)
        if key in seen:
            raise ValueError("Source-policy path and fact pairs must be unique.")
        seen.add(key)
        if binding.selector == "assignment" and binding.key is not None:
            raise ValueError("Assignment selectors cannot declare a key.")
        if binding.selector == "mapping_item" and binding.key is None:
            raise ValueError("Mapping-item selectors require a key.")
    return bindings


def load_scope_snapshot(
    root: Path, *, required: bool = True
) -> ScopeSnapshot | None:
    """Load optional provider-neutral workflow scope state."""
    canonical_path = _configured_path(root, CONTEXT_PATH)
    if canonical_path.is_file():
        context = load_workflow_context(root)
        if not context.valid_at(datetime.now(UTC)):
            raise ValueError("Workflow context has expired or become stale.")
        if isinstance(context, DeclaredWorkflowContext):
            workflow_target = WorkflowTarget(
                target_version="projectlore-workflow-target/1.0.0",
                project_id=context.project_id,
                model_entrypoint=context.model_entrypoint,
                provider_id=context.provider_id,
                scope_id=context.scope_id,
                container_id=context.container_id,
            )
            observation = LocalScopeProvider(context).current_observation(
                workflow_target
            )
        else:
            configured_target = load_workflow_target(root)
            if configured_target is None:
                raise ValueError(
                    "Observed workflow context requires a configured target."
                )
            try:
                context.observation.validate_target(configured_target)
            except WorkflowTargetMismatch as error:
                raise ValueError(
                    "Workflow observation does not match the configured target; "
                    "run 'lore scope refresh'."
                ) from error
            observation = context.observation
        return observation_to_legacy_snapshot(observation)
    configured_target = load_workflow_target(root)
    if configured_target is not None:
        raise ValueError(
            "Configured workflow target has no target-bound observation; "
            "run 'lore scope refresh'."
        )
    path = _configured_path(root, SCOPE_SNAPSHOT_PATH)
    if not path.is_file():
        if required:
            raise ValueError(
                "Workflow-scoped policy requires .projectlore/scope.json."
            )
        return None
    raw = path.read_bytes()
    if len(raw) > MAX_SCOPE_SNAPSHOT_BYTES:
        raise ValueError("Scope snapshot exceeds 16 KiB.")
    try:
        snapshot = ScopeSnapshot.model_validate_json(raw)
    except ValidationError as error:
        raise ValueError(f"Scope snapshot is invalid: {error}") from error
    target = load_scope_target(root, required=False)
    if (
        target is not None
        and snapshot.authority == "fraimed"
        and snapshot.frame_id != target.frame_id
    ):
        raise ValueError(
            "Scope snapshot does not match the configured Fraimed Frame; "
            "run 'lore scope refresh'."
        )
    return snapshot


def facts_from_tool_input(
    root: Path,
    tool_input: dict[str, Any],
) -> dict[str, str] | None:
    """Extract facts when a supported tool proposes a configured source edit."""
    bindings = load_source_bindings(root)
    if not bindings:
        return None
    proposed = _proposed_sources(root, tool_input, bindings)
    if not proposed:
        return None
    facts: dict[str, str] = {}
    by_path: dict[str, list[SourceFactBinding]] = {}
    for binding in bindings:
        by_path.setdefault(_binding_path(binding.path).as_posix(), []).append(binding)
    for source in proposed:
        relative = source.path.relative_to(root).as_posix()
        selected = by_path.get(relative)
        if selected is None:
            continue
        extracted = _extract_python_facts(source.content, selected)
        overlap = facts.keys() & extracted.keys()
        if overlap:
            raise ValueError(f"Duplicate extracted policy fact: {min(overlap)}")
        facts.update(extracted)
    return facts or None


def configured_source_paths(root: Path) -> tuple[str, ...]:
    """Return deterministic configured source paths."""
    return tuple(
        sorted(
            {
                _binding_path(binding.path).as_posix()
                for binding in load_source_bindings(root)
            }
        )
    )


def facts_from_paths(root: Path, paths: tuple[str, ...]) -> dict[str, str]:
    """Extract configured facts from checked-out source files."""
    bindings = load_source_bindings(root)
    if not bindings:
        raise ValueError("No source-policy bindings are configured.")
    configured: dict[str, list[SourceFactBinding]] = {}
    for binding in bindings:
        configured.setdefault(_binding_path(binding.path).as_posix(), []).append(
            binding
        )
    selected = tuple(sorted({_binding_path(raw).as_posix() for raw in paths}))
    if not selected:
        raise ValueError("At least one configured source path is required.")
    facts: dict[str, str] = {}
    for relative in selected:
        path_bindings = configured.get(relative)
        if path_bindings is None:
            raise ValueError(f"Source path is not configured for policy: {relative}")
        path = _confined_path(root, relative)
        extracted = _extract_python_facts(_read_bounded_source(path), path_bindings)
        overlap = facts.keys() & extracted.keys()
        if overlap:
            raise ValueError(f"Duplicate extracted policy fact: {min(overlap)}")
        facts.update(extracted)
    return facts


def _proposed_sources(
    root: Path,
    tool_input: dict[str, Any],
    bindings: tuple[SourceFactBinding, ...],
) -> tuple[ProposedSource, ...]:
    configured = {_binding_path(item.path).as_posix() for item in bindings}
    file_path = tool_input.get("file_path")
    content = tool_input.get("content")
    if isinstance(file_path, str) and isinstance(content, str):
        path = _confined_path(root, file_path)
        if path.relative_to(root).as_posix() not in configured:
            return ()
        return (ProposedSource(path, _bounded_source(content)),)

    if isinstance(file_path, str):
        old = tool_input.get("old_string")
        new = tool_input.get("new_string")
        if isinstance(old, str) and isinstance(new, str):
            path = _confined_path(root, file_path)
            if path.relative_to(root).as_posix() not in configured:
                return ()
            current = _read_bounded_source(path)
            count = current.count(old)
            replace_all = tool_input.get("replace_all") is True
            if count == 0:
                raise ValueError("Edit old_string was not found.")
            if count > 1 and not replace_all:
                raise ValueError("Edit old_string is not unique.")
            proposed = current.replace(old, new, -1 if replace_all else 1)
            return (ProposedSource(path, _bounded_source(proposed)),)

    command = tool_input.get("command")
    if isinstance(command, str) and command.startswith("*** Begin Patch"):
        return _sources_from_patch(root, command, configured)
    return ()


def _sources_from_patch(
    root: Path,
    patch: str,
    configured: set[str],
) -> tuple[ProposedSource, ...]:
    if len(patch.encode()) > MAX_PROPOSED_SOURCE_BYTES:
        raise ValueError("Source patch exceeds 256 KiB.")
    sections = _patch_sections(patch)
    proposed: list[ProposedSource] = []
    for operation, raw_path, body in sections:
        path = _confined_path(root, raw_path)
        if path.relative_to(root).as_posix() not in configured:
            continue
        if operation == "add":
            if any(not line.startswith("+") for line in body):
                raise ValueError("Added source patch lines must start with '+'.")
            content = "\n".join(line[1:] for line in body) + "\n"
        else:
            content = _apply_update_patch(_read_bounded_source(path), body)
        proposed.append(ProposedSource(path, _bounded_source(content)))
    return tuple(proposed)


def _patch_sections(patch: str) -> list[tuple[str, str, list[str]]]:
    lines = patch.splitlines()
    if not lines or lines[0] != "*** Begin Patch":
        raise ValueError("Malformed source patch.")
    sections: list[tuple[str, str, list[str]]] = []
    current: tuple[str, str, list[str]] | None = None
    for line in lines[1:]:
        if line.startswith("*** Add File: "):
            current = ("add", line.removeprefix("*** Add File: ").strip(), [])
            sections.append(current)
        elif line.startswith("*** Update File: "):
            current = (
                "update",
                line.removeprefix("*** Update File: ").strip(),
                [],
            )
            sections.append(current)
        elif line == "*** End Patch" or (
            line.startswith("*** ") and not line.startswith("*** End of File")
        ):
            current = None
        elif current is not None:
            current[2].append(line)
    return sections


def _apply_update_patch(current: str, body: list[str]) -> str:
    lines = current.splitlines()
    trailing_newline = current.endswith("\n")
    hunks: list[list[str]] = []
    hunk: list[str] = []
    for line in body:
        if line.startswith("@@"):
            if hunk:
                hunks.append(hunk)
            hunk = []
        elif line != "*** End of File":
            hunk.append(line)
    if hunk:
        hunks.append(hunk)
    if not hunks:
        raise ValueError("Source update patch contains no hunks.")
    for patch_hunk in hunks:
        if any(not line or line[0] not in {" ", "+", "-"} for line in patch_hunk):
            raise ValueError("Malformed source update hunk.")
        old = [line[1:] for line in patch_hunk if line[0] in {" ", "-"}]
        new = [line[1:] for line in patch_hunk if line[0] in {" ", "+"}]
        starts = [
            index
            for index in range(len(lines) - len(old) + 1)
            if lines[index : index + len(old)] == old
        ]
        if len(starts) != 1:
            raise ValueError("Source update hunk must match exactly once.")
        start = starts[0]
        lines[start : start + len(old)] = new
    result = "\n".join(lines)
    return result + "\n" if trailing_newline else result


def _extract_python_facts(
    content: str,
    bindings: list[SourceFactBinding],
) -> dict[str, str]:
    try:
        tree = ast.parse(content)
    except SyntaxError as error:
        raise ValueError(
            f"Proposed Python source is invalid at line {error.lineno}."
        ) from error
    assignments: dict[str, ast.expr] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                assignments[target.id] = statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.value is not None
        ):
            assignments[statement.target.id] = statement.value
    facts: dict[str, str] = {}
    for binding in bindings:
        value = assignments.get(binding.target)
        if value is None:
            raise ValueError(
                f"Python selector target {binding.target!r} is missing."
            )
        if binding.selector == "mapping_item":
            value = _mapping_value(value, binding.target, binding.key)
        facts[binding.fact_name] = _decimal_literal(value)
    return facts


def _mapping_value(
    value: ast.expr,
    target: str,
    key: str | None,
) -> ast.expr:
    if not isinstance(value, ast.Dict) or key is None:
        raise ValueError(f"Python selector target {target!r} is not a dict.")
    matches = [
        item_value
        for item_key, item_value in zip(value.keys, value.values, strict=True)
        if isinstance(item_key, ast.Constant) and item_key.value == key
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Python mapping selector {target}[{key!r}] must match once."
        )
    return matches[0]


def _decimal_literal(value: ast.expr) -> str:
    if (
        not isinstance(value, ast.Call)
        or not isinstance(value.func, ast.Name)
        or value.func.id != "Decimal"
        or len(value.args) != 1
        or value.keywords
        or not isinstance(value.args[0], ast.Constant)
        or not isinstance(value.args[0].value, str)
    ):
        raise ValueError(
            "Source-policy values must use the literal Decimal(\"value\") form."
        )
    return value.args[0].value


def _binding_path(raw: str) -> PurePosixPath:
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
        raise ValueError(
            "Source-policy paths must be relative, confined Python files."
        )
    return path


def _configured_path(root: Path, relative: Path) -> Path:
    return _confined_path(root, str(relative))


def _confined_path(root: Path, raw: str) -> Path:
    candidate = Path(raw)
    root = root.resolve()
    lexical = Path(
        os.path.abspath(root / candidate if not candidate.is_absolute() else candidate)
    )
    if lexical != root and root not in lexical.parents:
        raise ValueError(f"Path escapes project root: {raw}")
    resolved = lexical.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path escapes project root: {raw}")
    if resolved != lexical:
        raise ValueError(f"Source-policy paths cannot traverse links: {raw}")
    return resolved


def _read_bounded_source(path: Path) -> str:
    raw = path.read_bytes()
    if len(raw) > MAX_PROPOSED_SOURCE_BYTES:
        raise ValueError("Configured source exceeds 256 KiB.")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Configured source must be UTF-8.") from error


def _bounded_source(value: str) -> str:
    if len(value.encode()) > MAX_PROPOSED_SOURCE_BYTES:
        raise ValueError("Proposed source exceeds 256 KiB.")
    return value
