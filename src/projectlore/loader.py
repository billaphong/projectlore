"""Bounded, repository-confined YAML loading with source locations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode


@dataclass(frozen=True)
class LoaderLimits:
    maximum_file_bytes: int = 1_048_576
    maximum_total_bytes: int = 4_194_304
    maximum_files: int = 32
    maximum_depth: int = 64
    maximum_nodes: int = 50_000


@dataclass(frozen=True)
class SourceLocation:
    file: Path
    line: int
    column: int


@dataclass(frozen=True)
class LoadedDocument:
    value: Any
    locations: dict[str, SourceLocation]
    files: tuple[Path, ...]


class LoaderError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        file: Path,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.file = file
        self.line = line
        self.column = column


def discover_model(repository_root: Path) -> Path:
    root = repository_root.resolve()
    candidates = (
        root / ".projectlore" / "model.yaml",
        root / "projectlore.yaml",
    )
    existing = [candidate for candidate in candidates if candidate.exists()]
    if not existing:
        raise FileNotFoundError(f"No ProjectLore model found under: {root}")
    if len(existing) > 1:
        raise LoaderError(
            "PL1108",
            "Multiple ProjectLore entrypoints found.",
            file=root,
        )
    return _confined_path(existing[0], root, existing[0])


def project_root_for_model(entrypoint: Path) -> Path:
    """Return the repository root implied by a supported model entrypoint."""
    resolved = entrypoint.resolve()
    if resolved.name == "model.yaml" and resolved.parent.name == ".projectlore":
        return resolved.parent.parent
    return resolved.parent


def load_repository_model(
    entrypoint: Path,
    *,
    repository_root: Path | None = None,
    limits: LoaderLimits | None = None,
) -> LoadedDocument:
    """Load an entrypoint and its includes without leaving the repository."""
    selected_limits = limits or LoaderLimits()
    root = (repository_root or entrypoint.parent).resolve()
    entry = _confined_path(entrypoint, root, entrypoint)
    state = _LoadState(root=root, limits=selected_limits)
    value, locations = state.load(entry, stack=())
    return LoadedDocument(
        value=value,
        locations=locations,
        files=tuple(state.files),
    )


@dataclass
class _LoadState:
    root: Path
    limits: LoaderLimits
    total_bytes: int = 0
    total_nodes: int = 0
    files: list[Path] = field(default_factory=list)

    def load(
        self,
        path: Path,
        *,
        stack: tuple[Path, ...],
    ) -> tuple[dict[str, Any], dict[str, SourceLocation]]:
        if path in stack:
            raise LoaderError("PL1106", "Include cycle detected.", file=path)
        if path not in self.files:
            if len(self.files) >= self.limits.maximum_files:
                raise LoaderError(
                    "PL1103",
                    "Included file count limit exceeded.",
                    file=path,
                )
            self.files.append(path)

        raw = path.read_bytes()
        if len(raw) > self.limits.maximum_file_bytes:
            raise LoaderError("PL1102", "YAML file size limit exceeded.", file=path)
        self.total_bytes += len(raw)
        if self.total_bytes > self.limits.maximum_total_bytes:
            raise LoaderError("PL1102", "Total YAML size limit exceeded.", file=path)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise LoaderError("PL1101", "YAML must be UTF-8.", file=path) from error

        try:
            root_node = yaml.compose(text, Loader=yaml.SafeLoader)
            value = yaml.safe_load(text)
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            raise LoaderError(
                "PL1001",
                str(error),
                file=path,
                line=None if mark is None else mark.line + 1,
                column=None if mark is None else mark.column + 1,
            ) from error
        if root_node is None or not isinstance(value, dict):
            raise LoaderError("PL1101", "YAML root must be a mapping.", file=path)

        locations: dict[str, SourceLocation] = {}
        self._map_locations(root_node, path, "$", 0, locations, set())
        includes = value.pop("includes", [])
        if not isinstance(includes, list) or not all(
            isinstance(item, str) and item for item in includes
        ):
            raise LoaderError("PL1101", "includes must be a list of paths.", file=path)

        merged: dict[str, Any] = {}
        merged_locations: dict[str, SourceLocation] = {}
        for include in includes:
            include_path = _confined_path(path.parent / include, self.root, path)
            child, child_locations = self.load(
                include_path,
                stack=(*stack, path),
            )
            child_locations = _rebase_locations(child_locations, merged)
            _merge_model(merged, child, include_path)
            merged_locations.update(child_locations)
        _merge_model(merged, value, path)
        merged_locations.update(locations)
        return merged, merged_locations

    def _map_locations(
        self,
        node: Node,
        file: Path,
        path: str,
        depth: int,
        locations: dict[str, SourceLocation],
        seen: set[int],
    ) -> None:
        if depth > self.limits.maximum_depth:
            raise LoaderError("PL1104", "YAML nesting depth limit exceeded.", file=file)
        node_id = id(node)
        if node_id in seen:
            raise LoaderError("PL1105", "YAML aliases are not supported.", file=file)
        seen.add(node_id)
        self.total_nodes += 1
        if self.total_nodes > self.limits.maximum_nodes:
            raise LoaderError("PL1104", "YAML node count limit exceeded.", file=file)
        locations[path] = SourceLocation(
            file=file,
            line=node.start_mark.line + 1,
            column=node.start_mark.column + 1,
        )
        if isinstance(node, MappingNode):
            for key_node, value_node in node.value:
                key = key_node.value if isinstance(key_node, ScalarNode) else "?"
                child_path = key if path == "$" else f"{path}.{key}"
                self._map_locations(
                    value_node, file, child_path, depth + 1, locations, seen
                )
        elif isinstance(node, SequenceNode):
            for index, child in enumerate(node.value):
                self._map_locations(
                    child, file, f"{path}.{index}", depth + 1, locations, seen
                )


def _confined_path(candidate: Path, root: Path, referring_file: Path) -> Path:
    if candidate.is_symlink():
        raise LoaderError(
            "PL1101",
            "Symlinked model files are not allowed.",
            file=candidate,
        )
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise LoaderError(
            "PL1101",
            "Model path escapes the repository root.",
            file=referring_file,
        )
    if not resolved.is_file():
        raise FileNotFoundError(f"Project knowledge model not found: {resolved}")
    return resolved


def _merge_model(target: dict[str, Any], source: dict[str, Any], file: Path) -> None:
    list_fields = {
        "domains",
        "concepts",
        "relationships",
        "rules",
        "sources",
    }
    for key, value in source.items():
        if key in list_fields:
            if not isinstance(value, list):
                raise LoaderError("PL1101", f"{key} must be a list.", file=file)
            target.setdefault(key, []).extend(value)
        elif key in target and target[key] != value:
            raise LoaderError(
                "PL1107",
                f"Conflicting included value for {key!r}.",
                file=file,
            )
        else:
            target[key] = value


def _rebase_locations(
    locations: dict[str, SourceLocation],
    target: dict[str, Any],
) -> dict[str, SourceLocation]:
    list_fields = ("domains", "concepts", "relationships", "rules", "sources")
    offsets = {
        field: len(target.get(field, []))
        for field in list_fields
        if isinstance(target.get(field, []), list)
    }
    rebased: dict[str, SourceLocation] = {}
    for path, location in locations.items():
        updated = path
        for field_name, offset in offsets.items():
            prefix = f"{field_name}."
            if path.startswith(prefix):
                remainder = path[len(prefix) :]
                index_text, separator, tail = remainder.partition(".")
                if index_text.isdigit():
                    updated = f"{field_name}.{int(index_text) + offset}"
                    if separator:
                        updated = f"{updated}.{tail}"
                break
        rebased[updated] = location
    return rebased
