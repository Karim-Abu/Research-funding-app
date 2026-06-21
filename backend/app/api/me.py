"""Current-user router — GET /me."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.contracts.auth import User
from app.repositories import users
from app.security.deps import AuthContext, require_session

router = APIRouter(tags=["Auth"])


@router.get("/me", response_model=User)
def get_current_user(context: AuthContext = Depends(require_session)) -> User:
    return users.to_contract(context.user)
