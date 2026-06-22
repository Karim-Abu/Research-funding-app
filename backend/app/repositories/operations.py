"""AsyncOperation persistence + ORM→contract mapping."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.contracts.problem import Problem
from app.contracts.run import AsyncOperation as AsyncOperationSchema
from app.db.models import AsyncOperation


def get_scoped(
    db: Session, operation_id: str, workspace_id: str
) -> AsyncOperation | None:
    operation = db.get(AsyncOperation, operation_id)
    if operation is None or operation.workspace_id != workspace_id:
        return None
    return operation


def to_contract(operation: AsyncOperation) -> AsyncOperationSchema:
    error = Problem(**operation.error) if operation.error else None
    return AsyncOperationSchema(
        operation_id=operation.operation_id,
        resource_type=operation.resource_type,
        resource_id=operation.resource_id,
        status=operation.status,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
        progress_percent=operation.progress_percent,
        result=operation.result,
        error=error,
    )
