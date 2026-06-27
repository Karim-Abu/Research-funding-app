"""Pydantic models mirroring openapi-v1_1.yaml exactly (Milestone 1 subset)."""
from app.contracts.auth import LoginRequest, SessionResponse, User
from app.contracts.capabilities import Capabilities
from app.contracts.classification import DataClassification
from app.contracts.health import Health
from app.contracts.problem import FieldError, Problem
from app.contracts.project import (
    Project,
    ProjectCreate,
    ProjectList,
    ProjectPatch,
)
from app.contracts.source import (
    SourceDocument,
    SourceStatus,
    SourceType,
    TextSourceCreate,
    UrlSourceCreate,
)

__all__ = [
    "Capabilities",
    "DataClassification",
    "FieldError",
    "Health",
    "LoginRequest",
    "Problem",
    "Project",
    "ProjectCreate",
    "ProjectList",
    "ProjectPatch",
    "SessionResponse",
    "SourceDocument",
    "SourceStatus",
    "SourceType",
    "TextSourceCreate",
    "UrlSourceCreate",
    "User",
]
