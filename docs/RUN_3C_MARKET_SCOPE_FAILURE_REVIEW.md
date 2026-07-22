# RUN 3C – Market-Scope Recovery (Offline-RCA)

Stand: 22. Juli 2026

## Ergebnis

- MARKET_SCOPE_RECOVERY_OFFLINE_PASSED
- READY_FOR_TARGETED_GATE_C_RETEST_DECISION

## 1) Forensische Feststellung (ohne historische Datenbankzeilen)

Die historische Live-Session aus den verlinkten Versuchen ist zurzeit nicht mehr
persistiert. Die Beurteilung stützt sich ausschließlich auf:

- docs/LIVE_LLM_SMOKE_REPORT.md
- docs/RUN_3C_PROVIDER_RECOVERY_OFFLINE_RESULT.md
- docs/RUN_3C_ATTEMPT3_FAILURE_REVIEW.md
- docs/RUN_3C_PHASE2_DRY_RUN_RESULT.md
- docs/LIVE_LLM_HUMAN_REVIEW.md
- backend/app/market/executor.py
- backend/app/market/source_scope.py
- backend/app/market/verify.py
- backend/app/api/research.py
- backend/app/research/service.py
- backend/app/research/import_service.py

Die belegten Codes aus den Berichten zeigen, dass LIVE-02B nach dem Research-/Import-
-Pfad bei `market_comparison_not_limited_insufficient_external_evidence_no_error`
abgebrochen wurde, obwohl zwei freigegebene Quellen vorlagen.

## 2) Echte Modell-/DTO-Inventur (ohne Annahmen)

### Relevante Entitäten

- `ResearchTask.execution_mode` (`live` / `fake_demo`)
- `ResearchTask.status` + `ResearchTask.error_code` + `ResearchTask.result_count`
- `ResearchResult.status`, `.content_review_status`, `.support_status`, `.content_safety_status`
- `SourceDocument` (`type="url"`, `status`, `current_source_version_id`, `data_classification`)
- `SourceVersion.content_review_status`, `SourceVersion.content_safety_status`,
  `SourceVersion.processing_status`, `retrieval_provenance`
- `SourceFragment` (offset-basierte Textsegmente)
- `EvidenceAnchor` (`scope`, `verification_status`, `quote_hash`, `source_version_id`)
- `EvidenceLink` (`anchor_id`, `target_type`, `target_id`, `status`)
- `MarketComparison` (`status`, `warnings`, `research_gaps`, `source_version_ids`,
  `source_scope_hash`, `generation_status`, `error_code`)
- `MarketComparisonItem` (`confidence_label`, `verified_quote_refs`, `evidence_anchor_ids`,
  `coverage_status`)

### Kette der Marktvergleichs-Eligibility

`backend/app/market/source_scope.py`

1. `imported_public_sources` filtert nur:
   - `SourceDocument.type="url"`, `status="processed"`
   - `SourceVersion.processing_status="processed"`
   - `SourceVersion.content_review_status="reviewed"`
   - `SourceVersion.content_safety_status in {"passed","human_released"}`
   - `ResearchResult.status="imported"`
   - `ResearchResult.content_review_status="reviewed"`
   - `ResearchResult.support_status in {"supports","partially_supports"}`
   - `ResearchTask.execution_mode="live"`
   - `data_classification origin="public_source"`, `sensitivity="public"`
   - deterministisch sortierte `source_id`-Reihenfolge
2. `prefilter_fragments` extrahiert Kandidaten nur bei `MARKET_SIGNAL_TERMS`
   (oder bei `require_market_signal=False`).

`backend/app/research/import_service.py`:

- Import setzt `ResearchResult.status="imported"` und Versionen auf
  `content_review_status="unreviewed"` initial.

`backend/app/api/research.py`:

- `create_external_anchor` ist strikt auf exakte Quote/Offset/Fragment-Bindung
  und schreibt ausschließlich `scope="external"`-Evidenz.
- Evidence-Verknüpfung auf `EvidenceLink` wird von der Verifikationsroutine bei einem
  expliziten Ziel (`target_id`) hergestellt.

`backend/app/market/verify.py`:

- `verify_quote` verlangt exakt den Span innerhalb der aktuellen `SourceVersion` des
  aktuellen Projekts/Workspaces.
- Verifizierung wird mit Projekt-/Workspace- und Versionsschutz gebunden.

## 3) Präzise Root-Cause-Kette

