# RUN-3E Acceptance Matrix (aktualisiert)

Stand: 23. Juli 2026  
Scope: RUN 3C Abschluss nach Owner-Entscheid

## Konvention

- `passed` = vollständig nachgewiesen
- `blocked` = technisch begründet blockiert (Status nicht veränderbar ohne erneuten Live-Gate-Freigaben)
- `not_run` = nicht ausgeführt
- `pending` = manuell/humane Freigabe ausständig
- `partial` = Teile nachgewiesen, Gesamtziel nicht vollständig

## Statusüberblick

| ID | Bereich | Status | Nachweis / Quelle |
|---|---|---:|---|
| AI-01 | Strukturierter feldbezogener Vorschlagsfluss mit Manifest | `passed` | `docs/RUN_3C_OFFLINE_RESULT.md` |
| AI-02 | Grounding-fähiger, scoped Anchor-Pfad + Claim-Prüfung | `passed` | `docs/LIVE_LLM_SMOKE_REPORT.md` (offline), `docs/LLM_SUGGESTION_ARCHITECTURE.md` |
| AI-04 | Staleness bei Draft-/Run-/Source-/Registry-/Market-Änderung | `passed` | `docs/RUN_3C_OFFLINE_RESULT.md` (Staleness-Gates der Offline-Phase) |
| AI-ACCEPT-01 | Accept erzeugt idempotent genau eine neue DraftVersion | `passed` | `docs/RUN_3C_PHASE2_DRY_RUN_RESULT.md`, `docs/RUN_3C_OFFLINE_RESULT.md` |
| AI-Q01 | Reine Umformulierung | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q02 | Dauer aus Original | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q03 | TRL aus strukturiertem Input | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q04 | Markt/Prozent-Claim im erlaubten Kontext | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q05 | Unbelegter Marktanteil wird abgelehnt | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q06 | Organisationsbezug im erlaubten Scope | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q07 | Nicht erlaubte Organisation ablehnen | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q08 | Produktbezug mit erlaubtem Anchor | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q09 | Konkrete Marktbehauptung bei korrekter Quelle | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q10 | Unbelegte Rechtsbehauptung ablehnen | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q11 | Datum/zeitliche Begriffe gegen Source prüfen | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q12 | Währung + Zahlen im erlaubten Kontext | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q13 | Gliederungsnummern nicht als Fakten fehlklassifizieren | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q14 | Unbelegtes Jahr ablehnen | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q15 | Akronymorganisation bei Nachweis | `passed` | `docs/LLM_SUGGESTION_EVAL.md` |
| AI-Q16 | Unicode/Unicode-Sicherheit | `passed` | `docs/LLM_SUGGESTION_EVAL.md`, `docs/RUN_3C_OFFLINE_RESULT.md` |
| SEC-02 | Falsche/ fremde/snippets/unsafe Claims fail-closed | `passed` | `docs/RUN_3C_OFFLINE_RESULT.md`, `docs/RUN_3C_MARKET_SCOPE_FAILURE_REVIEW.md` |
| MKT-01 | MarketComparison zwei geprüfter Sources erkennt limitiert | `passed` | `docs/RUN_3C_PROVIDER_RECOVERY_OFFLINE_RESULT.md`, `docs/RUN_3C_MARKET_SCOPE_FAILURE_REVIEW.md` |
| MKT-02 | Market-Evidenz ausschließlich auf geprüfte Quellen/Anchors | `passed` | `docs/RUN_3C_MARKET_SCOPE_FAILURE_REVIEW.md`, `docs/LIVE_LLM_SMOKE_REPORT.md` |
| LIVE-01 | Echter Live-Web-Smoke inklusive Query/Approval/Import | `passed` | `docs/LIVE_WEB_SMOKE_REPORT.md` |
| LIVE-02A | Missing-input statt Halluzination (echter LLM-Smoke) | `passed` | `docs/LIVE_LLM_SMOKE_REPORT.md` |
| LIVE-02B | Grounded Anchor Suggestion | `blocked` | `docs/LIVE_LLM_SMOKE_REPORT.md` |
| LIVE-02C | Shorten-Suggestion ohne neue Facts | `blocked` | `docs/LIVE_LLM_SMOKE_REPORT.md` |
| LIVE-03 | API-/BFF-Persistenz-, Read-, Accept- und Replay-Nachweis | `blocked` | `docs/RUN_3C_PHASE2_DRY_RUN_RESULT.md` (Offline), `docs/LIVE_LLM_SMOKE_REPORT.md` |
| Browser-01 | Browser-E2E (vollständige UI-Verifikation) | `pending` | Nicht ausgeführt im RUN-3C-Abschluss |
| HUMAN-01 | Humane Qualitätsbewertung | `pending` | `docs/LIVE_LLM_HUMAN_REVIEW.md` |

## Globale Ergebniszustände

- `RUN_3_TECHNICALLY_PARTIALLY_ACCEPTED`
- `MARKET_SCOPE_OFFLINE_VALIDATED`
- `LIVE_WEB_CAPABILITY_VALIDATED`
- `LIVE_LLM_CAPABILITY_VALIDATED`
- `COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT`

## Übergang RUN 4

- RUN 4 ist freigegeben (UI/UX-Fokus), jedoch ohne Provider-, Market- oder Architekturänderungen.
- RUN 4 wird als nachgelagerter Qualitäts- und Nutzungs-Lauf geführt; die fehlenden Zeilenstatus bleiben offen, bis der Browser- und humane Endbewertungsfluss abgeschlossen ist.
