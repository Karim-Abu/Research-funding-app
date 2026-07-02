# M10.2 — UX Implementation Plan

Derived from [M10_2_Evaluation_UX_Audit.md](M10_2_Evaluation_UX_Audit.md). Implements
P0a/P0b/P1 (+P2 only if trivially safe); P3 is documented backlog. Constraints: no
finalized-contract change, no migration, no new backend feature (backend limited to the
allowed export label/grouping mapping), no weakening of M10.1 guarantees, accessibility on
all new interactions, copy changes gated by the test-assertion register.

## P0a — evaluation blockers (navigation/context/dashboard/export UI)

| Item | Change | Files | Tests |
|------|--------|-------|-------|
| A1 Active-Antrag context | Topbar selector labelled "Aktueller Antrag", writes `setActiveProjectId`; sidebar section shows active project title; project-scoped links disabled + hint when none | `components/shell/{topbar,project-selector,sidebar}.tsx`, `components/app-shell.tsx` (wiring), `lib/intake-store.ts` (reuse) | NEW `test/sidebar-context.test.tsx` |
| A2 Dashboard orientation | Search input + status filter chips (Alle/In Bearbeitung/Review offen/Blockiert/Demo) + sort (Zuletzt angelegt/Fortschritt/Titel); render `warning_badge` as "Analyse gestoppt" chip | `app/page.tsx`, `components/dashboard/project-card.tsx`, `lib/dashboard.ts` | extend `test/dashboard.test.tsx` |
| A3 Export readiness | "Feld-Bereitschaft" table (Kopierbereit / Platzhalter offen / Überarbeiten (Prüfung veraltet) / Beleg fehlt / Manuell im Portal zu erfassen) from `listFields` + review package + placeholder regex; legend: Kopierbereit = technisch kopierbereit unter Beta-Prüfungen, **keine** fachliche/Review-Freigabe; "Nicht zur Einreichung" visible whenever approval missing or blockers exist | `lib/export-readiness.ts` (new helper) or extend `lib/portal-transfer.ts`, `components/export/live-export.tsx`, `export-screen.tsx` | extend `test/live-export.test.tsx` |

## P0b — export generator readability (separable)

| Item | Change | Files | Tests |
|------|--------|-------|-------|
| B1 Friendly field labels | `EXPORT_FIELD_LABELS: dict[field_id, str]` (German, mirrored from registry semantics without "Open Editor (...)"), fallback = snapshot `field_name`; used for DOCX headings + Markdown sections | `backend/app/exports/generators/common.py`, `markdown.py`, `docx.py` | extend backend export tests |
| B2 Grouped Offene Punkte | Group issues/findings by field label ("Ohne Feldzuordnung" bucket), dedupe identical descriptions with count | same generator files | same |

Fallback: if B1/B2 destabilize exports, ship P0a+P1 and report generators separately
(user correction 1). technical_evidence generator untouched.

## P1 — high-value polish

| Item | Change | Files | Tests |
|------|--------|-------|-------|
| C1 Evidence explainer + source link + deep link | Explainer under badge ("Fundstelle bestätigt = Textstelle in der Quelle gefunden — keine inhaltliche Freigabe."); source-name button → Quellen tab + row highlight; handle `?tab=evidenz&anchor={id}` scroll/expand | `components/quellen/live-evidence.tsx`, `app/quellen/page.tsx` | extend `test/live-evidence.test.tsx` |
| C2 Requirements actionability | "Beleg ansehen" → `?tab=evidenz&anchor=`; "Quelle ergänzen" → `/quellen`; guidance "Im Review prüfen"/"Kommentar im Review erfassen" → `/review` (links only, no mutation); user buckets Blockiert/Angaben fehlen/Beleg fehlt/Prüfung nötig/Erfüllt | `components/anforderungen/live-requirements.tsx` | NEW `test/live-requirements.test.tsx` |
| C3 Review next actions + links + wording | "Nächste Schritte" card (recheck → stale reliability → top blocker groups, max 3, each with link); group rows scroll to blocker cards; QualitySummary adds "Abdeckung ≠ Suffizienz" + "risky = Risikosignal, kein App-Fehler" | `components/review/live-review.tsx`, `quality-summary.tsx`, `lib/review-view.ts` | extend `test/live-review.test.tsx`, `test/quality-summary.test.tsx` |
| C4 Editor KI-clarity + dedupe | Availability notices (non-A2 field / deterministic run / 503) + `dedupeFindings` in panel lists | `components/editor/{live-editor,assistant-panel}.tsx`, `lib/draft-ai-actions.ts` | extend `test/live-editor-a2.test.tsx` |
| C5 Sources drawer | Keyboard-accessible row → drawer (existing fields + linked-evidence count; tech details collapsed) | `components/quellen/source-table.tsx` (+ small drawer) | extend `test/source-table.test.tsx` |
| C6 Innolink hierarchy | "Formatiert kopieren (experimentell)" behind "Erweitert" disclosure; "Text kopieren" primary | `components/portal-transfer/field-transfer-card.tsx` | extend `test/portal-transfer.test.tsx` |
| C7 Terminology sweep | Primary-UI glossary sweep; no technical enum/ID leaks outside collapsed sections | small copy diffs across components | covered by suites |
| C8 technical_evidence framing | "Für Audit/Evaluation — nicht Teil des Antrags" labelling, visually secondary; content untouched | `components/export/export-screen.tsx` | extend `test/live-export.test.tsx` |

Playwright: NEW `e2e/m10-2-ux.spec.ts` (dashboard search/filter incl. an extra user project;
evidence→source nav; requirement CTA; review next-actions; export readiness overview; no
provider branding). Existing specs stay green.

## P2 (only if trivial during implementation)
Stopped-run aggregate tile; drawer evidence-link list; quote scroll-into-view.

## P3 — post-beta backlog (not built)
Collaboration/invitations/avatars · partner recommendation (new tool/privacy flow) ·
Innosuisse portal PDF import (parser backend) · source full-text preview (fragments API) ·
intake deadline/duration (contract change) · SNF/Horizon · work-package/milestone/budget
tables · inline requirement human-decision writes from the requirements screen.

## Deliberate deviations from the user's suggestion list
1. **Intake mandatory classification** — already implemented+validated; no change.
2. **Source preview** — deferred (P3): no fragments/preview API exists and inventing one is
   out of scope; drawer ships with existing data instead.
3. **Deadline/duration in intake** — deferred (P3): not in the finalized contract.
4. **Requirement "menschlich geprüft" action** — guidance links instead of inline mutation
   (no tested endpoint from this screen; correction 4).
5. **Dashboard pollution warnings** — rejected: user-created projects are normal; filters
   solve orientation; clean-DB stays an evaluation-guide requirement (correction 3).

## Order of work
Audit doc → this plan → A1→A2→A3 → B1+B2 → C1…C8 → e2e spec → full verification
(backend pytest; pnpm test/lint/tsc/build; Playwright; verify_all.ps1) → milestone report.
No commit.
