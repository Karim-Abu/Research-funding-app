"""Member-readable system status; the external test remains admin-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import admin
from app.api.errors import ProblemException
from app.config.settings import Settings
from app.contracts.system_status import SystemServiceStatus, SystemStatusView
from app.db.session import get_db
from app.security.deps import AuthContext, require_session, require_unsafe_guards, settings_dep


router = APIRouter(tags=["System status"])


def _view(context: AuthContext, db: Session, settings: Settings) -> SystemStatusView:
    raw = admin._status(db, settings)
    checked = [route.checked_at for route in raw.routes if route.checked_at]
    ai_checked = max(checked) if checked else None
    if raw.overall_status == "available":
        ai_state, ai_message, ai_next_step = (
            "available",
            "KI-Vorschläge können verwendet werden.",
            "Keine Aktion nötig.",
        )
    elif raw.overall_status == "degraded":
        ai_state, ai_message, ai_next_step = (
            "attention",
            "Ein Teil der KI-Verbindungen benötigt eine Prüfung.",
            "Ein Lead-Admin kann die Verbindung mit Testdaten prüfen.",
        )
    else:
        ai_state, ai_message, ai_next_step = (
            "unavailable",
            "KI-Vorschläge sind derzeit nicht verfügbar.",
            "Ein Lead-Admin kann die Verbindung mit Testdaten prüfen.",
        )
    firecrawl = raw.firecrawl
    if firecrawl.available and firecrawl.preflight_status == "pass":
        web_state, web_message, web_next_step = (
            "available",
            "Die Webrecherche ist verfügbar.",
            "Keine Aktion nötig.",
        )
    elif firecrawl.available:
        web_state, web_message, web_next_step = (
            "attention",
            "Die Webrecherche ist konfiguriert, aber noch nicht geprüft.",
            "Ein Lead-Admin kann die Verbindung mit Testdaten prüfen.",
        )
    else:
        web_state, web_message, web_next_step = (
            "unavailable",
            "Die Webrecherche ist derzeit nicht verfügbar.",
            "Ein Lead-Admin kann die Verbindung mit Testdaten prüfen.",
        )
    return SystemStatusView(
        services=[
            SystemServiceStatus(id="ai", label="KI-Vorschläge", state=ai_state, message=ai_message, next_step=ai_next_step, checked_at=ai_checked),
            SystemServiceStatus(id="web", label="Webrecherche", state=web_state, message=web_message, next_step=web_next_step, checked_at=firecrawl.checked_at),
        ],
        can_run_connection_check=context.user.role == "lead_admin",
    )


@router.get("/system-status", response_model=SystemStatusView)
def get_system_status(
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> SystemStatusView:
    return _view(context, db, settings)


@router.post("/system-status/connection-check", response_model=SystemStatusView)
def run_connection_check(
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> SystemStatusView:
    if context.user.role != "lead_admin":
        raise ProblemException(
            status=403,
            code="forbidden_role",
            title="Forbidden",
            detail="Only lead admins can run a connection check.",
        )
    admin.run_live_system_preflight(context=context, db=db, settings=settings)
    return _view(context, db, settings)
