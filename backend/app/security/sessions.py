"""Server-side session lifecycle (cryptographically random ids + CSRF token)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import User, UserSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_session(db: Session, user: User, ttl_seconds: int) -> UserSession:
    session = UserSession(
        id=secrets.token_urlsafe(32),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=_now() + timedelta(seconds=ttl_seconds),
    )
    db.add(session)
    db.flush()
    return session


def get_valid_session(db: Session, session_id: str | None) -> UserSession | None:
    if not session_id:
        return None
    session = db.get(UserSession, session_id)
    if session is None or session.revoked_at is not None:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= _now():
        return None
    return session


def revoke_session(db: Session, session: UserSession) -> None:
    session.revoked_at = _now()
    db.add(session)
    db.flush()
