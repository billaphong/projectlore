"""Privacy-safe lifecycle hook for passive knowledge acquisition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from projectlore.acquisition.passive import capture_scan, next_packet
from projectlore.acquisition.review import recover_commit_claim

MAX_INPUT_BYTES = 1_048_576
MAX_DEPTH = 32
MAX_NODES = 100_000


def _bounded_shape(value: Any, *, depth: int = 0) -> int:
    if depth > MAX_DEPTH:
        raise ValueError("hook input nesting exceeds 32")
    if isinstance(value, dict):
        count = 1 + sum(
            _bounded_shape(key, depth=depth + 1) + _bounded_shape(item, depth=depth + 1)
            for key, item in value.items()
        )
    elif isinstance(value, list):
        count = 1 + sum(_bounded_shape(item, depth=depth + 1) for item in value)
    else:
        count = 1
    if count > MAX_NODES:
        raise ValueError("hook input contains more than 100000 nodes")
    return count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="projectlore-acquisition-hook")
    parser.add_argument("--client", required=True, choices=("claude_code", "codex_cli"))
    parser.add_argument("--root", required=True, type=Path)
    return parser


def run(
    value: dict[str, Any],
    *,
    client: str,
    repository: Path | None = None,
) -> dict[str, Any]:
    """Normalize only lifecycle metadata; raw input is never retained."""

    _bounded_shape(value)
    cwd = value.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("hook field 'cwd' is required")
    event_cwd = Path(cwd).resolve(strict=True)
    root = event_cwd if repository is None else repository.resolve(strict=True)
    if not event_cwd.is_relative_to(root):
        raise ValueError("hook cwd is outside the configured repository")
    event = value.get("hook_event_name") or value.get("event")
    if event == "Stop":
        signal = capture_scan(root)
        return {
            "captured": True,
            "client": client,
            "event": event,
            "signal_id": signal.signal_id,
        }
    if event == "SessionStart":
        recover_commit_claim(root)
        packet = next_packet(root)
        return {
            "captured": False,
            "client": client,
            "event": event,
            "packet_id": None if packet is None else packet.packet_id,
        }
    return {"captured": False, "client": client, "event": event}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return _advise("ProjectLore acquisition hook input exceeds 1 MiB.")
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("hook input must be a JSON object")
        result = run(value, client=args.client, repository=args.root)
    except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as error:
        return _advise(f"ProjectLore acquisition unavailable: {error}")
    print(json.dumps(result, separators=(",", ":")))
    return 0


def _advise(message: str) -> int:
    print(message[:1000], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
