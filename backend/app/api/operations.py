"""Operations router — getOperation."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.run import AsyncOperation
from app.db.session import get_db
from app.repositories import operations as operations_repo
from app.security.deps import AuthContext, require_session

router = APIRouter(tags=["Infrastructure"])


@router.get("/operations/{operation_id}", response_model=AsyncOperation)
def get_operation(
    operation_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> AsyncOperation:
    operation = operations_repo.get_scoped(
        db, operation_id, context.user.workspace_id
    )
    if operation is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Operation not found.",
        )
    return operations_repo.to_contract(operation)
