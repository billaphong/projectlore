"""Root-confined immutable object storage and atomic workflow activation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from projectlore.acquisition.digest import canonical_json, content_digest
from projectlore.acquisition.models import Generation, GenerationState, KnowledgeRoot

ModelT = TypeVar("ModelT", bound=BaseModel)
ZERO_DIGEST = "sha256:" + ("0" * 64)
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
OBJECT_IDENTITIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "projectlore-knowledge-signal/0.6.1": (
        "projectlore:knowledge-signal:0.6.1",
        ("signal_id",),
    ),
    "projectlore-knowledge-packet/0.6.1": (
        "projectlore:knowledge-packet:0.6.1",
        ("packet_id",),
    ),
    "projectlore-knowledge-proposal/0.6.1": (
        "projectlore:knowledge-proposal:0.6.1",
        ("proposal_id",),
    ),
    "projectlore-knowledge-review/0.6.1": (
        "projectlore:knowledge-review:0.6.1",
        ("review_id", "decided_at"),
    ),
    "projectlore-knowledge-receipt/0.6.1": (
        "projectlore:knowledge-receipt:0.6.1",
        ("receipt_id", "created_at"),
    ),
}


class ImmutableObjectConflict(RuntimeError):
    """An object identity already exists with different bytes."""


class CorruptStore(RuntimeError):
    """Persisted acquisition state violates its content identity."""


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _flush_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _flush_directory(path: Path) -> None:
    """Best-effort parent-directory durability on platforms that support it."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


