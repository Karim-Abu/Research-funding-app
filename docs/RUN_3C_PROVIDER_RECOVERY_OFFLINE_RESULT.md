# RUN 3C Provider-Recovery – Gate A Offline-Ergebnis

Stand: 22. Juli 2026

Status: Gate A vollständig offline umgesetzt und geprüft. Gate B, Gate C,
Firecrawl-Recovery, Provider-Preflights und RUN 4 wurden nicht ausgeführt.

## 1. Ausgangspunkt und Commits

- Ausgangs-HEAD: `3e9e250952290599acc29b49baf2c554ec82291b`.
- Die bereits abgeschlossene Attempt-3-Forensik wurde vor Gate A als eigener
  Dokumentationscommit `df938bb` gesichert.
- Gate-A-Implementierung und Regressionen: `5e22ebc`.
- Alembic-Head vor und nach Gate A: `c3e5a7b9d024`.
- Neue Migrationen: keine.
- Externe LLM-/Firecrawl-Requests: `0`.
- Provider-Preflights: `0`.
- Live-Kosten: CHF `0`.

Die historische Live-Wahrheit bleibt unverändert: LIVE-01 ist bestanden,
LIVE-02A bestand in Attempt 3; LIVE-02B, LIVE-02C, LIVE-03 und Human Review
bleiben `not_run` beziehungsweise `pending`.

## 2. Präzise Providerdiagnose

`backend/app/provider_errors.py` ist die gemeinsame reine Klassifikation für
Readiness, Research Executor und Harness. Sie enthält keine Retry-Logik und
verarbeitet ausschließlich Fehlerklasse, sicheren Reason-Code und optionalen
HTTP-Status.

| Befund | Reason-Code | Retryable |
|---|---|---:|
| HTTP 401/403 | `provider_auth_error` | nein |
| HTTP 429 | `provider_rate_limited` | ja |
| HTTP 502/503/504 und übrige HTTP-5xx | `provider_outage` | ja |
| Timeout | `provider_timeout` | ja |
| Schema-/Inhaltsvertrag ungültig | `provider_response_invalid` | nein |

Die bestehende Preflight-Funktion verwendet dieselbe Klassifikation und
projiziert für bestehende Readiness-Clients weiterhin deren kompatible Literale
`auth_failed`, `rate_limited` und `timeout`. Es entstand kein zweites
Wahrheitssystem.

Der Research Executor persistiert nun den präzisen Code auf `ResearchTask` und
`AsyncOperation`. Die additive ResearchTask-Projektion liefert `error_code` und
`retryable`; Rohantworten oder Provider-Bodies werden nicht gespeichert. Der
Firecrawl-Adapter unterscheidet HTTP 402 von HTTP 429, damit Rate-Limiting nicht
als allgemeiner Kontingentfehler verloren geht. Es wurde weder ein automatischer
Retry noch ein Providerwechsel ergänzt.

## 3. Harness-Diagnose und früher Ledger

Nach `POST /research-briefs/{id}/run` liest das Harness zuerst über die
produktiven HTTP-Routen:

1. `GET /research-tasks/{task_id}`;
2. `GET /operations/{operation_id}`;
3. erst bei beidseitig erfolgreichem Terminalstatus die ResearchResults.

Ein persistierter HTTP-5xx-Fehler bleibt dadurch `provider_outage` mit
`retryable=true`. Er wird nicht mehr als
`insufficient_external_evidence` umetikettiert. Dieser zweite Code entsteht nur,
wenn die Recherche erfolgreich war, aber weniger als zwei geeignete Ergebnisse
lieferte.

Vor dem ersten Providertransport wird außerhalb des Repositorys atomar ein
redigierter Attempt-Ledger geschrieben. Er enthält ausschließlich Attempt-ID,
Sequenz, Provider, Route-Alias, Zweck, Start/Ende, HTTP-Klasse/-Status,
Retryability, sicheren Reason-Code, optionale Token und geschätzte/tatsächliche
Kosten. Query, URL, Prompt, Key, Header, Inhalt und Providerantwort sind
ausgeschlossen. Der Ledger besitzt einen in der Review-Session gebundenen
Integritäts-Hash, wird bei Erfolg oder frühem Fehler in den redigierten Bericht
übernommen und anschließend mit dem temporären Attempt-Verzeichnis entfernt.

## 4. Web-first-Aufteilung

Der einzige bestehende Phase-2-Orchestrator bietet jetzt:

- `prepare-web`: D0-Bootstrap, Brief, Planner, Firewall, Approval, Firecrawl,
  explizite Imports, Passageprojektion und Review-Session;
- `resume-llm`: erst nach exakter Quote-Hash-Freigabe A2-Preflight, LIVE-02A,
  gegebenenfalls separater Market-Preflight, MarketComparison, LIVE-02B,
  LIVE-02C sowie LIVE-03 Read/Accept/Replay;
- `cleanup-expired`: unverändert begrenzter Session-Cleanup.

`prepare-web` prüft ein eigenes explizites Firecrawl-Recovery-Opt-in und benötigt
keine OpenAI-/Anthropic-Schlüssel. `resume-llm` behält das separate LLM-Opt-in.
Beide Kommandos verwenden weiterhin dieselben produktiven HTTP-/BFF-,
Provider-, Research-, Market- und Suggestionpfade. Es entstand kein paralleler
Produktpfad.

