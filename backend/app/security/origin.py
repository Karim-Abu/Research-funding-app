"""Origin header validation for unsafe methods (defence in depth with CSRF)."""
from __future__ import annotations


def origin_allowed(origin: str | None, allowed_origins: list[str]) -> bool:
    # Unsafe requests must carry an Origin that is on the allow-list.
    if not origin:
        return False
    return origin in allowed_origins
