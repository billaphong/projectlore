"""Semantic validation shared by acquisition boundary adapters."""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path, PurePosixPath


class UnsafePathError(ValueError):
    """A supplied acquisition path escapes or aliases the repository root."""


def validate_relative_path(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value:
        raise UnsafePathError("path must already be NFC normalized")
    if not 1 <= len(value.encode("utf-8")) <= 1024:
        raise UnsafePathError("path must contain 1..1024 UTF-8 bytes")
    if "\\" in value or "\x00" in value:
        raise UnsafePathError("path must use '/' and contain no NUL")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise UnsafePathError("path must be a normalized root-relative path")
    return value


def confined_path(root: Path, relative: str, *, must_exist: bool = False) -> Path:
    """Resolve a root-relative path and reject symlinks and escapes."""

    validate_relative_path(relative)
    root = root.resolve(strict=True)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    cursor = root
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise UnsafePathError(f"symlink component is forbidden: {relative}")
    resolved = candidate.resolve(strict=must_exist)
    try:
        common = Path(os.path.commonpath((root, resolved)))
    except ValueError as error:
        raise UnsafePathError("path is outside the repository root") from error
    if common != root:
        raise UnsafePathError("path is outside the repository root")
    return resolved
