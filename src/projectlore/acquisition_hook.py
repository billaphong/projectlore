"""Privacy-safe lifecycle hook for passive knowledge acquisition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from projectlore.acquisition.passive import capture_hook_event, next_packet
from projectlore.acquisition.review import recover_commit_claim
from projectlore.acquisition.transactions import LockTimeout

MAX_INPUT_BYTES = 1_048_576
MAX_DEPTH = 32
MAX_NODES = 100_000
# Clients allow three seconds and the acquisition contract reserves one second of
# margin around its two-second hook boundary.  At most two sequential lock waits
# occur, so 250 ms per wait leaves at least 1.5 seconds for startup and model I/O.
HOOK_LOCK_TIMEOUT_SECONDS = 0.25


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
        session_id = value.get("session_id")
        if not isinstance(session_id, str):
            raise ValueError("hook field 'session_id' is required")
        signal = capture_hook_event(
            root,
            client=client,
            session_id=session_id,
            lock_timeout=HOOK_LOCK_TIMEOUT_SECONDS,
        )
        return {
            "captured": True,
            "client": client,
            "event": event,
            "signal_id": signal.signal_id,
        }
    if event == "SessionStart":
        recover_commit_claim(root, lock_timeout=HOOK_LOCK_TIMEOUT_SECONDS)
        packet = next_packet(root, lock_timeout=HOOK_LOCK_TIMEOUT_SECONDS)
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
        return _advise(
            "ProjectLore acquisition hook input exceeds 1 MiB.", client=args.client
        )
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("hook input must be a JSON object")
        result = run(value, client=args.client, repository=args.root)
    except LockTimeout as error:
        return _advise(
            "PLKA3003: ProjectLore acquisition deferred because knowledge state "
            f"is busy: {error}",
            client=args.client,
        )
    except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as error:
        return _advise(
            f"ProjectLore acquisition unavailable: {error}", client=args.client
        )
    print(
        json.dumps(
            {"continue": True} if args.client == "codex_cli" else result,
            separators=(",", ":"),
        )
    )
    return 0


def _advise(message: str, *, client: str) -> int:
    print(message[:1000], file=sys.stderr)
    if client == "codex_cli":
        print('{"continue":true}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
