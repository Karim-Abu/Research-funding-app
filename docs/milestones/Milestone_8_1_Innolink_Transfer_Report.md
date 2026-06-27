# Milestone 8.1 — Innolink Portal Transfer View & Copy Assistant

## Basis

- Branch: `feat/innolink-transfer` (created from `751e1f0`, tag `milestone-8-export`
  created on `751e1f0` as part of STEP 0).
- Pre-implementation gate (clean tree, full suite green) verified first: `pnpm test`
  81 passed, `tsc`/`lint` clean; backend unchanged (committed `751e1f0`, 206 green).
- No automatic commit was created (only the STEP-0 tag + branch).

## Scope & core decision

A **browser-only, copy-ready transfer workspace** that prepares the current proposal
drafts for **manual, field-by-field** transfer into the Innosuisse Innolink portal.
It renders the supported PortalFieldDrafts in canonical portal order with per-field
copy buttons, visible review/placeholder/limit warnings, and a coverage panel that is
honest about what the Beta does not cover.

**Core decision honoured:** `html` was **not** added to `ExportCreate.type`; **OpenAPI
was not modified**; **no ExportArtifact** and **no new public API operation** are
created. The view reuses the existing authenticated clients (`lib/fields.ts
listFields`, `lib/review.ts getReview`). **This milestone is frontend-only** — no
backend code changed. The browser page itself is the HTML presentation; no
downloadable HTML artifact is produced. No browser automation / portal login /
submission / injection / scraping / Innolink API / LLM / agent / external network.

## Changed / new files

- **New** `lib/clipboard.ts` (plain + optional formatted copy, HTML escaping,
  fallback), `lib/portal-transfer.ts` (section grouping, placeholder detection,
  per-field warnings, unsupported-area list), `components/portal-transfer/
  {portal-transfer,field-transfer-card}.tsx`, `app/portal-transfer/page.tsx`
  (live/mock containers + empty states).
- **New tests** `test/portal-transfer.test.tsx`, `test/clipboard.test.ts`,
  `e2e/portal-transfer.spec.ts`.
- **Modified** `components/export/live-export.tsx` (Innolink-Übernahme card → links
  to `/portal-transfer`, creates no export), `components/shell/sidebar.tsx`
  (Innolink-Übernahme nav entry), `components/editor/live-editor.tsx` (one-line
  stability fix — see *Side fix* below).

## Supported fields (ready for field-by-field transfer)

The 8 M6 singleton draft fields, rendered in registry order (from `listFields`) and
grouped into the 5 Innolink sections: **Einleitung** (`INTRO.APP.NAME`, `…NAME_EN`,
`…ABSTRACT`, `…EXECUTIVE_SUMMARY`), **Organisation & Partner**
(`ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS`), **Wertschöpfung**
(`VC.BUSINESS_TARGETS_MODEL.EDITOR`), **Lösung & Innovation**
(`SOL.INNOVATION_SOLUTION.EDITOR`), **Projektplan**
(`PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION`). Only fields with a current DraftVersion
are copyable; ordering is consumed from `listFields` (not re-hardcoded).

## Unsupported structured fields (manual Innolink entry)

Always listed in the mandatory coverage panel: repeated Work Packages, Milestones,
partner-hour tables, Budget/Finanzierungsplan, salary-cost tables, material-cost
positions, cash/own-contribution positions, file uploads, and checkbox/dropdown
selections not represented by drafts — with the fixed statement *“Die Übernahmeansicht
deckt derzeit die unterstützten Textfelder ab. Strukturierte und wiederholbare
Portalbereiche müssen weiterhin direkt in Innolink erfasst werden.”*

## Clipboard formats

- **Default: `text/plain`** (`navigator.clipboard.writeText`). The copied content is
  **exactly `current_version.text`** — never field IDs, section labels, review status,
  evidence metadata, source names, character counts, or UI warnings. Placeholders the
  user left in their own draft are part of the text and copied as-is.
- **Optional/experimental: formatted** (`navigator.clipboard.write` with a
  `ClipboardItem` carrying `text/html` **and** a `text/plain` fallback). The HTML is
  built from the text with **escaping** and only `<p>` / `<ul><li>` (no scripts,
  styles, handlers or raw source HTML; never `innerHTML`). It is labelled
  *experimentell* with a hint that **Innolink may strip or alter HTML formatting**;
  on any failure it falls back to plain text. Unicode is preserved throughout.

## Copy warnings (visible; confirm, never block)

