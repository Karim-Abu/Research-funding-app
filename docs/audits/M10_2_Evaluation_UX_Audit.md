# M10.2 — Evaluation UX Audit

**Date:** 2026-07-02 · **Basis:** branch `feat/evaluation-hardening` (M10.1 remediated,
verify_all ALL GREEN). **Method:** code inspection of all frontend routes/components
(`app/`, `components/`, `lib/`), review-package/evidence/source DTOs, export generators
(`backend/app/exports/`), the vitest + Playwright suites, and the M10/M10.1/evaluation docs.
User observations were treated as **symptoms** and verified against the code; several are
already solved and are marked so.

**Priorities:** P0 = evaluation blocker · P1 = should fix before evaluation · P2 =
nice-to-have if cheap · P3 = post-beta. **Risk:** low/medium/high implementation risk.
"Backend?" = whether any backend/API/contract change would be required.

**Binding constraints for all fixes:** no finalized-contract change, no DB migration, no new
backend feature (backend only minor export/label mapping), no weakening of M10.1
stale-reliability / no-raw-log guarantees, accessibility (keyboard + non-color-only badges),
copy changes checked against existing test assertions first.

---

## 1. Dashboard (`app/page.tsx`, `components/dashboard/*`)

| # | Problem | Root cause | Evaluation impact | Proposed improvement | Prio | Risk | Backend? |
|---|---------|-----------|-------------------|----------------------|------|------|----------|
| 1.1 | No search/filter/sort — with a user-created third project (normal, not pollution) the evaluator cannot orient | Layout gap: page renders a flat grid of all cards | Evaluator loses the two demo projects among others; time wasted | Client-side search box, status filter chips (Alle/In Bearbeitung/Review offen/Blockiert/Demo), sort (Zuletzt angelegt/Fortschritt/Titel) | **P0** | low | No |
| 1.2 | `warning_badge: "run_stopped"` is delivered by the API (`WorkflowSummaryDto`) but never rendered | Missing display of existing data (`lib/projects.ts` maps it; card ignores it) | A stopped analysis is invisible → evaluator thinks the app hangs | "Analyse gestoppt" chip on the card (text label, not color-only) | **P0** | low | No |
| 1.3 | Next action is a generic "Weiterarbeiten" button | Copy: `ACTION_ROUTES` exists with 8 next_action values, but the label never changes | "What should I do next?" unanswered | Action-specific button label from `next_action` (e.g. "Quellen hochladen", "Analyse prüfen", "Entwurf fortsetzen") — keep "Weiterarbeiten" as fallback; check e2e `demo-dataset.spec.ts` assertions first | P1 | low | No |
| 1.4 | Demo badge exists; user feared >2 projects = DB pollution | Not a defect: title-suffix detection works; user projects are legitimate | Misdiagnosis risk during sessions | No count-based warnings (per correction 3); filters solve orientation; clean-DB stays a guide requirement | — (verified OK) | — | No |
| 1.5 | Collaboration/invitations/avatars | Feature does not exist (avatars are display-only) | None for evaluation | **P3 post-beta** (auth-model change) | P3 | — | Yes (auth) |

## 2. Sidebar / project context (`components/shell/{sidebar,topbar,project-selector}.tsx`)

| # | Problem | Root cause | Impact | Improvement | Prio | Risk | Backend? |
|---|---------|-----------|--------|-------------|------|------|----------|
| 2.1 | Which Antrag is active is invisible: topbar `ProjectSelector` is an unlabeled dropdown ("Projekt"), sidebar section "Aktueller Antrag" never names the project | Missing display of existing state (`sessionStorage rf_active_project_id` + loaded project list) | Evaluator edits/reviews the wrong Antrag without noticing — trust damage | Topbar becomes a labelled switcher "Aktueller Antrag: <Titel>" writing `setActiveProjectId`; sidebar section shows the active title | **P0** | low–medium (no sidebar tests exist) | No |
| 2.2 | Project links clickable with no project selected → pages degrade with different ad-hoc alerts | Missing guard; each page has its own fallback | Confusing dead-ends | Disable project-scoped links (with accessible hint "Zuerst Antrag auswählen") when no active project | **P0** | low | No |
| 2.3 | "Evidenz" navigates to `/quellen?tab=evidenz` — sidebar item looks like a page but lands on a tab named "Quellen/Evidenz" | Navigation/label mismatch | The Evidence≠Sources confusion the user reported | Keep route; make tab state reflect the query param clearly + heading "Belege & Fundstellen" inside the tab (copy check vs e2e first) | P1 | low | No |

