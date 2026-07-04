CLAUDE.md — Project Rules for Research Funding App 0. Purpose

This file defines how Claude Code must work in this repository.

The goal is not fast random coding. The goal is professional, controlled, testable implementation for a Bachelor thesis MVP.

Bias toward:

correctness over speed
clarity over cleverness
small changes over broad rewrites
user value over technical showmanship
maintainability over speculative flexibility

Use judgment for trivial tasks, but do not ignore these rules for non-trivial UI, backend, API, data, security or architecture work.

1. Project Context

This project is a Next.js / TypeScript application for an Innosuisse proposal-support system.

The product is a field-based proposal assistant for Research Funding / Innosuisse applications.

It is not:

a technical multi-agent debugger
a free-form chatbot
an autonomous proposal generator
an automatic Innolink submission tool
a system that makes funding decisions

Primary users:

non-technical proposal teams
researchers
project leads
reviewers
research support staff

The UI must be:

calm
understandable
professional
action-oriented
usable for long proposal texts
clear about what the system knows, does not know and requires humans to verify

The system must support:

portal-field-based proposal drafting
evidence anchoring
human-in-the-loop review
quality checks
export / manual copy-paste support
no automatic portal write-back 2. Non-Negotiable Rules
Backend / API / Data Contracts
Do not change backend/API contracts without explicit approval.
Do not change DTO shapes, route contracts, database schemas or server behavior unless the task explicitly asks for it.
If a frontend need conflicts with the current API, adapt in the frontend with a view model or fallback first.
If a backend change would be better, propose it as a separate follow-up, do not silently implement it.
Dependencies
Do not add new dependencies without explaining why and asking first.
Prefer existing components, existing helpers and shadcn/ui patterns.
Do not introduce a library for something that can be solved safely with existing code.
For UI, prefer shadcn/ui components before creating custom complex components.
Technical Details in UI

Never show these in the standard user interface:

raw IDs
raw enums
source_id
field_id
run_id
review_package_version
normalizer
offsets
chunk_id
JSON payloads
internal actor IDs
backend status keys
raw stack traces
"Open Editor" as a user-facing field name
E2E / M6 / M8 / test project names in visible demo UI

Technical details may only appear inside a collapsed section titled:

Technische Details
Human-in-the-loop
KI suggestions must never be applied automatically.
The user must explicitly accept, reject or edit KI suggestions.
Human review remains the final authority for:
eligibility
budget
evidence
market claims
innovation claims
final proposal text
export readiness
The UI must not imply that the system decides whether funding will be granted.
Innolink / Export
Never imply automatic Innolink submission.
Never imply automatic portal synchronization.
Use wording such as:
manuell übernehmen
kopieren
Kopieransicht
für Innolink vorbereiten
Avoid wording such as:
automatisch übertragen
synchronisieren
einreichen
Portal-Writeback 3. Behavioral Guidelines
Think Before Coding

Before implementing non-trivial changes:

State your assumptions.
Identify ambiguity.
Mention trade-offs.
If multiple interpretations exist, present them.
If the request is unclear, stop and ask.
If a simpler approach exists, say so.
Push back if the requested implementation is likely to create regressions, overengineering or misleading UX.

Do not hide uncertainty.

Simplicity First

Implement the minimum code that solves the actual problem.

Avoid:

speculative features
abstractions for single-use code
configurability that was not requested
broad rewrites for small UI changes
defensive error handling for impossible scenarios
duplicate helper layers that do the same thing
200 lines when 50 lines would solve it

Before finalizing, ask:
"Would a senior engineer consider this overcomplicated?"

If yes, simplify.

Surgical Changes

When editing existing code:

Touch only files required for the task.
Do not reformat unrelated code.
Do not refactor adjacent code unless necessary.
Do not rename files, routes or components unless asked.
Match existing style and conventions.
Remove imports, variables or functions that your change made unused.
Do not remove pre-existing dead code unless asked.
If you notice unrelated problems, list them as TODOs instead of changing them.

Every changed line must trace back to the user's request.

Goal-Driven Execution

For every non-trivial task, define success criteria.

Examples:

"Fix disabled button UX" means: disabled buttons explain why they are disabled.
"Improve editor layout" means: long text fields have sufficient writing space and tests still pass.
"Refactor labels" means: no raw backend labels appear in standard UI.

For multi-step work, use this structure:

Step: [what you change]
Verify: [how you check it]
Step: [what you change]
Verify: [how you check it]
Step: [what you change]
Verify: [how you check it]

Loop until the defined verification passes.

4. Professional Autonomy

You should use logical initiative when it adds clear value.

Allowed:

point out a UX issue the user did not mention
propose a simpler implementation
propose a safer phased approach
add missing accessibility labels if directly related
improve obviously confusing copy if it is in the touched area
create a small helper if it removes duplication across touched files
document larger adjacent problems as TODOs

Not allowed without approval:

changing API contracts
adding dependencies
rewriting whole screens when asked for a small fix
changing routing structure
changing backend persistence
changing security/data-classification behavior
implementing speculative future features
deleting unrelated code
silently altering test expectations to hide regressions

If you find a high-value issue outside the current scope:

mention it
classify it as P0 / P1 / P2
do not implement it unless approved 5. UX Principles

The product must be understandable for non-technical users.

General UX
Every screen needs one clear primary action.
Every empty state needs:
explanation
next action
no technical wording
Every error state needs:
what happened
what the user can do next
optional details behind disclosure
Disabled buttons must explain why they are disabled.
Avoid dense screens with too many equally prominent panels.
Prefer progressive disclosure.
Prefer clear sectioning over large tables when users need to act.
Use tables only when comparison is the task. 6. Status Language

Use consistent meaning:

