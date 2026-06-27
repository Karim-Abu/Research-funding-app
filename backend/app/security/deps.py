"""FastAPI dependencies: session authentication, Origin + CSRF guards, roles."""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import Settings, get_settings
from app.db.models import User, UserSession
from app.db.session import get_db
from app.security.origin import origin_allowed
from app.security.sessions import get_valid_session


@dataclass
class AuthContext:
    user: User
    session: UserSession


def settings_dep() -> Settings:
    return get_settings()


def require_session(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> AuthContext:
    cookie = request.cookies.get(settings.session_cookie_name)
    session = get_valid_session(db, cookie)
    if session is None:
        raise ProblemException(
            status=401,
            code="unauthenticated",
            title="Authentication required",
            detail="A valid session is required.",
        )
    user = db.get(User, session.user_id)
    if user is None:
        raise ProblemException(
            status=401,
            code="unauthenticated",
            title="Authentication required",
            detail="A valid session is required.",
        )
    return AuthContext(user=user, session=session)


def require_origin(
    request: Request, settings: Settings = Depends(settings_dep)
) -> None:
    if not origin_allowed(request.headers.get("origin"), settings.allowed_origins):
        raise ProblemException(
            status=403,
            code="origin_forbidden",
            title="Forbidden",
            detail="Request Origin is not allowed.",
        )


def require_unsafe_guards(
    request: Request,
    context: AuthContext = Depends(require_session),
    settings: Settings = Depends(settings_dep),
) -> AuthContext:
    """Session + Origin + CSRF synchronizer-token check for unsafe methods."""
    if not origin_allowed(request.headers.get("origin"), settings.allowed_origins):
        raise ProblemException(
            status=403,
            code="origin_forbidden",
            title="Forbidden",
            detail="Request Origin is not allowed.",
        )
    token = request.headers.get("x-csrf-token")
    if not token or not secrets.compare_digest(token, context.session.csrf_token):
        raise ProblemException(
            status=403,
            code="csrf_failed",
            title="Forbidden",
            detail="Missing or invalid CSRF token.",
        )
    return context


def require_roles(*roles: str):
    """Role guard — used only where openapi-v1_1.yaml restricts x-required-roles."""

    def _dep(context: AuthContext = Depends(require_session)) -> AuthContext:
        if context.user.role not in roles:
            raise ProblemException(
                status=403,
                code="forbidden_role",
                title="Forbidden",
                detail="Your role is not permitted to perform this action.",
            )
        return context

    return _dep
