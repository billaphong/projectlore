"""Bounded execution for locally trusted deterministic checkers."""

from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from projectlore.models import StrictModel

MAX_CHECKER_OUTPUT_BYTES = 64 * 1024
SAFE_ENVIRONMENT_KEYS = frozenset({"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR"})
SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*([^\s,;]+)"
)


class CheckerPolicyError(ValueError):
    """Raised when a checker request crosses a trusted policy boundary."""


class TrustedChecker(StrictModel):
    """Operator-authored executable policy stored outside the knowledge model."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    argv: tuple[str, ...] = Field(min_length=1, max_length=32)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pinned_files: dict[str, str] = Field(default_factory=dict)
    working_directory: str = "."
    timeout_seconds: int = Field(default=3, ge=1, le=60)
    maximum_output_bytes: int = Field(
        default=MAX_CHECKER_OUTPUT_BYTES, ge=1, le=MAX_CHECKER_OUTPUT_BYTES
    )
    network: Literal["deny"] = "deny"


class CheckerRegistry:
    """An immutable, local trust registry; never populated from model content."""

    def __init__(self, checkers: Sequence[TrustedChecker]) -> None:
        entries = {checker.name: checker for checker in checkers}
        if len(entries) != len(checkers):
            raise CheckerPolicyError("Trusted checker names must be unique.")
        self._entries = entries

    def resolve(self, requested_name: str) -> TrustedChecker:
        try:
            return self._entries[requested_name]
        except KeyError as error:
            raise CheckerPolicyError(
                f"Checker {requested_name!r} is not locally trusted."
            ) from error


class CheckerExecution(StrictModel):
    execution_version: Literal["projectlore-checker-execution/0.1.0"]
    checker: str
    decision: Literal["pass", "fail", "indeterminate"]
    reason_code: str
    exit_code: int | None
    stdout: str
    stderr: str
    output_truncated: bool
    network: Literal["deny"]
    network_enforcement: Literal["not_run", "os_sandbox"]
    sandbox_backend: str | None
    argv_digest: str


class NetworkSandbox(Protocol):
    """Trusted runtime adapter that enforces a deny-network process boundary."""

    @property
    def backend_name(self) -> str: ...

    def wrap(
        self,
        argv: tuple[str, ...],
        *,
        project_root: Path,
        working_directory: Path,
    ) -> tuple[str, ...]: ...


class BubblewrapSandbox:
    """Linux network namespace and read-only project mount via bubblewrap."""

    def __init__(self, executable: Path, executable_sha256: str) -> None:
        resolved = executable.resolve(strict=True)
        if _sha256(resolved) != executable_sha256:
            raise CheckerPolicyError("Bubblewrap executable digest does not match.")
        self._executable = resolved

    @property
    def backend_name(self) -> str:
        return "bubblewrap-unshare-net"

    def wrap(
        self,
        argv: tuple[str, ...],
        *,
        project_root: Path,
        working_directory: Path,
    ) -> tuple[str, ...]:
        return (
            str(self._executable),
            "--unshare-net",
            "--die-with-parent",
            "--new-session",
            "--ro-bind",
            str(project_root),
            str(project_root),
            "--chdir",
            str(working_directory),
            "--",
            *argv,
        )


@dataclass(frozen=True)
class ContextEvidence:
    """Untrusted context safe for display, never execution."""

    source_kind: Literal["model", "fraimed", "documentation", "code"]
    text: str
    trust: Literal["untrusted_data"] = "untrusted_data"


def redact_context(
    source_kind: Literal["model", "fraimed", "documentation", "code"],
    text: str,
) -> ContextEvidence:
    """Redact common inline credentials while preserving untrusted-data status."""

    redacted = SECRET_PATTERN.sub(lambda match: match.group(0).replace(
        match.group(1), "[REDACTED]"
    ), text)
    return ContextEvidence(source_kind=source_kind, text=redacted)


def run_checker(
    registry: CheckerRegistry,
    requested_name: str,
    *,
    project_root: Path,
    environment: Mapping[str, str] | None = None,
    sandbox: NetworkSandbox | None = None,
) -> CheckerExecution:
    """Run one fixed trusted command without a shell or model-controlled arguments."""

    checker = registry.resolve(requested_name)
    root = project_root.resolve(strict=True)
    cwd = _confined_path(root, checker.working_directory)
    executable = _resolve_executable(checker.argv[0], cwd)
    if _sha256(executable) != checker.executable_sha256:
        raise CheckerPolicyError("Trusted checker executable digest does not match.")
    for relative, expected_digest in checker.pinned_files.items():
        dependency = _confined_path(root, relative)
        if _sha256(dependency) != expected_digest:
            raise CheckerPolicyError(
                f"Trusted checker dependency digest does not match: {relative}"
            )

    checker_argv = (str(executable), *checker.argv[1:])
    if sandbox is None:
        return _not_run(checker, checker_argv, "network_isolation_unavailable")
    argv = sandbox.wrap(
        checker_argv,
        project_root=root,
        working_directory=cwd,
    )
    if not argv:
        raise CheckerPolicyError("Network sandbox returned an empty argv.")
    env = _safe_environment(environment)
    creationflags = 0
    start_new_session = os.name != "nt"
    if os.name == "nt":
        creationflags = int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    process = subprocess.Popen(  # noqa: S603 - argv is operator-authored and pinned
        argv,
        cwd=cwd,
        env=env,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        start_new_session=start_new_session,
        creationflags=creationflags,
    )
    try:
        stdout_bytes, stderr_bytes = process.communicate(
            timeout=checker.timeout_seconds
        )
    except subprocess.TimeoutExpired:
        _terminate_tree(process)
        stdout_bytes, stderr_bytes = process.communicate()
        return _execution(
            checker, argv, "indeterminate", "timeout", None,
            sandbox.backend_name,
            stdout_bytes, stderr_bytes
        )
    decision: Literal["pass", "fail"] = (
        "pass" if process.returncode == 0 else "fail"
    )
    return _execution(
        checker,
        argv,
        decision,
        "completed" if decision == "pass" else "nonzero_exit",
        process.returncode,
        sandbox.backend_name,
        stdout_bytes,
        stderr_bytes,
    )


def _confined_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve(strict=True)
    if not candidate.is_relative_to(root):
        raise CheckerPolicyError("Checker working directory escapes project root.")
    return candidate


def _resolve_executable(command: str, cwd: Path) -> Path:
    candidate = Path(command)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    resolved = candidate.resolve(strict=True)
    if not resolved.is_file():
        raise CheckerPolicyError("Checker executable must be a regular file.")
    return resolved


def _safe_environment(environment: Mapping[str, str] | None) -> dict[str, str]:
    source = os.environ if environment is None else environment
    safe = {
        key: value
        for key, value in source.items()
        if key.upper() in SAFE_ENVIRONMENT_KEYS
    }
    safe["PROJECTLORE_NETWORK"] = "deny"
    return safe


def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(  # noqa: S603, S607 - fixed OS command, no shell
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
    else:
        killpg = getattr(os, "killpg")  # noqa: B009 - absent from Windows typing
        sigkill = getattr(  # noqa: B009 - absent from Windows typing
            signal, "SIGKILL"
        )
        killpg(process.pid, sigkill)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _execution(
    checker: TrustedChecker,
    argv: tuple[str, ...],
    decision: Literal["pass", "fail", "indeterminate"],
    reason_code: str,
    exit_code: int | None,
    sandbox_backend: str,
    stdout: bytes,
    stderr: bytes,
) -> CheckerExecution:
    stdout_text, stdout_cut = _bounded(stdout, checker.maximum_output_bytes)
    stderr_text, stderr_cut = _bounded(stderr, checker.maximum_output_bytes)
    digest = hashlib.sha256("\0".join(argv).encode()).hexdigest()
    return CheckerExecution(
        execution_version="projectlore-checker-execution/0.1.0",
        checker=checker.name,
        decision=decision,
        reason_code=reason_code,
        exit_code=exit_code,
        stdout=stdout_text,
        stderr=stderr_text,
        output_truncated=stdout_cut or stderr_cut,
        network=checker.network,
        network_enforcement="os_sandbox",
        sandbox_backend=sandbox_backend,
        argv_digest=f"sha256:{digest}",
    )


def _not_run(
    checker: TrustedChecker,
    argv: tuple[str, ...],
    reason_code: str,
) -> CheckerExecution:
    digest = hashlib.sha256("\0".join(argv).encode()).hexdigest()
    return CheckerExecution(
        execution_version="projectlore-checker-execution/0.1.0",
        checker=checker.name,
        decision="indeterminate",
        reason_code=reason_code,
        exit_code=None,
        stdout="",
        stderr="",
        output_truncated=False,
        network=checker.network,
        network_enforcement="not_run",
        sandbox_backend=None,
        argv_digest=f"sha256:{digest}",
    )


def _bounded(value: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(value) > limit
    return value[:limit].decode("utf-8", errors="replace"), truncated


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
