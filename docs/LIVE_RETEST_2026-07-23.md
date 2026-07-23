# Live-Retest 23.07.2026 (LIVE-02B/02C/03-Backlog, neue Freigabe)

Freigabe: genehmigter Verbesserungsplan vom 23.07.2026 (Owner-Entscheid
«komplett live testen», Kosten-Caps der dokumentierten Harnesse) inkl.
`RUN_FIRECRAWL_RECOVERY_APPROVED` für den Firecrawl-Re-Run nach dem
RUN-3-`provider_timeout`. Ausgeführt über die bestehenden Nachweis-Harnesse;
keine Umdeutung bestehender Statuswerte ohne echten Beleg.

## 1. Live-Aktivierung (Voraussetzung, neu seit diesem Retest)

- `backend/.env` vollständig live: `AI_EVAL_MODE=real`, `AGENT_FAKE_PROVIDER=false`,
  `WEB_RESEARCH_ENABLED=true`, `WEB_RESEARCH_FAKE_PROVIDER=false`; A1-Rolle neu
  konfiguriert (`gpt-5.6-luna` primär, `claude-haiku-4-5-20251001` Fallback) mit
  dokumentierten Preiseinträgen (source_url + checked_at=2026-07-23); Restpunkt
  `m,n.p0`-Zeile entfernt.
- Dev-DB-Schema per additivem Abgleich auf Modellstand gebracht (create_all-Drift:
  4 fehlende Tabellen, 123 fehlende Spalten ergänzt; Backup
  `backend/app.db.bak-2026-07-23`; danach `alembic stamp head`).
- Synthetischer Provider-Preflight (Replikat von `POST /admin/live-system-status/
  preflight`): **5/5 Routen PASS** (Luna, Haiku 4.5, Terra, Sonnet 5, Firecrawl),
  persistiert; dadurch `capabilities.generation_mode = real_eval` (verifiziert).
  Bericht: `backend/var/evaluation/provider_preflight.md`.

## 2. Ergebnisse

### LIVE-Web-Smoke (RUN-3B-Harness `scripts/run_live_web_smoke.py`)

**PASSED.** Echte Kette Planung → Firewall (`allow`, Risiko `low`) → Freigabe
(`used`) → Firecrawl-Suche + Fetch (3 Calls, 11.7 s) → Import; reale öffentliche
Quelle (`www.bfe.admin.ch`), `safety_status=passed`, kein Fake-Fallback, kein
Provider-Timeout. Details: `docs/LIVE_WEB_SMOKE_REPORT.md`.

### RUN-3C Phase 2 (`scripts/run_live_llm_phase2.py`, 3 vollständige Versuche)

| Versuch | prepare-web | LIVE-02A (A2 live) | Markt-Phase | Abbruchgrund |
|---|---|---|---|---|
| 1 (19:51) | PASS (Firecrawl real, 2 Anker) | **fail** | — | `failed_grounding_validation` → `live_02a_failed` |
| 2 (19:54) | PASS | **PASS** (echter Terra-Vorschlag akzeptiert, Grounding bestanden) | echter Sonnet-Call; Vergleich erstellt | fail-closed `market_comparison_anchor_scope_invalid` (Items ohne exakt verifizierte Zitat-Anker) |
| 3 (19:57) | PASS | **fail** | — | `live_02a_failed` |

Konstant über alle Versuche: `execution_mode=live`, `fake_fallback_observed=no`,
**kein einziger `provider_timeout`**. Letzter Ledger: `docs/LIVE_LLM_SMOKE_REPORT.md`.

### Kosten (effektiv, aus Ledgern)

LLM gesamt ≈ **CHF 0.06** (6 Terra-Calls à CHF 0.0003–0.021; Sonnet-Call in
Versuch 2 im Ledger des verworfenen Versuchs), Firecrawl 12 Calls (3 Smoke + 3×3
Phase-2), Preflight-Pings im Rappenbereich. Weit unter den Caps (CHF 3.00/Lauf).

## 3. Statuswahrheit (neu, ersetzt NUR die Begründung)

```text
LIVE_WEB_E2E_RETEST_PASSED                       (neu, 2026-07-23)
LIVE_02A_VALIDATED_LIVE_NOT_YET_STABLE           (1/3 Versuche akzeptierter Vorschlag)
COMBINED_LIVE_E2E_PARTIAL_STRICT_GATES           (ersetzt *_BLOCKED_BY_PROVIDER_TIMEOUT:
                                                  kein Provider-Fehler mehr; begrenzt durch
                                                  fail-closed Grounding-/Exakt-Zitat-Gates
                                                  bei realem Modell-Nichtdeterminismus)
HUMAN_QUALITY_REVIEW                             pending (unverändert)
```

LIVE-02B/02C/03 bleiben ohne vollständigen kombinierten PASS; der frühere
externe Blocker (Provider-Timeout) ist nachweislich behoben. Der verbleibende
Engpass ist Produktdesign (ehrliche fail-closed Gates) × LLM-Nichtdeterminismus
— kein Infrastruktur- und kein Konfigurationsproblem.

## 4. Live-Test in der App (Startprozedere ohne Demo-Overrides)

```powershell
# Backend (Env kommt vollständig aus backend/.env — KEINE $env:*FAKE*-Overrides!)
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# Frontend (zweites Terminal)
$env:APP_BACKEND_MODE = "live"; npm run dev
```

Danach: Quellen-Seite → Banner-Button «Neuen Live-Lauf erstellen» ist aktiv
(generation_mode=real_eval) → Live-Bestätigung (`live-run-v1`) → Webrecherche an,
Suchanfragen freigeben → Analyse starten (Kostenlimit CHF 2.00 greift). Editor
zeigt dann «Text mit KI verbessern» statt «Demo-Vorschlag erstellen».

## 5. Folgerungen (Backlog, nicht umgesetzt)

- **P1:** Exakt-Zitat-Verifikation der Markt-Items (`market/verify.py`) um eine
  normalisierte Vergleichsstufe ergänzen (Whitespace-/Markdown-Normalisierung),
  damit LIVE-02B mit realen Webquellen produkttauglich bestehen kann — ohne die
  ehrliche Semantik zu schwächen (weiterhin wörtliches Zitat, nur robustere
  Lokalisierung).
- **P1:** A2-Repair-Budget im Harness auf Produktniveau (1+max_retries) heben,
  damit ein einzelner Grounding-Fail nicht den Versuch beendet.
- HUMAN-01 bleibt Voraussetzung der Endfreigabe (unverändert).