## 3. Intake (`components/intake/intake-form.tsx`)

| # | Problem | Root cause | Impact | Improvement | Prio | Risk | Backend? |
|---|---------|-----------|--------|-------------|------|------|----------|
| 3.1 | "Classification should be mandatory" | **Already solved:** `vertraulichkeit` is required + validated before submit | None | Verify only; minor helper copy | — (verified OK) | — | No |
| 3.2 | Deadline / project duration capture | **Not in the API contract** (`ProjectCreatePayload` has no deadline/duration) | Cards show "Frist: offen" | **P3 post-beta** (contract/model change). Budget (`budget_framework_chf`) IS supported and captured | P3 | — | Yes (contract) |
| 3.3 | Partner section clarity | Copy only | Low | Small helper text ("Umsetzungspartner erforderlich; beitragsberechtigter Forschungspartner …") | P2 | low | No |
| 3.4 | Partner recommendation via web research | New tool/privacy flow | — | **P3 post-beta** per spec | P3 | — | Yes |

## 4. Sources (`components/quellen/source-table.tsx`, `app/quellen/page.tsx`)

| # | Problem | Root cause | Impact | Improvement | Prio | Risk | Backend? |
|---|---------|-----------|--------|-------------|------|------|----------|
| 4.1 | Rows not clickable; no way to inspect a source | Missing link/detail UI; `SourceDocumentDto` has name/type/status/classification/created/error but **no fragment/preview text** and no fragments API | Evaluator cannot answer "what is in this source?" | Keyboard-accessible row → detail drawer from **existing** fields + linked-evidence count (anchors filtered by `source_id`); technical metadata collapsed | P1 | low | No |
| 4.2 | Full readable source preview | **API limitation** — no fragments/preview endpoint; inventing one is out of scope | — | **P3 post-beta** (needs new API surface) | P3 | — | Yes |
| 4.3 | Status/errors partially technical | Copy | Low | User-language status texts in the drawer; keep table labels (asserted in tests) | P2 | low | No |

## 5. Evidence (`components/quellen/live-evidence.tsx`)

| # | Problem | Root cause | Impact | Improvement | Prio | Risk | Backend? |
|---|---------|-----------|--------|-------------|------|------|----------|
| 5.1 | "Fundstelle bestätigt" reads like factual approval | Copy: no explainer near the badge | **Overclaiming risk** — core evaluation concern (coverage ≠ sufficiency family) | One-line explainer: "Fundstelle bestätigt = Textstelle in der Quelle gefunden — keine inhaltliche Freigabe." | **P1 (highest)** | low | No |
| 5.2 | Anchor does not link to its source | Missing link; `source_id`/`source_name` present; Sources tab is on the SAME page | "Where is the source?" needs manual searching | Source name becomes a button → switches to Quellen tab + highlights/focuses the row | P1 | low | No |
| 5.3 | No deep-link target for requirement→evidence | Missing anchor-id handling | Requirements can't link here | Support `/quellen?tab=evidenz&anchor={id}` → scroll/expand that card | P1 | low | No |
| 5.4 | Technical details dominate | **Already solved:** match_type/normalizer/offsets are inside collapsed "Technische Details" | None | Verify only | — (verified OK) | — | No |

## 6. Requirements (`components/anforderungen/live-requirements.tsx`)

