"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    auth,
    capabilities,
    evidence,
    fields,
    health,
    me,
    operations,
    partners,
    projects,
    requirements,
    review,
    runs,
    sources,
)
from app.api.errors import (
    ProblemException,
    http_exception_handler,
    problem_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.config.logging import configure_logging
from app.config.settings import get_settings

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("app")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup check: verify DB connectivity and report contract/registry version.
    from app.db.session import engine

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    # Fail-closed: load + validate the requirement/rule registries at startup so a
    # corrupt or drifted registry stops the app rather than evaluating runs
    # against a broken policy.
    from app.registry import get_registry

    registry = get_registry()
    # Single-instance recovery: fail anything left mid-processing on restart.
    from app.ingestion.pipeline import recover_interrupted
    from app.runs.executor import recover_interrupted_runs

    recovered_sources = recover_interrupted()
    recovered_runs = recover_interrupted_runs()
    logger.info(
        "startup ok api_version=%s requirement_registry=%s rule_registry=%s "
        "recovered_sources=%d recovered_runs=%d",
        settings.api_version,
        registry.requirement_registry_version,
        registry.rule_registry_version,
        recovered_sources,
        recovered_runs,
    )
    yield


app = FastAPI(
    title="Innosuisse Proposal Assistant API",
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_exception_handler(ProblemException, problem_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

for module in (
    health, auth, me, capabilities, projects, sources, runs, operations,
    partners, requirements, evidence, fields, review,
):
    app.include_router(module.router, prefix=API_PREFIX)
