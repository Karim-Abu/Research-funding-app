#!/usr/bin/env python
"""Opt-in Live-Firecrawl-Evaluation (Ebene D) — echte Webrecherche, public-safe.

Ablauf (alles über die produktiven Bausteine — Firewall, Approval-Service,
Firecrawl-Adapter; keine parallele Logik):

1. Wegwerf-SQLite-DB mit einem REIN SYNTHETISCHEN Projekt, dessen Titel,
   Partnername und Budgetzahl eindeutige CANARY-Marker sind.
2. Ein public-safe Recherchebrief-Query (generische D0-Begriffe), der die
   Canaries zusätzlich enthält, läuft durch die Search-Query-Firewall
   (``evaluate_query`` + ``approval_service.run_preview``).
3. Assertions: KEIN Canary in der bereinigten Query, KEIN Canary im
   Audit-Trail, KEIN Canary in den Lognachrichten.
4. Live-Firecrawl-Suche mit der bereinigten Query: Ergebnis ist eine echte
   URL (nie ``example.org`` — das ist der Fake-Provider) ODER ein sauber
   dokumentierter Leer-/Fehlerzustand (0 Treffer, Kontingent, Ausfall).

Opt-in-Guards (sonst wird alles ehrlich als ``not_run`` berichtet, Exit 0):
``CI`` ungesetzt · ``RUN_REAL_PROVIDER_SMOKE=true`` ·
``WEB_RESEARCH_ENABLED=true`` · ``WEB_RESEARCH_FAKE_PROVIDER`` nicht true ·
``FIRECRAWL_API_KEY`` vorhanden.

Bericht: stdout + ``backend/var/evaluation/live_research_smoke.md`` —
Status, Zählwerte, Domain des ersten Treffers. Keine Keys, keine Canaries,
keine Rohinhalte. Ein Provider-Ausfall macht den Aufruf NIE rot.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
_OUT = _BACKEND / "var" / "evaluation" / "live_research_smoke.md"

_SMOKE_DB = Path(tempfile.gettempdir()) / "live_research_smoke.db"
if _SMOKE_DB.exists():
    _SMOKE_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_SMOKE_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")
os.chdir(_BACKEND)  # env_file=".env" ist CWD-relativ → backend/.env (Key)
sys.path.insert(0, str(_BACKEND))

# Eindeutige, rein synthetische Canary-Marker (nie echte Namen/Zahlen).
CANARY_TITLE = "ZORNAK-KANARIE-TITEL-9471"
CANARY_PARTNER = "Kanarienwerk Beispielia AG 9472"
CANARY_BUDGET = 947473  # eindeutige synthetische Budgetzahl
CANARIES = (CANARY_TITLE, "ZORNAK", "Kanarienwerk", "Beispielia", "947473")

# Public-safe D0-Kern der Query (generisch, ohne Projektidee).
PUBLIC_SAFE_CORE = "innovation funding energy monitoring market overview Schweiz"


def _report(lines: list[str]) -> None:
    text = "\n".join(lines) + "\n"
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(text, encoding="utf-8")
    print(text)
    print(f"Bericht: {_OUT}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    header = [
        "# Live-Firecrawl-Evaluation (Ebene D)",
        "",
        f"*Generiert:* {generated}",
        "",
    ]

    from app.config.settings import get_settings

    settings = get_settings()
    opted_in = (
        os.environ.get("CI") is None
        and os.environ.get("RUN_REAL_PROVIDER_SMOKE", "").lower() == "true"
        and settings.web_research_enabled
        and not settings.web_research_fake_provider
        and bool(settings.firecrawl_api_key)
    )
    if not opted_in:
        _report(header + [
            "**Status: not_run** — Opt-in unvollständig "
            "(RUN_REAL_PROVIDER_SMOKE/WEB_RESEARCH_ENABLED/Key/Fake-Flag). "
            "Es wurde kein externer Call ausgeführt.",
        ])
        return 0

    # --- Wegwerf-DB + synthetisches Canary-Projekt ---------------------------
    from app.db.session import SessionLocal, engine
    from app.db.models import Base, AuditEvent, Partner, Project, User, Workspace

    Base.metadata.create_all(engine)
    db = SessionLocal()
    workspace_id = "ws-live-smoke"
    actor = "user-live-smoke"
    db.add(Workspace(id=workspace_id, name="Live Smoke WS"))
    db.add(User(
        id=actor, workspace_id=workspace_id, name="Live Smoke",
        email="smoke@example.test", password_hash="x", role="lead_admin",
    ))
    project_id = "proj-" + uuid.uuid4().hex[:8]
    project = Project(
        project_id=project_id, workspace_id=workspace_id, title=CANARY_TITLE,
        description="Synthetisches Canary-Projekt für den Live-Smoke.",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification={
            "sensitivity": "public", "origin": "synthetic",
            "processing_mode": "cloud_assisted", "web_research_mode": "public_only",
            "nda_applies": False,
        },
        budget_framework_chf=float(CANARY_BUDGET),
        created_by=actor, status="draft",
    )
    db.add(project)
    db.add(Partner(
        partner_id="pt-" + uuid.uuid4().hex[:8], project_id=project_id,
        workspace_id=workspace_id, name=CANARY_PARTNER,
        partner_type="implementation_partner", country="CH", created_by=actor,
    ))
    db.flush()

    # --- Log-Capture für den Canary-Scan --------------------------------------
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(self.format(record))

    capture = _Capture()
    logging.getLogger().addHandler(capture)

    # --- Firewall + Approval (produktiver Pfad) -------------------------------
    from app.security.approval_service import run_preview

    raw_query = (
        f"{PUBLIC_SAFE_CORE} {CANARY_TITLE} {CANARY_PARTNER} CHF 947'473"
    )
    outcome_preview = run_preview(
        db,
        project=project,
        actor_user_id=actor,
        raw_query=raw_query,
        intended_tool="firecrawl",
        purpose="live_research_smoke",
        apply_project_lexicon=True,
        force_approval=True,
    )
    db.commit()
    result = outcome_preview.result
    sanitized = result.sanitized_query

    redaction_counts = ", ".join(
        f"{entry['category']}×{entry['count']}"
        for entry in result.redaction_summary
    ) or "keine"
    lines = header + [
        "**Status: durchgeführt**",
        "",
        f"- Firewall-Entscheid: `{result.decision}` · Risiko {result.risk_score}",
        f"- Redaktionen: {redaction_counts}",
    ]

    failures: list[str] = []
    leaked_in_query = [c for c in CANARIES if c.lower() in sanitized.lower()]
    if leaked_in_query:
        failures.append(f"{len(leaked_in_query)} Canary(s) in der bereinigten Query")
    lines.append(
        "- Canaries in bereinigter Query: "
        + ("KEINE ✓" if not leaked_in_query else f"{len(leaked_in_query)} — FAIL")
    )

    audit_blob = " ".join(
        f"{event.action} {event.detail}"
        for event in db.query(AuditEvent).all()
    )
    leaked_in_audit = [c for c in CANARIES if c.lower() in audit_blob.lower()]
    if leaked_in_audit:
        failures.append(f"{len(leaked_in_audit)} Canary(s) im Audit-Trail")
    lines.append(
        "- Canaries im Audit-Trail: "
        + ("KEINE ✓" if not leaked_in_audit else f"{len(leaked_in_audit)} — FAIL")
    )

    log_blob = "\n".join(captured)
    leaked_in_logs = [c for c in CANARIES if c.lower() in log_blob.lower()]
    if leaked_in_logs:
        failures.append(f"{len(leaked_in_logs)} Canary(s) in Lognachrichten")
    lines.append(
        "- Canaries in Logs: "
        + ("KEINE ✓" if not leaked_in_logs else f"{len(leaked_in_logs)} — FAIL")
    )

    # Produktsemantik: eine geblockte Query wird NIE gesendet — auch nicht
    # saniert. Der Live-Call nutzt die separat geprüfte public-safe Query
    # (entspricht der menschlich freigegebenen bereinigten Query).
    if result.decision == "block":
        lines.append(
            "- Canary-Query wurde von der Firewall geblockt (korrekt); der "
            "Live-Call nutzt die separat geprüfte public-safe Query."
        )
        safe_outcome = run_preview(
            db,
            project=project,
            actor_user_id=actor,
            raw_query=PUBLIC_SAFE_CORE,
            intended_tool="firecrawl",
            purpose="live_research_smoke",
            apply_project_lexicon=True,
            force_approval=True,
        )
        db.commit()
        if safe_outcome.result.decision == "block":
            failures.append("public-safe Kern-Query wurde geblockt")
        sanitized = safe_outcome.result.sanitized_query
        lines.append(
            f"- Freigabefähige Query: Entscheid `{safe_outcome.result.decision}`"
        )

    # --- Live-Firecrawl mit der bereinigten Query -----------------------------
    from app.research.providers.base import (
        CreditExceeded, ProviderError, ProviderTimeout, SearchRequest,
    )
    from app.research.providers.firecrawl import FirecrawlProvider

    provider = FirecrawlProvider(
        api_key=settings.firecrawl_api_key, timeout_seconds=30
    )
    try:
        outcome = provider.search(SearchRequest(query=sanitized, max_results=3))
    except CreditExceeded:
        lines.append(
            "- Live-Suche: FEHLERZUSTAND dokumentiert — Kontingent-/Budget-"
            "grenze (HTTP 402/429). Kein Ergebnis, kein stiller Fake-Ersatz."
        )
        outcome = None
    except (ProviderError, ProviderTimeout) as exc:
        lines.append(
            "- Live-Suche: FEHLERZUSTAND dokumentiert — "
            f"{type(exc).__name__}. Kein Ergebnis, kein stiller Fake-Ersatz."
        )
        outcome = None

    if outcome is not None:
        if not outcome.candidates:
            lines.append(
                "- Live-Suche: durchgeführt, 0 Treffer — gültiger, "
                "dokumentierter Leerzustand (kein erfundenes Ergebnis)."
            )
        else:
            first = outcome.candidates[0]
            domain = urlparse(first.url).netloc
            fake_hits = [
                c.url for c in outcome.candidates if "example.org" in c.url
            ]
            if fake_hits:
                failures.append(
                    f"{len(fake_hits)} example.org-Ergebnis(se) im Live-Modus"
                )
            lines.append(
                f"- Live-Suche: {len(outcome.candidates)} echte(s) Ergebnis(se); "
                f"erste Domain: `{domain}` · Latenz {outcome.latency_ms} ms"
            )
            lines.append(
                "- example.org im Live-Modus: "
                + ("KEINS ✓" if not fake_hits else f"{len(fake_hits)} — FAIL")
            )

    lines += [
        "",
        ("**Ergebnis: PASS** — Firewall hält Canaries zurück; Live-Modus "
         "liefert echte URLs oder einen dokumentierten Leer-/Fehlerzustand.")
        if not failures
        else "**Ergebnis: FAIL** — " + "; ".join(failures),
    ]
    logging.getLogger().removeHandler(capture)
    db.close()
    _report(lines)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