| # | Problem | Root cause | Impact | Improvement | Prio | Risk | Backend? |
|---|---------|-----------|--------|-------------|------|------|----------|
| 6.1 | "Beleg vorhanden" is dead text | Missing link; `evidence_links[].anchor_id` is available | "Where is the evidence?" unanswered | Chip → "Beleg ansehen" linking to `?tab=evidenz&anchor={first anchor}` | P1 | low | No |
| 6.2 | "Kein Beleg" has no next action | Missing CTA | "What should I do?" unanswered | CTA "Quelle ergänzen" → `/quellen` | P1 | low | No |
| 6.3 | "Noch nicht menschlich geprüft" offers nothing | No inline decision UI; M7 decisions API exists but is untested from this screen | Evaluator stuck | **Guidance links only** (correction 4): "Im Review prüfen" / "Kommentar im Review erfassen" → `/review`; inline writes = P3 | P1 | low | No |
| 6.4 | Grouping is by machine status, not user question | Layout/copy | Harder triage | Buckets: Blockiert / Angaben fehlen / Beleg fehlt / Prüfung nötig / Erfüllt (mapped from status+evidence) | P1 | low | No |
| 6.5 | requirement_id/basis technical | **Already solved:** collapsed "Technische Details" | None | Verify only | — | — | No |

## 7. Draft editor (`components/editor/{live-editor,assistant-panel}.tsx`)

| # | Problem | Root cause | Impact | Improvement | Prio | Risk | Backend? |
|---|---------|-----------|--------|-------------|------|------|----------|
| 7.1 | "KI-Vorschlag erstellen" availability unexplained | Gating is `isA2Field()` + backend 503; only the 503 case has a notice (`AI_LIVE_NOTICE`) | Evaluator reads silence as breakage | Explain all states: non-A2 field → "Für dieses Feld nicht verfügbar"; deterministic run → "Im deterministischen Modus deaktiviert"; 503 → existing notice | P1 | low | No |
| 7.2 | Right panel noisy/repetitive | Repeated identical hints not deduped (Review Center already has `dedupeFindings`) | Cognitive load | Reuse `dedupeFindings` ("N × …") in the panel lists | P1 | low | No |
| 7.3 | Portal PDF import | Needs parser/mapping backend | — | **P3 post-beta** per spec | P3 | — | Yes |

## 8. Review Center (`components/review/*`)

| # | Problem | Root cause | Impact | Improvement | Prio | Risk | Backend? |
|---|---------|-----------|--------|-------------|------|------|----------|
| 8.1 | No "what next?" summary | Missing derivation from existing package data | Core evaluator question unanswered | "Nächste Schritte" card: top 3 from recheck_required / stale reliability / dominant blocker groups, each with its action link | **P1 (highest)** | low | No |
| 8.2 | Findings in group lists don't navigate | Only `jumpToFirstBlocker` exists | Dead-ends | Group-list rows link/scroll to their blocker card; blocker cards already link to `/editor` | P1 | low | No |
| 8.3 | Coverage vs sufficiency explanation | Partially solved: QualitySummary explains sufficiency; **coverage line + "risky = Risikosignal, kein App-Fehler" missing** | Misreading `risky` | Add both one-liners to QualitySummary | P1 | low | No |
| 8.4 | M10.1 stale banner | **Working as designed** (`reliability-stale-banner`, approval-blocking) | — | Keep untouched; regression-guard in tests | — (keep) | — | No |
| 8.5 | Duplicate blocker lists | Partially solved (`dedupeFindings` on hints); blocker cards can repeat per field | Noise | Group blocker cards by finding group; count badge | P2 | low | No |

## 9. Export / Innolink (`components/export/*`, `components/portal-transfer/*`, `backend/app/exports/generators/*`)

