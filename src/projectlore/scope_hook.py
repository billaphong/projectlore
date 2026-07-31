"""Advisory SessionStart hook that refreshes configured Fraimed scope."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from projectlore.scope_cache import load_scope_target, refresh_scope_from_environment
from projectlore.workflow import DeclaredWorkflowContext
from projectlore.workflow_state import CONTEXT_PATH, load_workflow_context
from projectlore.workflow_target import load_workflow_target

MAX_INPUT_BYTES = 65_536


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return _advise("ProjectLore scope hook input exceeds 64 KiB.")
    try:
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise ValueError("Scope hook input must be a JSON object.")
        cwd_value = event.get("cwd")
        if not isinstance(cwd_value, str) or not cwd_value:
            raise ValueError("Scope hook field 'cwd' is required.")
        root = Path(cwd_value).resolve(strict=True)
        if (root / CONTEXT_PATH).is_file():
            context = load_workflow_context(root)
            if isinstance(context, DeclaredWorkflowContext):
                return 0
        if load_workflow_target(root) is None and load_scope_target(
            root, required=False
        ) is None:
            return 0
        path, snapshot = asyncio.run(refresh_scope_from_environment(root))
    except (
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        TimeoutError,
        ValueError,
    ) as error:
        return _advise(f"ProjectLore scope refresh unavailable: {error}")
    print(
        json.dumps(
            {
                "refreshed": True,
                "path": str(path),
                "scope_id": snapshot.frame_id,
                "frame_id": snapshot.frame_id,
                "authority_ref": snapshot.authority_ref,
            },
            separators=(",", ":"),
        )
    )
    return 0


def _advise(message: str) -> int:
    print(message[:1000], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
