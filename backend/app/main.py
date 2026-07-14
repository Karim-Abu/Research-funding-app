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
    exports,
    fields,
    firewall,
    health,
    imports,
    integrated_draft,
    market_research,
    research_briefs,
    me,
    operations,
    market,
    partners,
    projects,
    reliability,
    requirements,
    research,
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
    # Fail-closed: validate the agent profile registry at startup too (M9A).
    # A1/A2/A3 are not executed in the run graph; this only guards the contract.
    from app.agents.registry import get_agent_registry

    get_agent_registry()
    # Milestone 9I-B: inject the beta-internal market-comparison profile (code-only;
    # no finalized contract modified).
    from app.market.agent_profile import ensure_registered as _register_market_profile

    _register_market_profile()
    # Single-instance recovery: fail anything left mid-processing on restart.
    from app.exports.executor import recover_interrupted_exports
    from app.ingestion.pipeline import recover_interrupted
    from app.runs.executor import recover_interrupted_runs

    recovered_sources = recover_interrupted()
    recovered_runs = recover_interrupted_runs()
    recovered_exports = recover_interrupted_exports()
    logger.info("recovered_exports=%d", recovered_exports)
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
    partners, requirements, evidence, fields, review, exports, research, market,
    firewall, reliability, imports, market_research, research_briefs, integrated_draft,
):
    app.include_router(module.router, prefix=API_PREFIX)
