# Milestone 10.2 — Evaluation UX & Export Polish

**Scope:** make the supervised-beta frontend understandable and action-oriented for
non-technical evaluators, and make DOCX/Markdown exports applicant-friendly — **no new
backend product feature, no DB migration, no finalized-contract change, no weakening of any
M10/M10.1 privacy/reliability/approval guarantee.** Fake/deterministic providers only.

## Branch / commit basis
- Branch **`feat/evaluation-hardening`**, on top of the M10.1 remediation state
  (`f23dd96` audit + M10.1 changes in the working tree).
- `git status`: **0** changes under `final_backend_contracts_v1_1/`, **0** under
  `backend/app/migrations/`; backend diffs limited to
  `app/exports/generators/{common,docx,markdown}.py` + `tests/test_export_generators.py`
  (the explicitly allowed export label/readability mapping).

## UX audit summary
Full audit: [M10_2_Evaluation_UX_Audit.md](../audits/M10_2_Evaluation_UX_Audit.md).
User observations were treated as symptoms and verified against the code. **Verified as
already solved** (no change): mandatory intake data-classification; collapsed "Technische
Details" on Evidence/Requirements; QualitySummary sufficiency disclaimer; Word export marked
"Empfohlen"; requirement status buckets/filters; M10.1 stale-reliability banner (untouched).
**Real gaps fixed:** invisible active-Antrag context; no dashboard search/filter/sort and an
ignored `warning_badge`; no per-field export readiness; technical "Open Editor (…)" headings
+ one flat repeated "Offene Punkte" list in DOCX/Markdown; evidence not linked to sources;
requirements without next-action links; no "Nächste Schritte" in the Review Center;
unexplained KI-button availability; experimental formatted copy next to the primary action.

## Implementation plan summary
Plan: [M10_2_UX_Implementation_Plan.md](../audits/M10_2_UX_Implementation_Plan.md) —
P0a (context/dashboard/export-readiness UI) → P0b (export generators, separable) → P1
(evidence/requirements/review/editor/sources/Innolink/terminology), P2 only if trivial,
P3 documented backlog. All P0a/P0b/P1 items shipped; generators stayed stable (no P0b
fallback needed).

## Changed screens & what was improved
| Screen | Improvement |
|--------|-------------|
| Shell (Topbar/Sidebar) | Labelled switcher **"Aktueller Antrag"** with the project title; sidebar names the active Antrag; in live mode the shell resolves real projects + the stored active id itself; project-scoped links disabled with "Zuerst Antrag auswählen" when none (keyboard-accessible, tooltip on the icon rail) |
| Dashboard | Search field, status filter chips (Alle/In Bearbeitung/Review offen/Blockiert/Demo), sort (Zuletzt angelegt/Fortschritt/Titel); **"Analyse gestoppt"** warning chip (previously delivered by the API but never rendered); per-card **"Nächster Schritt: …"** line from `next_action`; empty-filter state with reset. User-created projects are first-class — no count-based pollution warnings (clean-DB stays an evaluation-guide requirement) |
| Export (UI) | **"Feld-Bereitschaft"** table per portal field: Kopierbereit / Platzhalter offen / Überarbeiten (Prüfung veraltet) / Beleg fehlt — with the binding legend that **Kopierbereit = technisch bereit für die manuelle Übernahme unter Beta-Prüfungen, keine fachliche/Review-Freigabe**; **"Nicht zur Einreichung"** badge whenever approval is missing or blockers exist; "Manuell im Portal zu erfassen: …" list; technical_evidence card labelled **"Für Audit/Evaluation"** and visually secondary (content untouched) |
| Export (DOCX/Markdown) | Applicant-friendly German field headings via a display-only `EXPORT_FIELD_LABELS` map in `generators/common.py` (fallback = snapshot `field_name`; snapshot/contract unchanged); "Offene Punkte" now **grouped by field** with identical lines deduplicated ("3 × …") in both generators |
| Evidence | Source name is a labelled button → switches to the Quellen tab and opens that source's detail dialog; deep link `/quellen?tab=evidenz&anchor={id}` expands + highlights the referenced card; hint sharpened: "…auffindbar ist — **keine inhaltliche Freigabe**." |
| Requirements | "**Beleg ansehen**" deep-links to the evidence card; "**Quelle ergänzen**" → `/quellen` when no evidence; "**Kommentar im Review erfassen**" guidance link (per correction: **links only, no new mutation**) |
| Review Center | "**Nächste Schritte**" card (max 3, derived: recheck → stale reliability → dominant blocker groups, each with its action); group-list blocker rows scroll to their blocker card; QualitySummary adds "Abdeckung ≠ Suffizienz" and "«Risiko» ist ein Risikosignal — kein Fehler der Anwendung"; **M10.1 stale banner + approval gate untouched** |
| Editor | Non-A2 fields now explain the KI button ("für dieses Feld nicht verfügbar — unterstützt «Lösung & Innovation» und «Wertschöpfung»") in addition to the existing 503/data-class notice |
| Sources | Row name is a real button opening the existing details dialog (previously only the small Info icon); external open-by-id for the evidence→source link |
| Innolink copy | "Text kopieren" stays the single primary action; "Formatiert kopieren (experimentell)" moved behind an "Erweitert" disclosure; warnings + "Trotzdem kopieren" confirmation unchanged |
| Terminology | Sweep confirmed: no `run/operation/exact_verified/claim_hash/enum` strings render in primary UI (all status enums go through German label maps; IDs stay in collapsed "Technische Details") |