Die vorherige Laufzeitverweigerung entstand in der produktiven Marktvergleichslogik:

- Zwei geeignete, importierte Live-Quellen waren vorhanden (`len(sources) == 2`).
- `prefilter_fragments(...)` ergab keine Kandidaten.
- Vor der Korrektur wurde der leere Kandidatenpfad in `comparison_executor` als
  globaler Mangelfall mit `status="insufficient_external_evidence"` beantwortet.

Damit wurde das fachliche Ergebnis (`limited`) für den Sonderfall „zwei geeignete, aber
inhaltlich nicht-marktrelevante Quellen“ nicht erreicht.

**Klassifikation:** `EFFECTIVE_GROUNDED_SCOPE_MISMATCH`

**Prüfbarer Zustand im Code:** `backend/app/market/executor.py` – leerer Kandidatenpfad
mit `len(sources) >= 2`.

## 4) Deterministische Offline-Reproduktion (frische DB, produktive Pfade)

Testfall:

- `backend/tests/test_market_comparison.py::test_market_comparison_two_reviewed_live_sources_becomes_limited`

Belegte Schritte (offline, ohne Netz):

1. Projekt + Workspace in Test-DB anlegen.
2. Zwei Source Documents + Versions + Fragments seeden (`type=url`, public_source, reviewed/imported/live).
3. Rechercheergebnisse per `POST /research-results/{id}/review` auf `supports` setzen.
4. Passagen anzeigen (`GET /research-results/{id}/anchor-passages`) und exakt über
   `POST /research-results/{id}/external-anchors` zu `scope=external`-Anchors materialisieren.
5. `POST /projects/{project_id}/market-comparisons` auslösen.
6. Hintergrund-Executor beenden lassen und Vergleich lesen.

Erwartung nach Fix:

- `MarketComparison.status == "limited"`
- `warnings` enthält `limited_external_evidence`
- `item_count == 0`, `source_version_ids` enthält exakt beide unterschiedlichen
  Versionen.

Dieser Test deckt die historische Fehlklasse reproduzierbar ab und belegt den
Minimalfix über denselben produktiven HTTP-/BFF-Stack.

## 5) Ergebnis der Behebung

Minimaler Produktfix:

- `backend/app/market/executor.py`
  – leerer Kandidatenpfad unterscheidet nun:
  - `<2` geeignete Quellen → weiterhin `insufficient_external_evidence`
  - `>=2` geeignete Quellen ohne Marktpassagen → jetzt `limited` mit
    `warning="limited_external_evidence"`.

Damit wird die fachlich vereinbarte Stufung für den Sonderfall „mehrere
ggeeignete Quellen ohne belastbare Markt-Claims“ korrekt repräsentiert, ohne
Sicherheitsregeln abzubauen.

## 6) Ausgeführte Offline-Tests

- `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_market_comparison.py`
- Ergebnis: `20 passed`
- inkl. des Repro-Falls für `test_market_comparison_two_reviewed_live_sources_becomes_limited`

- `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_run3b_research_market.py`
- Ergebnis: `11 passed`

## 6a) Voller Offline-Gate-Run

- `powershell -ExecutionPolicy Bypass -File scripts/verify_all.ps1`
- Ergebnis: `FAIL` (nicht-produktiver Infrastrukturfehler):
  - `tests/test_docx_render_smoke.py::test_docx_render_smoke_all_pages` benötigt eine
    Windows-Word-Sitzung / COM-Interaktion (`COM error: Session not available`).
  - `vitest`-Schritt scheitert am Auflösungsfehler der lokalen `vitest.config.ts`-Pfad (Access denied).

  Alle übrigen Backend-, Playwright-, Release- und API-Smoke-Pfade des Skripts liefen
  bis zu diesen bekannten Grenzen sauber durch.

## 7) Offene Unsicherheiten

- Keine weiteren Produktursachen nachweisbar.
- Keine zusätzlichen Transaktions-/Sichtbarkeitsdefekte durch diesen Fix nachgewiesen.
  (Keine neuen Datenstränge nötig, da die Statusabweichung allein aus der
  Vergleichsabschluss-Kondition stammte.)

## 8) Nächster Schritt

Nach eindeutigem Reproduktionsbeweis und minimalem Fix ist der Status auf
`MARKET_SCOPE_RECOVERY_OFFLINE_PASSED` gesetzt und die Freigabe zum gezielten
Gate-C-Entscheidungsprozess dokumentiert.
