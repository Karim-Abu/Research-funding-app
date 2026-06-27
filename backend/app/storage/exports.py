"""Local export-file storage: atomic writes, size cap, content-hash integrity.

Server-generated traversal-safe keys; binaries never in SQLite; files are never
publicly addressable (served only via the authenticated download endpoint).
"""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config.settings import get_settings

_SAFE_REF = re.compile(r"^[0-9a-f]{32}$")


class ExportTooLargeError(Exception):
    """Generated export exceeds the configured size cap."""


class ExportIntegrityError(Exception):
    """Stored bytes do not match the recorded content hash."""


@dataclass(frozen=True)
class StoredExport:
    storage_key: str
    content_hash: str
    size_bytes: int


class LocalExportStorage:
    def __init__(self, root: str, max_bytes: int) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._max_bytes = max_bytes

    def _path_for(self, ref: str) -> Path:
        if not _SAFE_REF.match(ref):
            raise ValueError("invalid storage reference")
        path = (self._root / ref[:2] / ref).resolve()
        if self._root != path and self._root not in path.parents:
            raise ValueError("storage path escapes root")
        return path

    def put(self, data: bytes) -> StoredExport:
        """Atomic write (temp + os.replace). Enforces the size cap; cleans the
        temp file on any failure."""
        if len(data) > self._max_bytes:
            raise ExportTooLargeError(
                f"export of {len(data)} bytes exceeds limit {self._max_bytes}"
            )
        ref = uuid.uuid4().hex
        path = self._path_for(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise
        return StoredExport(
            storage_key=ref,
            content_hash=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
        )

    def open_verified(self, ref: str, *, expected_hash: str) -> bytes:
        """Read bytes and verify the SHA-256 before returning (corr. #6)."""
        with open(self._path_for(ref), "rb") as handle:
            data = handle.read()
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise ExportIntegrityError("stored export hash mismatch")
        return data

    def exists(self, ref: str) -> bool:
        return self._path_for(ref).exists()

    def delete(self, ref: str) -> None:
        path = self._path_for(ref)
        if path.exists():
            path.unlink()
        tmp = path.with_suffix(".tmp")
        if tmp.exists():
            tmp.unlink()

    def known_keys(self) -> set[str]:
        """All persisted final keys (for orphan reconciliation at recovery)."""
        keys: set[str] = set()
        for child in self._root.glob("*/*"):
            if child.is_file() and _SAFE_REF.match(child.name):
                keys.add(child.name)
        return keys

    def purge_orphans(self, keep: set[str]) -> int:
        """Remove final/temp files not referenced by a live artifact."""
        removed = 0
        for child in self._root.glob("*/*"):
            if not child.is_file():
                continue
            name = child.name
            if name.endswith(".tmp") or (
                _SAFE_REF.match(name) and name not in keep
            ):
                child.unlink()
                removed += 1
        return removed


@lru_cache
def get_export_storage() -> LocalExportStorage:
    settings = get_settings()
    return LocalExportStorage(settings.export_storage_dir, settings.max_export_bytes)