| # | Problem | Root cause | Impact | Improvement | Prio | Risk | Backend? |
|---|---------|-----------|--------|-------------|------|------|----------|
| 9.1 | No per-field readiness overview | Missing UI; data present (`listFields` + `ReviewPackageDto` + placeholder regex already fetched by `live-export.tsx`) | "What is copy-ready?" unanswered — the export page's core question | "Feld-Bereitschaft" table: **Kopierbereit / Platzhalter offen / Überarbeiten (Prüfung veraltet) / Beleg fehlt / Manuell im Portal zu erfassen** + legend that Kopierbereit ≠ fachliche/Review-Freigabe; "Nicht zur Einreichung" shown whenever approval missing or blockers exist | **P0** | low | No |
| 9.2 | DOCX/Markdown field headings use registry `label_or_question` (e.g. "Open Editor (Business Targets & Business Model)") baked into snapshot `field_name` | Label mapping missing in generators | Exports look technical/English | field_id→friendly-German-label map in `generators/common.py` (fallback `field_name`); explicitly allowed "minor export label mapping" | **P0b** | low–medium | Yes (allowed mapping only) |
| 9.3 | "Offene Punkte" is a flat repeated list in Markdown/DOCX | Generators render one flat list | Repetitive, hard to act on | Group by field label + dedupe identical descriptions ("3 × …") | **P0b** | low–medium | Yes (allowed) |
| 9.4 | technical_evidence prominence | Partially solved (card order); needs explicit audit labelling | Evaluator confusion about audience | Label "Für Audit/Evaluation — nicht Teil des Antrags"; visually secondary; **content untouched** (correction 7) | P1 | low | No |
| 9.5 | "Formatiert kopieren (experimentell)" sits beside the primary action | Layout | Risky-looking primary path | Move behind an "Erweitert" disclosure; "Text kopieren" stays primary; asserted strings kept | P1 | low | No |
| 9.6 | Word/Markdown hierarchy | **Already solved** (Word "Empfohlen" leading card) | — | Verify only | — | — | No |

## 10. Copy & terminology (cross-cutting)

- Preferred glossary (Antrag, Entwurf, Quelle, Fundstelle, Beleg, Prüfung nötig, Blockiert,
  Zu prüfen, Kopierbereit, Überarbeiten, Qualitätsprüfung, Technischer Nachweis, Nicht zur
  Einreichung) is largely in place; sweep target = no `run/operation/exact_verified/
  claim_hash/scope-hash/enum/internal-ID` leaks in primary UI (IDs stay in collapsed
  "Technische Details"). **Prio P1, risk low, no backend.**
- **Test-assertion register (do-not-break without deliberate update):** "Weiterarbeiten",
  status badges ("In Bearbeitung", "Review offen", "Blockiert", "Eingereicht"),
  "Fördervoraussetzungen", "Partner & Rollen", "Strukturvorlage", "Fundstelle bestätigt",
  "Word-Arbeitsdokument", "Text kopieren", "Trotzdem kopieren", "Kopiert", "Qualitätsprüfung"
  (heading), "ungeprüfte Änderungen", "Qualitätsprüfung veraltet" (M10.1 banner). Any
  deliberate change must update the exact tests and be listed in the M10.2 report.

## Test-coverage gaps relevant to this milestone
No vitest coverage today for: sidebar/topbar context, intake form UI, live requirements
screen, export screen layout. New tests accompany each implemented item (see plan doc).

## Summary counts
- **P0:** 3 UI items (1.1, 1.2, 2.1+2.2 as one context item, 9.1) + **P0b:** 2 generator
  items (9.2, 9.3).
- **P1:** 5.1–5.3, 6.1–6.4, 7.1–7.2, 8.1–8.3, 9.4–9.5, terminology sweep, 1.3, 2.3, 4.1.
- **Verified already-solved:** 3.1, 5.4, 6.5, 8.4, 9.6 (+1.4 clarified as non-issue).
- **P3 (post-beta, honest deferrals):** 1.5 collaboration, 3.2 deadline/duration (contract),
  3.4 partner recommendation, 4.2 source full-text preview (API), 7.3 PDF import, inline
  requirement decision writes.
