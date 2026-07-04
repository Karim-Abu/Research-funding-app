# Repository And Stack Map

## Repository-Struktur

| Pfad | Zweck | Status | Bemerkung |
|---|---|---|---|
| `app/` | Next.js App Router Pages und BFF-Routen | Aktuell implementiert | BFF leitet an FastAPI weiter (`lib/bridge.ts:1`) |
| `components/` | UI-Komponenten für Shell, Quellen, Editor, Review, Export, Portal Transfer | Aktuell implementiert | Live und Mock-Komponenten gemischt (`components/export/live-export.tsx:91`) |
| `lib/` | Frontend-Clients, DTOs, ViewModels, Mockdaten | Teilweise live, teilweise Mock | `lib/app-mode.ts:38`, `lib/api.ts:51` |
| `backend/app/` | FastAPI Backend, Services, DB, Agents, Policies | Aktuell implementiert | Router-Registrierung in `backend/app/main.py:64` |
| `backend/app/db/models.py` | SQLAlchemy-Datenmodell | Aktuell implementiert | Enthält zentrale Domänenklassen (`backend/app/db/models.py:92`) |
| `backend/app/migrations/` | Alembic-Migrationen | Aktuell implementiert | Initial + Milestone-Migrationen (`backend/app/migrations/versions/08e269f5b452_initial_schema.py:1`) |
| `final_backend_contracts_v1_1/` | OpenAPI, Domain-/Agent-/Rule-/Tool-/Policy-Registries | Ziel-/Contract-Quelle und aktive Registry | Loader nutzt YAMLs fail-closed (`backend/app/registry/loader.py:1`) |
| `test/` | Frontend/Vitest/MSW Tests | Aktuell implementiert | z. B. Export/Fields/Review/Portal Transfer |
| `e2e/` | Playwright E2E/API-Smokes | Aktuell implementiert | A2, Market, Portal Transfer, Reliability |
| `backend/tests/` | Pytest Backend Tests | Aktuell implementiert | Auth, Runs, Sources, Agents, Review, Export, Privacy |
| `scripts/` | Verification/Smoke Scripts | Aktuell implementiert | `scripts/verify_all.ps1`, `scripts/smoke_api.py` |
| `docs/` | Milestone-, Security-, Evaluation- und Audit-Dokumente | Vorhandene Dokumentation | Code hat Vorrang, Docs dienen nur Kontext |

## Frontend-Stack

Der Frontend-Stack ist Next.js 16, React 19, TypeScript, Tailwind/PostCSS, TipTap für Rich Text, lucide-react für Icons, Vitest und Playwright (`package.json:7`, `package.json:20`, `package.json:24`, `package.json:30`, `package.json:44`). Das UI nutzt App Router Pages unter `app/*/page.tsx` und Komponenten unter `components/*`.

## Backend-Stack

Das Backend nutzt FastAPI, Uvicorn, Pydantic v2, SQLAlchemy, Alembic, Argon2, python-multipart, pypdf, python-docx, LangGraph, PyYAML, httpx und pytest (`backend/requirements.txt:4`, `backend/requirements.txt:8`, `backend/requirements.txt:12`, `backend/requirements.txt:18`). FastAPI registriert Router mit Prefix `/api/v1` (`backend/app/main.py:30`, `backend/app/main.py:64`).

## Datenbank/ORM/Migrationen

SQLAlchemy-Modelle liegen in `backend/app/db/models.py`; Sessions/Engine in `backend/app/db/session.py`; Migrationen in `backend/app/migrations/versions/*` (`backend/app/db/models.py:30`, `backend/app/db/session.py:1`, `backend/alembic.ini:1`). Default-DB-URL ist als Development-Default im Settings-Code vorhanden, echte `.env`-Werte werden hier nicht dokumentiert (`backend/app/config/settings.py:20`).

## API-Schicht

Backend-Router liegen in `backend/app/api/*` und werden gesammelt in `backend/app/main.py` eingebunden (`backend/app/main.py:12`, `backend/app/main.py:64`). Next.js BFF-Routen unter `app/api/*` forwarden oder proxyen an `FASTAPI_BRIDGE_URL` serverseitig, ohne diese URL als `NEXT_PUBLIC` auszugeben (`lib/bridge.ts:1`, `lib/bridge.ts:71`, `app/api/projects/route.ts:1`).

