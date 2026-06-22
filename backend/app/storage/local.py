"""Local filesystem storage with generated, traversal-safe keys."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

# Storage refs are server-generated 32-char hex keys — never user input.
_SAFE_REF = re.compile(r"^[0-9a-f]{32}$")


class LocalSourceStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, ref: str) -> Path:
        if not _SAFE_REF.match(ref):
            raise ValueError("invalid storage reference")
        path = (self._root / ref[:2] / ref).resolve()
        # Defence in depth: the resolved path must stay within the root.
        if self._root != path and self._root not in path.parents:
            raise ValueError("storage path escapes root")
        return path

    def put(self, data: bytes) -> str:
        ref = uuid.uuid4().hex
        path = self._path_for(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        return ref

    def open(self, ref: str) -> bytes:
        with open(self._path_for(ref), "rb") as handle:
            return handle.read()

    def delete(self, ref: str) -> None:
        path = self._path_for(ref)
        if path.exists():
            path.unlink()