## 5. Zusammenhängende Offline-Regressionen

### Firecrawl-502-Fehlerpfad

`test_phase2_prepare_web_provider_502_is_classified_and_cleaned` durchläuft den
produktiven `prepare-web`-Einstieg mit blockiertem DNS/Socket und einem
Transportdouble, das am Firecrawl-Search exakt HTTP 502 simuliert.

Nachgewiesen:

- ResearchTask und AsyncOperation persistieren `failed/provider_outage`;
- ResearchTask projiziert `retryable=true` und `result_count=0`;
- keine Ergebnisliste wird als erfolgreicher Researchzustand interpretiert;
- kein `insufficient_external_evidence`;
- früher Ledger enthält HTTP 502 und den sicheren Code;
- null LLM-Transportrequests, kein Fake-Fallback, kein Import;
- vollständiger Cleanup von DB, Sources, Checkpoint, Export und Attempt-Ledger.

### Web-first Happy Path

`test_phase2_prepare_web_resume_llm_full_offline_dry_run` durchläuft in zwei
getrennten Spawn-Prozessen die vollständige Kette:

```text
prepare-web
→ Session speichern und neu laden
→ exakte Quote-Hash-Freigabe
→ resume-llm
→ A2/Market-Testadapter
→ LIVE-02A/B/C
→ Suggestion Read
→ scoped Accept und Replay
→ genau eine neue DraftVersion
→ Originalversion weiterhin lesbar
→ Cleanup
```

Vor der Anchor-Freigabe wurden exakt `0` LLM-Transportrequests beobachtet. Die
drei Firecrawl-Testoperationen waren `search`, `fetch`, `fetch`; nach Freigabe
folgten die sechs geplanten LLM-Testtransporte. Sämtliche nutzerwirksamen
Operationen liefen über die produktiven HTTP-/BFF-Routen. Registry-Bindung,
Feld-ID, Requirement, Portalfrage, Skill und Marker 3.1/3.2/3.3 blieben aus den
echten Registry-/Portalmetadaten abgeleitet.

## 6. Gemessene Gates

| Gate | Ergebnis |
|---|---|
| Provider-/Harness-/beide zusammenhängenden Dry Runs | `52 passed`, 31,6 s |
| Research-Brief/Public-Web/Market-/Partner-Regressionen | `81 passed`, 16,9 s |
| Runtime-Verträge/Registry/Role-Skills/RUN-3B/RUN-3C | `36 passed`, 15,4 s |
| Statischer Vertragsvalidator | 9 Dokumente, 58 Schemas, 76 Requirements, 165 Portal-Felder, 83 API-Operationen, `passed` |
| Migration Fresh/Down/Up | Head `c3e5a7b9d024`, `passed`, 8,3 s |
| `scripts/verify_all.ps1` in isolierter Sitzung | Produkt-/Frontendtests liefen; ausschließlich Word COM wegen fehlender Windows-Anmeldesitzung `failed`, 692,4 s |
| unveränderter `scripts/verify_all.ps1`-Hostlauf | Exit `0`, 683,3 s |
| Vollständiges Pytest im Hostlauf | `passed`, vier bestehende Skips |
| DOCX-Render-Smoke im Hostlauf | `passed` |
| Vitest, ESLint, TypeScript, Production Build | jeweils `passed` |
| Playwright mit einem Worker | `passed` |
| Golden Path, funktionaler Import, Review Truth, API-Smoke | jeweils `passed` |
| `git diff --check` | `passed` |

Für die Word-COM-Umgebungsgrenze wurden weder Code noch Tests geändert. Der
unveränderte Befehl bestand anschließend in der lokalen Host-Sitzung.

## 7. Verträge, Migration und Hygiene

- `ResearchTask.error_code` und `ResearchTask.retryable` sind additive Pydantic-
  und OpenAPI-Felder; bestehende Felder bleiben kompatibel.
- Die Änderung benötigt keine Schema- oder Datenmigration.
- Der finalisierte statische Vertrag und Runtime-OpenAPI blieben grün.
- Es sind keine `.env`, Datenbanken, Logs, Rohprompts, Providerantworten oder
  Sessionartefakte getrackt.
- Der Signaturscan meldete ausschließlich bereits bekannte synthetische
  Security-Canaries beziehungsweise Dokumentationsstrings; keine neuen Secrets.
- Die beim absichtlich roten 502-Test entstandenen lokalen `p2err-*`- und
  `.pytest_cache`-Reste wurden gezielt entfernt. Bestehende ignorierte lokale
  Benutzer-/Testdaten unter `backend/var` wurden nicht gelöscht oder committed.
- Kumulativer Gate-A-Diff des Implementierungscommits: 12 Dateien, 632
  Einfügungen, 130 Löschungen.

## 8. Grenzen und Haltepunkt

Gate A belegt ausschließlich Offline-Korrektheit, Diagnosewahrheit,
Web-first-Orchestrierung und Cleanup. Es belegt keine wiederhergestellte
Firecrawl-Verfügbarkeit und keine neue Live-LLM-Qualität.

- Gate B: `not_run`, nicht autorisiert.
- Gate C: `not_run`, nicht autorisiert.
- RUN 4: `not_started`, nicht autorisiert.

Der nächste zulässige Schritt erfordert die exakte separate Freigabe
`RUN_FIRECRAWL_RECOVERY_APPROVED`.
