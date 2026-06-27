"""Auth router — POST/GET/DELETE /session."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import Settings
from app.contracts.auth import LoginRequest, SessionResponse
from app.db.session import get_db
from app.repositories import audit, users
from app.security.deps import AuthContext, require_session, require_unsafe_guards, settings_dep
from app.security.passwords import verify_password
from app.security.sessions import create_session, revoke_session

router = APIRouter(tags=["Auth"])


def _set_session_cookie(
    response: Response, settings: Settings, session_id: str
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )


@router.post("/session", response_model=SessionResponse)
def create_session_endpoint(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> SessionResponse:
    user = users.get_by_email(db, payload.email)
    if user is None or not verify_password(user.password_hash, payload.password):
        raise ProblemException(
            status=401,
            code="invalid_credentials",
            title="Invalid credentials",
            detail="Email or password is incorrect.",
        )
    session = create_session(db, user, settings.session_ttl_seconds)
    audit.record(
        db,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="session.create",
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    _set_session_cookie(response, settings, session.id)
    return SessionResponse(user=users.to_contract(user), csrf_token=session.csrf_token)


@router.get("/session", response_model=SessionResponse)
def get_session_endpoint(
    context: AuthContext = Depends(require_session),
) -> SessionResponse:
    return SessionResponse(
        user=users.to_contract(context.user),
        csrf_token=context.session.csrf_token,
    )


@router.delete("/session", status_code=204)
def delete_session_endpoint(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    context: AuthContext = Depends(require_unsafe_guards),
) -> Response:
    revoke_session(db, context.session)
    audit.record(
        db,
        workspace_id=context.user.workspace_id,
        actor_user_id=context.user.id,
        action="session.delete",
        target_type="user",
        target_id=context.user.id,
    )
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
