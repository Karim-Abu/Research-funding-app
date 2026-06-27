"""Idempotent seed: demo workspace, funding profile, pre-provisioned users.

No self-sign-up exists; these are the only login identities. Passwords come
from settings/env (dev defaults documented in the README).

Run from the backend/ directory:  python -m app.seed
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.db.models import FundingProfile, User, Workspace
from app.db.session import SessionLocal
from app.repositories import users as users_repo
from app.security.passwords import hash_password

logger = logging.getLogger("app.seed")


def _ensure_workspace(db: Session, settings) -> None:
    if db.get(Workspace, settings.seed_workspace_id) is None:
        db.add(
            Workspace(
                id=settings.seed_workspace_id, name=settings.seed_workspace_name
            )
        )


def _ensure_funding_profile(db: Session, settings) -> None:
    if db.get(FundingProfile, settings.seed_funding_profile_id) is None:
        db.add(
            FundingProfile(
                id=settings.seed_funding_profile_id,
                title=settings.seed_funding_profile_title,
            )
        )


def _ensure_user(
    db: Session, *, user_id: str, workspace_id: str, name: str, email: str,
    role: str, password: str,
) -> None:
    if users_repo.get_by_email(db, email) is not None:
        return
    db.add(
        User(
            id=user_id,
            workspace_id=workspace_id,
            name=name,
            email=email.lower(),
            password_hash=hash_password(password),
            role=role,
            display_label=name,
        )
    )


def seed() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        _ensure_workspace(db, settings)
        _ensure_funding_profile(db, settings)
        _ensure_user(
            db,
            user_id="user-anna",
            workspace_id=settings.seed_workspace_id,
            name=settings.seed_lead_admin_name,
            email=settings.seed_lead_admin_email,
            role="lead_admin",
            password=settings.seed_lead_admin_password,
        )
        _ensure_user(
            db,
            user_id="user-tobias",
            workspace_id=settings.seed_workspace_id,
            name=settings.seed_member_name,
            email=settings.seed_member_email,
            role="member",
            password=settings.seed_member_password,
        )
        db.commit()
        logger.info("seed complete workspace=%s", settings.seed_workspace_id)
    finally:
        db.close()


if __name__ == "__main__":
    configure_logging(get_settings().log_level)
    seed()