Erfüllt = requirement status
Verifiziert / Fundstelle bestätigt = evidence status
Bereit = field or export readiness
Prüfung nötig = human review needed
Blocker = user must resolve before approval/export
Offen = not completed or not checked
Teilweise = partial evidence or partial fulfillment

Status colors:

Green = Erfüllt / Verifiziert / Bestanden / Bereit
Orange = Teilweise / Prüfung nötig / Review veraltet
Red = Blocker / Fehler / Nicht bestanden
Gray = Offen / Nicht gestartet / Nicht geprüft
Purple = active navigation or primary action

Do not mix requirement status with evidence status.

Examples:

A requirement can be Erfüllt.
An evidence anchor can be Fundstelle bestätigt.
A field can be Bereit.
A review can be Bestanden. 7. Security, Privacy and Data Handling

This project handles potentially sensitive proposal data.

Rules:

MVP and evaluation must avoid real NDA data unless explicitly approved.
Unknown data must be treated as high-risk until classified.
Do not leak project ideas, partner names, budget details or proprietary details into external web tools.
Web research queries must be abstracted and minimized.
Do not log raw prompts, proposal texts, partner data, budget details or confidential documents.
Avoid storing sensitive content in browser storage unless explicitly required and approved.
Never use previous confidential proposals as training/reference material unless explicitly approved and legally cleared.

Data classes:

D0 Public: public calls, public websites, public documents
D1 Internal: non-public but not highly sensitive project/process information
D2 Confidential: project idea, drafts, budget, partner fit, market argumentation
D3 NDA / Restricted: NDA-protected material, confidential partner data, approved proposals
Unknown: treat as D3 until classified

For external search tools:

no raw project idea
no partner names
no exact budget numbers
no proprietary solution details
no confidential passages
only generic search terms 8. Engineering Rules
TypeScript / React
Keep TypeScript strict and explicit.
Prefer typed view models for UI mapping.
Do not use any unless unavoidable and justified.
Do not duplicate label maps if a central helper exists.
Do not move business logic into UI components.
Use frontend view models to translate backend data into user-friendly UI.
Components

Prefer existing components and shadcn/ui patterns.

Good component candidates:

Tabs
Sheet
Dialog
Tooltip
ScrollArea
Badge
Card
Textarea
Resizable Panels
Command
Collapsible / Accordion

Do not introduce a component abstraction unless:

used in at least two places, or
it meaningfully reduces complexity in a large screen, or
it isolates a clearly bounded concern.
View Models

Use view models when backend data is too technical for the UI.

View model responsibilities:

clean labels
map statuses
provide fallbacks
hide technical fields
group UI sections
compute display counts

View models must not:

change API data
implement backend business logic
persist state
silently reinterpret domain facts 9. Tool Usage
shadcn/ui MCP

Use shadcn MCP to inspect and add standard components.

Before adding components:

Check if the component already exists.
Prefer existing local implementation.
Add only the required component.
Do not add a full set of unused components.
UI UX Pro Max

Use UI UX Pro Max as a review aid, not as an autonomous builder.

Good usage:

review hierarchy
review whitespace
review density
review CTA clarity
review disabled-state clarity
review non-technical user comprehension

Do not let it redesign the entire app without approval.

21st.dev / Magic Components

Use only for inspiration or isolated prototypes.

Rules:

Do not directly replace production screens with generated components.
Create prototypes under components/lab/ if needed.
No new dependency without approval.
Integrate only after reviewing design, accessibility and consistency. 10. Implementation Workflow
Before Editing Code

For non-trivial tasks:

Inspect relevant files.
State assumptions.
Explain the plan.
Identify risks.
Define success criteria.
Keep the change small and testable.

Do not start coding if:

the request is ambiguous
the scope is too large
implementation requires API changes without approval
a new dependency seems necessary but was not approved
the requested behavior conflicts with HITL, privacy or product constraints
While Editing
Make surgical changes.
Keep commits conceptually clean.
Preserve existing tests.
Preserve existing behavior unless explicitly changed.
Avoid unrelated formatting changes.
Prefer incremental slices.
After Editing Code

Always summarize:

Changed files
Visible user-facing changes
Technical changes
Risks
Manual test steps
Commands run and results
TODOs not implemented 11. Verification Commands

Run relevant commands after implementation.

General checks:

npx tsc --noEmit
npm run lint
npm run build

Full tests:

npx vitest run

Important targeted tests:

npx vitest run test/live-editor.test.tsx
npx vitest run test/live-review.test.tsx test/review.test.ts
npx vitest run test/requirements.test.ts

If a command fails:

do not hide it
report the failure
explain likely cause
fix if within scope
otherwise ask for direction

Do not claim success unless checks actually pass.

12. Reporting Format

After each completed implementation, respond with:

1. Changed files

- file A — what changed
- file B — what changed

2. User-visible changes

- ...

3. Technical notes

- ...

4. Risks

- ...

5. Verification

- npx tsc --noEmit: pass/fail
- npm run lint: pass/fail
- npm run build: pass/fail
- targeted tests: pass/fail

6. Manual test steps

- ...

7. TODOs / not implemented

- P0:
- P1:
- P2:

13. Priority Labels

Use:

P0 = must fix before demo/evaluation
P1 = should fix soon, meaningful UX or correctness impact
P2 = nice-to-have / polish / future cleanup

Do not implement P1/P2 items during a P0 task unless explicitly approved.

14. Definition of Done

A task is done only when:

user-facing behavior matches the request
no unrelated behavior was changed
no backend/API contract was changed without approval
no raw technical labels are exposed in standard UI
disabled states are understandable
relevant empty/error states are user-friendly
TypeScript passes
lint passes
build passes
affected tests pass
manual test steps are provided
remaining risks are documented

If any of these are not true, say so clearly.
