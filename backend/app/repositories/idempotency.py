"""Persistent idempotency records for mutating, key-bearing requests."""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IdempotencyRecord


def fingerprint(method: str, path: str, body: str) -> str:
    return hashlib.sha256(f"{method}\n{path}\n{body}".encode()).hexdigest()


def get(db: Session, scope: str, key: str) -> IdempotencyRecord | None:
    return db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
    )


def save(
    db: Session,
    *,
    scope: str,
    key: str,
    request_fingerprint: str,
    response_status: int,
    response_body: dict,
    resource_id: str | None,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        id=str(uuid.uuid4()),
        scope=scope,
        idempotency_key=key,
        request_fingerprint=request_fingerprint,
        response_status=response_status,
        response_body=response_body,
        resource_id=resource_id,
    )
    db.add(record)
    db.flush()
    return record
