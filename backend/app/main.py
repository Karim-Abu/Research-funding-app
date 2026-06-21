"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import auth, capabilities, health, me, projects
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
    logger.info(
        "startup ok api_version=%s policy_version=%s",
        settings.api_version,
        settings.policy_version,
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

for module in (health, auth, me, capabilities, projects):
    app.include_router(module.router, prefix=API_PREFIX)