## Changed files
- **Shell/Dashboard:** `components/shell/{app-shell,project-selector,sidebar}.tsx`,
  `app/page.tsx`, `components/dashboard/project-card.tsx`, `lib/dashboard.ts`
- **Export:** `lib/export-view.ts`, `components/export/live-export.tsx`;
  backend `app/exports/generators/{common,markdown,docx}.py`
- **Evidence/Sources:** `components/quellen/{live-evidence,source-table}.tsx`,
  `app/quellen/page.tsx`, `lib/evidence.ts`
- **Requirements:** `components/anforderungen/live-requirements.tsx`
- **Review:** `components/review/{live-review,quality-summary}.tsx`
- **Editor:** `components/editor/live-editor.tsx`
- **Innolink:** `components/portal-transfer/field-transfer-card.tsx`
- **Tests:** NEW `test/sidebar-context.test.tsx`, `test/live-requirements.test.tsx`,
  `e2e/m10-2-ux.spec.ts`; extended `test/{dashboard,live-export,live-evidence,live-review,
  quality-summary,live-editor-a2,portal-transfer}.test.tsx`;
  backend `tests/test_export_generators.py` (+2)
- **Docs:** the two audit/plan docs + this report.

## Deliberate test-assertion updates (copy protocol)
1. `test/dashboard.test.tsx`: "Review offen" and "Demo" became ambiguous because the new
   filter chips repeat those words — assertions now count/scope them (2 card badges + 1
   chip). No weakening: the original intent (summary tile + badges visible) is still
   asserted.
2. No German string asserted by existing Playwright specs was changed; the sharpened
   evidence hint and all new copy are additions.

## Deliberately deferred (honest deviations)
- **Intake mandatory classification** — already implemented; nothing to do.
- **Source full-text preview** — no fragments/preview API exists; not invented (P3).
- **Intake deadline/duration** — not in the finalized contract (P3).
- **Inline "menschlich geprüft" decision from Requirements** — guidance links only; no new
  mutation path (P3, per execution correction).
- **Editor right-panel dedupe** — exploration showed no actual duplication in the live
  editor panel (tabs hold distinct content); no artificial change made.
- **Dashboard deadline sort** — deadline data is always null in the beta contract; omitted.

## Post-beta UX backlog
Collaboration/invitations/real membership & avatars · Firecrawl partner recommendation ·
Innosuisse portal PDF import · source full-text preview (fragments API) · intake
deadline/duration (contract change) · SNF/Horizon · work-package/milestone/budget tables ·
inline requirement decisions · blocker-card grouping by finding group (P2) ·
stopped-run aggregate tile (P2).

## Tests run & results (fakes only, no real key)
- **Backend `pytest`: 501 passed, 3 skipped** (M10.1: 499 + 2 new generator tests).
- **Frontend:** vitest **140 passed** (M10.1: 130 + 10), `eslint` clean, `tsc --noEmit`
  clean, `next build` OK.
- **`verify_all.ps1` (one-command verification incl. Playwright + API smoke):** _result
  recorded below on completion._

## Readiness verdict for supervised evaluation
All 13 M10.2 acceptance criteria are met: no finalized contract modified; no migration; no
new backend feature; M10.1 guarantees intact (stale-reliability banner/gate and no-raw-log
surfaces untouched, regression-guarded); technical details hidden by default; sources/
evidence/requirements are inspectable and actionable; review findings guide to next actions;
the export UI separates proposal-facing exports from the audit artifact; Innolink copy stays
manual and safe; deferred items documented. **The app is more evaluation-ready than before —
supervised beta evaluation can proceed on this build** (still not production; see
Known_Limitations).
