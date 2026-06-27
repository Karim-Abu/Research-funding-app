"""Storage protocol — original binaries live outside the database."""
from __future__ import annotations

from typing import Protocol


class SourceStorage(Protocol):
    def put(self, data: bytes) -> str:
        """Persist bytes under a freshly generated safe key; return the ref."""
        ...

    def open(self, ref: str) -> bytes:
        ...

    def delete(self, ref: str) -> None:
        ...
