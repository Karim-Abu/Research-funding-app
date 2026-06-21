"""User lookups + ORM→contract mapping."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.auth import User as UserSchema
from app.db.models import User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def to_contract(user: User) -> UserSchema:
    return UserSchema(
        user_id=user.id,
        name=user.name,
        email=user.email,
        effective_role=user.role,
        display_label=user.display_label,
    )