## Agenten-/LLM-Schicht

ModelGateway, Provider, Agent Registry, Prompt Assets und konkrete A1/A2/A3-Funktionen liegen unter `backend/app/agents/*` (`backend/app/agents/gateway.py:1`, `backend/app/agents/registry.py:1`, `backend/app/agents/providers/fake.py:1`, `backend/app/agents/fact_extraction.py:1`, `backend/app/agents/field_drafting.py:1`, `backend/app/agents/critic_review.py:1`). Die Registry enthält 13 Profile (`final_backend_contracts_v1_1/agents_v1_1.yaml:169`, `final_backend_contracts_v1_1/agents_v1_1.yaml:1325`).

## Export-/Dokumentgenerierung

Export-Artefakte werden als `ExportArtifact` persistiert und über Generatoren für DOCX, Markdown und Technical Evidence erzeugt (`backend/app/db/models.py:998`, `backend/app/exports/service.py:39`, `backend/app/exports/generators/docx.py:1`, `backend/app/exports/generators/markdown.py:3`, `backend/app/exports/generators/technical_evidence.py:1`).

## Wichtige Konfigurationsdateien

| Datei | Zweck | Status |
|---|---|---|
| `package.json` | Frontend-Skripte und Dependencies | Aktuell implementiert (`package.json:6`) |
| `next.config.mjs` | Next.js-Konfiguration | Aktuell implementiert |
| `tsconfig.json` | TypeScript-Konfiguration | Aktuell implementiert |
| `vitest.config.ts` | Vitest-Konfiguration | Aktuell implementiert |
| `playwright.config.ts` | Playwright-Konfiguration | Aktuell implementiert |
| `backend/requirements.txt` | Backend-Abhängigkeiten | Aktuell implementiert (`backend/requirements.txt:1`) |
| `backend/pytest.ini` | Pytest-Konfiguration | Aktuell implementiert |
| `backend/alembic.ini` | Alembic-Konfiguration | Aktuell implementiert |
| `final_backend_contracts_v1_1/*.yaml` | Contracts/Registries | Aktuell verwendet oder Zielarchitektur |

## Relevante Environment-Variablen ohne Werte

Nur Namen aus Code, keine Werte:

| Variable/Setting | Zweck | Codebeleg |
|---|---|---|
| `DATABASE_URL` / `database_url` | DB-Verbindung | `backend/app/config/settings.py:20` |
| `APP_ENV` / `app_env` | Environment | `backend/app/config/settings.py:21` |
| `SESSION_COOKIE_NAME` | Session Cookie | `backend/app/config/settings.py:37` |
| `ALLOWED_ORIGINS` | Origin-/CSRF-Guard | `backend/app/config/settings.py:43` |
| `FASTAPI_BRIDGE_URL` | Next.js BFF zu FastAPI | `lib/bridge.ts:71` |
| `APP_BACKEND_MODE` | Frontend live/mock Mode | `app/layout.tsx:19` |
| `ANTHROPIC_API_KEY` | Anthropic Direct Provider | `backend/app/config/settings.py:83` |
| `OPENAI_API_KEY` | OpenAI Direct Provider | `backend/app/config/settings.py:84` |
| `AGENT_INSTITUTIONAL_ROUTE_APPROVED` | Cloud-Agent-Gate | `backend/app/config/settings.py:87` |
| `AGENT_FAKE_PROVIDER` | Agent Fake Provider | `backend/app/config/settings.py:97` |
| `WEB_RESEARCH_ENABLED` | Public Web Research Gate | `backend/app/config/settings.py:103` |
| `FIRECRAWL_API_KEY` | Firecrawl Provider | `backend/app/config/settings.py:104` |
| `WEB_RESEARCH_FAKE_PROVIDER` | Web Fake Provider | `backend/app/config/settings.py:105` |
| `D2_WEB_RESEARCH_ENABLED` | D1/D2 Live-Web-Provider Gate | `backend/app/config/settings.py:110` |

Seed-Password-Settings existieren im Code, werden hier aber absichtlich nicht als Werte dokumentiert (`backend/app/config/settings.py:125`).

