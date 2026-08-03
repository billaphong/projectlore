"""Deterministic, domain-separated identities for acquisition objects."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented by the acquisition profile."""


def _validate(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise CanonicalizationError("floating-point values are not supported")
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalizationError("JSON object keys must be strings")
        for item in value.values():
            _validate(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _validate(item)
        return
    raise CanonicalizationError(f"unsupported JSON value: {type(value).__name__}")


def canonical_json(value: Any) -> bytes:
    """Return the RFC 8785-compatible bytes for the supported value profile.

    Acquisition contracts use strings, booleans, integers, nulls, arrays, and
    objects. Floats are deliberately rejected, avoiding cross-runtime number
    serialization ambiguity.
    """

    _validate(value)
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return rendered.encode("utf-8")


def content_digest(
    domain: str,
    value: Mapping[str, Any],
    *,
    exclude: Sequence[str] = (),
) -> str:
    """Hash an object using the frozen domain-NUL-JCS convention."""

    if not domain or "\x00" in domain:
        raise ValueError("digest domain must be non-empty and contain no NUL")
    excluded = frozenset(exclude)
    payload = {key: item for key, item in value.items() if key not in excluded}
    preimage = domain.encode("utf-8") + b"\x00" + canonical_json(payload)
    return f"sha256:{hashlib.sha256(preimage).hexdigest()}"