class KnowledgeStore:
    """Manage disposable acquisition workflow state below `.projectlore/`."""

    ROOT_DOMAIN = "projectlore:knowledge-root:0.6.1"
    GENERATION_DOMAIN = "projectlore:knowledge-generation:0.6.1"

    def __init__(self, repository: Path) -> None:
        self.repository = repository.resolve(strict=True)
        self.directory = self.repository / ".projectlore" / "knowledge"
        self.objects = self.directory / "objects"
        self.generations = self.directory / "generations"
        self.active_root = self.directory / "root.json"
        self._assert_storage_path()

    def _assert_storage_path(self) -> None:
        current = self.repository
        for part in (".projectlore", "knowledge"):
            current /= part
            if not current.exists():
                continue
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            if current.is_symlink() or attributes & 0x400:
                raise CorruptStore(
                    "acquisition storage ancestor is a symlink or reparse point: "
                    f"{current}"
                )

    def _assert_confined_path(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.repository)
        except ValueError as error:
            raise CorruptStore("acquisition path escapes repository") from error
        current = self.repository
        for part in relative.parts:
            current /= part
            if not current.exists():
                continue
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            if current.is_symlink() or attributes & 0x400:
                raise CorruptStore(
                    f"acquisition path contains a symlink or reparse point: {current}"
                )

    def initialize(self) -> Generation:
        """Create and activate the deterministic empty generation if absent."""

        self._assert_storage_path()
        if self.active_root.exists():
            return self.current_generation()
        provisional_root = {
            "contract_version": "projectlore-knowledge-root/0.6.1",
            "generation_id": ZERO_DIGEST,
            "members": [],
        }
        root_digest = content_digest(
            self.ROOT_DOMAIN, provisional_root, exclude=("generation_id",)
        )
        provisional_generation = {
            "contract_version": "projectlore-knowledge-generation/0.6.1",
            "sequence": 0,
            "state": "pending",
            "root_digest": root_digest,
        }
        generation_id = content_digest(self.GENERATION_DOMAIN, provisional_generation)
        root = KnowledgeRoot(
            root_digest=root_digest,
            generation_id=generation_id,
            members=(),
        )
        generation = Generation(
            generation_id=generation_id,
            sequence=0,
            state=GenerationState.PENDING,
            root_digest=root_digest,
        )
        self._write_generation(generation, root)
        self.activate(generation.generation_id)
        return generation

    def put_object(
        self, domain: str, value: dict[str, Any], *, exclude: tuple[str, ...] = ()
    ) -> str:
        self._assert_storage_path()
        digest = content_digest(domain, value, exclude=exclude)
        path = (
            self.objects
            / digest.removeprefix("sha256:")[:2]
            / f"{digest.removeprefix('sha256:')}.json"
        )
        self._assert_confined_path(path)
        data = canonical_json(value) + b"\n"
        if path.exists():
            if path.read_bytes() != data:
                raise ImmutableObjectConflict(digest)
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if path.read_bytes() != data:
                raise ImmutableObjectConflict(digest) from None
        return digest

    def get_object(self, digest: str) -> dict[str, Any]:
        self._assert_storage_path()
        self._validate_digest(digest)
        hexadecimal = digest.removeprefix("sha256:")
        path = self.objects / hexadecimal[:2] / f"{hexadecimal}.json"
        self._assert_confined_path(path)
        try:
            value = json.loads(path.read_bytes())
        except (OSError, ValueError) as error:
            raise CorruptStore(f"invalid immutable object {digest}: {error}") from error
        if not isinstance(value, dict):
            raise CorruptStore(f"immutable object {digest} is not an object")
        identity = OBJECT_IDENTITIES.get(str(value.get("contract_version")))
        if value.get("contract_version") is not None and identity is None:
            raise CorruptStore(
                f"unknown immutable object contract: {value.get('contract_version')}"
            )
        if identity is not None:
            domain, exclude = identity
            if content_digest(domain, value, exclude=exclude) != digest:
                raise CorruptStore(f"immutable object digest mismatch: {digest}")
        return value

    def has_object(self, digest: str) -> bool:
        self._validate_digest(digest)
        hexadecimal = digest.removeprefix("sha256:")
        path = self.objects / hexadecimal[:2] / f"{hexadecimal}.json"
        self._assert_confined_path(path)
        return path.is_file()

    def put_blob(self, value: bytes) -> str:
        self._assert_storage_path()
        digest = f"sha256:{hashlib.sha256(value).hexdigest()}"
        hexadecimal = digest.removeprefix("sha256:")
        path = self.directory / "blobs" / hexadecimal[:2] / hexadecimal
        self._assert_confined_path(path)
        if path.exists():
            if path.read_bytes() != value:
                raise ImmutableObjectConflict(digest)
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if path.read_bytes() != value:
                raise ImmutableObjectConflict(digest) from None
        return digest

    def get_blob(self, digest: str) -> bytes:
        self._assert_storage_path()
        self._validate_digest(digest)
        hexadecimal = digest.removeprefix("sha256:")
        path = self.directory / "blobs" / hexadecimal[:2] / hexadecimal
        self._assert_confined_path(path)
        try:
            value = path.read_bytes()
        except OSError as error:
            raise CorruptStore(f"missing immutable blob {digest}") from error
        actual = f"sha256:{hashlib.sha256(value).hexdigest()}"
        if actual != digest:
            raise CorruptStore(f"immutable blob digest mismatch: {digest}")
        return value

    @staticmethod
    def _validate_digest(digest: str) -> None:
        if DIGEST_PATTERN.fullmatch(digest) is None:
            raise CorruptStore("invalid acquisition object digest")

    def stage(
        self, members: tuple[str, ...], state: GenerationState = GenerationState.PENDING
    ) -> Generation:
        self._assert_storage_path()
        return self.stage_after(self.current_generation(), members, state)

    def stage_after(
        self,
        predecessor: Generation,
        members: tuple[str, ...],
        state: GenerationState = GenerationState.PENDING,
    ) -> Generation:
        """Stage after a verified predecessor, including during root recovery."""

        ordered = tuple(sorted(set(members)))
        root_payload: dict[str, Any] = {
            "contract_version": "projectlore-knowledge-root/0.6.1",
            "generation_id": ZERO_DIGEST,
            "members": list(ordered),
        }
        root_digest = content_digest(
            self.ROOT_DOMAIN, root_payload, exclude=("generation_id",)
        )
        generation_payload: dict[str, Any] = {
            "contract_version": "projectlore-knowledge-generation/0.6.1",
            "sequence": predecessor.sequence + 1,
            "state": state.value,
            "root_digest": root_digest,
        }
        generation_id = content_digest(self.GENERATION_DOMAIN, generation_payload)
        root = KnowledgeRoot(
            root_digest=root_digest, generation_id=generation_id, members=ordered
        )
        generation = Generation(
            generation_id=generation_id,
            sequence=predecessor.sequence + 1,
            state=state,
            root_digest=root_digest,
        )
        self._write_generation(generation, root)
        return generation

    def activate(self, generation_id: str) -> None:
        self._assert_storage_path()
        generation = self._read_verified_generation(generation_id)
        root = self._read_model(self._root_path(generation_id), KnowledgeRoot)
        if (
            generation.root_digest != root.root_digest
            or root.generation_id != generation_id
        ):
            raise CorruptStore("generation and root digests disagree")
        _atomic_write(
            self.active_root, canonical_json(root.model_dump(mode="json")) + b"\n"
        )

    def write_lifecycle_receipt(self, receipt_id: str, value: dict[str, Any]) -> Path:
        """Persist a digest-identified lifecycle receipt outside the active root."""

        self._validate_digest(receipt_id)
        path = self.directory / "receipts" / f"{receipt_id[7:]}.json"
        self._assert_confined_path(path)
        data = canonical_json(value) + b"\n"
        if path.exists() and path.read_bytes() != data:
            raise ImmutableObjectConflict(receipt_id)
        if not path.exists():
            _atomic_write(path, data)
        return path

    def current_root(self) -> KnowledgeRoot:
        self._assert_storage_path()
        if not self.active_root.exists():
            self.initialize()
        root = self._read_model(self.active_root, KnowledgeRoot)
        expected = content_digest(
            self.ROOT_DOMAIN,
            root.model_dump(mode="json"),
            exclude=("root_digest", "generation_id"),
        )
        if expected != root.root_digest:
            raise CorruptStore("active root digest is invalid")
        return root

    def current_generation(self) -> Generation:
        root = self.current_root()
        generation = self._read_verified_generation(root.generation_id)
        if generation.root_digest != root.root_digest:
            raise CorruptStore("active generation does not match active root")
        return generation

    def recover(self) -> Generation:
        """Validate the atomic active pointer; staged generations remain inert."""

        return self.current_generation()

    def valid_generations(self) -> tuple[Generation, ...]:
        """Return fully validated staged generations without selecting one."""

        if not self.generations.is_dir() or self.generations.is_symlink():
            return ()
        valid: list[Generation] = []
        for directory in self.generations.iterdir():
            if not directory.is_dir() or directory.is_symlink():
                continue
            try:
                generation = self._read_model(directory / "generation.json", Generation)
                root = self._read_model(directory / "root.json", KnowledgeRoot)
                if generation.generation_id != f"sha256:{directory.name}":
                    continue
                if generation.root_digest != root.root_digest:
                    continue
                expected_root = content_digest(
                    self.ROOT_DOMAIN,
                    root.model_dump(mode="json"),
                    exclude=("root_digest", "generation_id"),
                )
                if expected_root != root.root_digest:
                    continue
                expected_generation = content_digest(
                    self.GENERATION_DOMAIN,
                    generation.model_dump(mode="json"),
                    exclude=("generation_id",),
                )
                if expected_generation != generation.generation_id:
                    continue
            except CorruptStore:
                continue
            valid.append(generation)
        return tuple(
            sorted(valid, key=lambda item: (item.sequence, item.generation_id))
        )

    def root_for_generation(self, generation_id: str) -> KnowledgeRoot:
        self._validate_digest(generation_id)
        generation = self._read_verified_generation(generation_id)
        root = self._read_model(self._root_path(generation_id), KnowledgeRoot)
        expected = content_digest(
            self.ROOT_DOMAIN,
            root.model_dump(mode="json"),
            exclude=("root_digest", "generation_id"),
        )
        if (
            root.generation_id != generation_id
            or root.root_digest != generation.root_digest
            or root.root_digest != expected
        ):
            raise CorruptStore("generation root identity is invalid")
        return root

    def _read_verified_generation(self, generation_id: str) -> Generation:
        self._validate_digest(generation_id)
        generation = self._read_model(self._generation_path(generation_id), Generation)
        expected = content_digest(
            self.GENERATION_DOMAIN,
            generation.model_dump(mode="json"),
            exclude=("generation_id",),
        )
        if generation.generation_id != generation_id or expected != generation_id:
            raise CorruptStore("generation identity is invalid")
        return generation

    def _write_generation(self, generation: Generation, root: KnowledgeRoot) -> None:
        directory = self.generations / generation.generation_id.removeprefix("sha256:")
        self._assert_confined_path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for path, model in (
            (directory / "generation.json", generation),
            (directory / "root.json", root),
        ):
            data = canonical_json(model.model_dump(mode="json")) + b"\n"
            if path.exists() and path.read_bytes() != data:
                raise ImmutableObjectConflict(str(path))
            if not path.exists():
                _atomic_write(path, data)

    def _generation_path(self, generation_id: str) -> Path:
        self._validate_digest(generation_id)
        path = (
            self.generations / generation_id.removeprefix("sha256:") / "generation.json"
        )
        self._assert_confined_path(path)
        return path

    def _root_path(self, generation_id: str) -> Path:
        self._validate_digest(generation_id)
        path = self.generations / generation_id.removeprefix("sha256:") / "root.json"
        self._assert_confined_path(path)
        return path

    @staticmethod
    def _read_model(path: Path, model: type[ModelT]) -> ModelT:
        try:
            value = json.loads(path.read_bytes())
            return model.model_validate(value)
        except (OSError, ValueError) as error:
            raise CorruptStore(
                f"invalid acquisition state at {path}: {error}"
            ) from error
