"""Transaction boundary for acquisition workflow generations."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType

from projectlore.acquisition.models import Generation, GenerationState
from projectlore.acquisition.store import KnowledgeStore


class LockTimeout(TimeoutError):
    """A repository transaction lock could not be acquired in time."""


class FileLock:
    """Small cross-process exclusive lock with explicit ownership bytes."""

    def __init__(self, path: Path, *, timeout: float = 5.0) -> None:
        self.path = path
        self.timeout = timeout
        self._held = False

    def __enter__(self) -> FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        payload = f"pid={os.getpid()}\n".encode()
        while True:
            try:
                descriptor = os.open(
                    self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                )
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._held = True
                return self
            except FileExistsError:
                if self._reclaim_stale_lock():
                    continue
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"timed out acquiring {self.path}") from None
                time.sleep(0.01)

    def _reclaim_stale_lock(self) -> bool:
        """Remove an exact, well-formed lock only when its owner is gone."""

        if self.path.is_symlink():
            return False
        try:
            payload = self.path.read_bytes()
            text = payload.decode("ascii")
            if not text.startswith("pid=") or not text.endswith("\n"):
                return False
            pid = int(text[4:-1])
            if pid <= 0:
                return False
            try:
                if _process_is_alive(pid):
                    return False
            except PermissionError:
                return False
            if self.path.is_symlink() or self.path.read_bytes() != payload:
                return False
            self.path.unlink()
            return True
        except (OSError, UnicodeError, ValueError):
            return False

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._held:
            self.path.unlink(missing_ok=True)
            self._held = False


def _process_is_alive(pid: int) -> bool:
    """Check liveness without using os.kill(pid, 0), which terminates on Windows."""

    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # access denied means it exists
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False


class WorkflowTransaction:
    """Stage one immutable generation and activate it exactly once."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    def commit(
        self,
        members: Iterable[str],
        *,
        state: GenerationState = GenerationState.PENDING,
    ) -> Generation:
        lock = self.store.directory / "locks" / "workflow.lock"
        with FileLock(lock):
            current = self.store.current_root()
            generation = self.store.stage((*current.members, *tuple(members)), state)
            self.store.activate(generation.generation_id)
            return generation


class CanonicalWorkflowTransaction:
    """Hold canonical then workflow locks continuously across an apply."""

    def __init__(self, store: KnowledgeStore, *, timeout: float = 5.0) -> None:
        locks = store.directory / "locks"
        self._canonical = FileLock(locks / "canonical.lock", timeout=timeout)
        self._workflow = FileLock(locks / "workflow.lock", timeout=timeout)

    def __enter__(self) -> CanonicalWorkflowTransaction:
        self._canonical.__enter__()
        try:
            self._workflow.__enter__()
        except BaseException:
            self._canonical.__exit__(None, None, None)
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._workflow.__exit__(exc_type, exc_value, traceback)
        self._canonical.__exit__(exc_type, exc_value, traceback)
