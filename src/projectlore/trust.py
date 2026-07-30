"""Local, reviewable receipts for client-owned project trust."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from projectlore.models import StrictModel

ClientName = Literal["claude_code", "codex_cli"]
RECEIPT_VERSION: Literal["projectlore-client-trust/0.1.0"] = (
    "projectlore-client-trust/0.1.0"
)


class ClientTrustReceipt(StrictModel):
    receipt_version: Literal["projectlore-client-trust/0.1.0"]
    client: ClientName
    client_version: str = Field(min_length=1)
    reviewed_at: datetime
    config_digests: dict[str, str]
    claim: Literal["user_reviewed_client_project_configuration"]


def config_paths(root: Path, client: ClientName) -> list[Path]:
    if client == "claude_code":
        return [
            root / ".mcp.json",
            root / ".claude" / "settings.json",
            root / "CLAUDE.md",
        ]
    return [
        root / ".codex" / "config.toml",
        root / ".codex" / "hooks.json",
        root / "AGENTS.md",
    ]


def issue_receipt(
    root: Path,
    client: ClientName,
    client_version: str,
) -> ClientTrustReceipt:
    digests = {
        path.relative_to(root).as_posix(): _file_digest(path)
        for path in config_paths(root, client)
    }
    return ClientTrustReceipt(
        receipt_version=RECEIPT_VERSION,
        client=client,
        client_version=client_version,
        reviewed_at=datetime.now(UTC),
        config_digests=digests,
        claim="user_reviewed_client_project_configuration",
    )


def write_receipt(root: Path, receipt: ClientTrustReceipt) -> Path:
    directory = root / ".projectlore" / "trust"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{receipt.client}.json"
    path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return path


def verify_receipt(
    root: Path,
    client: ClientName,
    client_version: str | None,
) -> dict[str, object]:
    path = root / ".projectlore" / "trust" / f"{client}.json"
    try:
        receipt = ClientTrustReceipt.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {"verified": False, "state": "missing_or_invalid", "path": str(path)}
    current = {
        item.relative_to(root).as_posix(): _file_digest(item)
        for item in config_paths(root, client)
    }
    if receipt.client_version != client_version:
        return {"verified": False, "state": "client_version_drift", "path": str(path)}
    if receipt.config_digests != current:
        return {"verified": False, "state": "configuration_drift", "path": str(path)}
    return {
        "verified": True,
        "state": "reviewed_current",
        "path": str(path),
        "reviewed_at": receipt.reviewed_at.isoformat(),
    }


def _file_digest(path: Path) -> str:
    content = path.read_bytes()
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