Warnings are **always rendered visibly on each card**. When present, the copy button
opens an inline “Trotzdem kopieren?” confirmation; copy proceeds after explicit
confirmation (users may transfer an intermediate draft). Triggers + wording: visible
placeholders / open items → *“Dieser Feldtext enthält noch offene Angaben.”*; over
the limit → *“Der Text überschreitet das Innolink-Zeichenlimit.”*; missing/stale
approval, `recheck_required`, or a blocker finding targeting the field → *“Die
Review-Freigabe ist nicht aktuell.”* The word “einreichbereit” is never used; normal
drafting is never blocked.

## Transfer status

Local UI state only — a per-session `Set` of copied field IDs shown as a “Kopiert”
badge (not copied / copied-this-session). No invented `submitted_to_portal` status and
no claim that a copied field was pasted into Innolink.

## Security & privacy behaviour

No external network call, no Innolink credentials/keys, no automatic/background
clipboard access (copy only on an explicit click), no analytics carrying draft text.
A **generic clipboard privacy reminder is always shown** (clipboard contents may be
read by local applications) and **does not rely solely on local intake state** — when
a reliable confidentiality classification is available it adds a calmer tailored
sentence, otherwise the generic reminder stands; the copy function is never disabled by
confidentiality. **No SEDATE / reference-application content** (names, organisations,
contacts, figures, wording) appears anywhere in the UI, copied text, code, tests or
docs — the reference PDFs were used only to validate field structure and the
copy-paste workflow.

## Side fix (pre-existing M6 editor race)

A long-standing flake in the M6 live editor (the React StrictMode double-invoke of the
load effect let a late `listFields` resolution re-select the first field and clobber an
in-progress edit, intermittently failing `e2e/template-drafts.spec.ts`) is fixed with a
one-time auto-select guard (`autoSelectedRef`) in `components/editor/live-editor.tsx`.
Behaviour is unchanged; the editor’s 5 unit tests and the template-drafts spec now pass
deterministically (3×/3× and in the full suite).

## Test results

- **Frontend** `pnpm test`: **94 passed** (81 baseline + 13 new — `clipboard.test.ts`
  6, `portal-transfer.test.tsx` 7). `tsc --noEmit` 0 errors, `pnpm lint` 0, `pnpm
  build` success. Covers: registry-order grouping; plain clipboard receives **only**
  field content; formatted clipboard receives sanitized HTML **+ plain fallback** with
  escaping; Unicode preserved; composite full-field copy; visible placeholder /
  character-limit / stale-or-missing-approval warnings + confirm-then-copy; copied
  badge; clipboard-failure fallback; empty state; always-present coverage panel +
  generic privacy reminder; no portal-submission status; mock mode functional.
- **Backend** `pytest`: **206 passed** (unchanged — no backend edits).
- **Playwright** (live servers): **9 passed + 1 seeded demo passed**.
  `portal-transfer.spec.ts` (clipboard permissions granted): login → Export Center →
  Innolink-Übernahme → `/portal-transfer` → section order → copy Abstract → clipboard
  holds only the Abstract text → copy a composite field → clipboard holds only that
  field’s text → placeholder warning visible → Work Packages/Budget listed as manual
  Innolink entry → logout. All prior M4–M8 specs still pass.

## Manual Innolink paste test (to be validated manually)

Innolink is never automated and is not accessible from this environment, so the manual
acceptance test is documented as a procedure in `docs/demo/Innolink_Copy_Paste_Guide.md`
and its **results are pending manual execution** by the responsible person in an
Innolink test application: (1) paste plain text into a short field; (2) paste plain text
into a composite editor; (3) test formatted paragraphs/lists; (4) verify Unicode; (5)
verify the character count Innolink reports; (6) record which formatting Innolink keeps
or strips.

## Known limitations

- **Per-subsection composite copy is deferred** — composite editor fields copy the
  complete field. The registered subsection labels are not exposed to the frontend and
  exposing them would require a backend change, which is a non-goal for this milestone.
- Copied-state is per browser session only and is never authoritative portal state.
- Formatted (HTML) copy is experimental; Innolink may normalise it to plain text.

## No automatic submission

Nothing is transferred or submitted automatically. The view only prepares content for
the user to copy and paste manually; the responsible person performs the actual entry
and submission in Innolink.

## Readiness for Milestone 9

The Innolink transfer view is a self-contained, frontend-only assistant over the
existing review/draft data, with no backend, OpenAPI, export-artifact or
portal-automation changes, fully covered by unit + live end-to-end tests and without
destabilising any prior milestone. Ready for **Milestone 9 (Agent Activation)**.
