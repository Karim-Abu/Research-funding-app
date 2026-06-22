"""Pluggable source binary storage (local now; Azure Blob later)."""
from __future__ import annotations

from functools import lru_cache

from app.config.settings import get_settings
from app.storage.base import SourceStorage
from app.storage.local import LocalSourceStorage


@lru_cache
def get_storage() -> SourceStorage:
    return LocalSourceStorage(get_settings().source_storage_dir)


__all__ = ["SourceStorage", "LocalSourceStorage", "get_storage"]
