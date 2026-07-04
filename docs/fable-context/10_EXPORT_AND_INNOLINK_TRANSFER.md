# Export And Innolink Transfer

## Exportarten

| Exportart | Status | Codebeleg |
|---|---|---|
| DOCX | Implementiert | `backend/app/exports/generators/docx.py:1` |
| Markdown | Implementiert | `backend/app/exports/generators/markdown.py:3` |
| Technical Evidence JSON | Implementiert | `backend/app/exports/generators/technical_evidence.py:1` |
| Innolink-Kopieransicht | Teilweise implementiert, UI-only | `components/portal-transfer/portal-transfer.tsx:32` |

DOCX/Markdown/Technical Evidence sind Backend-Artefakte; Innolink Copy ist keine persistierte Exportdatei, sondern UI-Funktion über Clipboard (`components/portal-transfer/field-transfer-card.tsx:60`).

## Primär/Sekundär

Im Produktkontext ist Copy-Paste Hauptausgabe. Im Code sind Backend-Exports als generische Exportartefakte implementiert, während Copy-Ansicht in UI eingebettet ist (`backend/app/exports/service.py:39`, `components/export/live-export.tsx:433`). Diese Priorisierung ist architektonisch noch nicht vollständig gespiegelt, weil Copy keinen Backend-Audit-Workflow hat (`components/portal-transfer/portal-transfer.tsx:46`).

## Draft/ENTWURF Markierung

`evaluate_draft_marked` setzt `draft_marked=True`, wenn Force Draft, Run nicht completed, Recheck erforderlich, keine gültige run-scope Approval, stale Approval, Scope-Hash-Mismatch oder ReviewPackage-Version-Mismatch vorliegen (`backend/app/exports/eligibility.py:27`, `backend/app/exports/eligibility.py:35`). Generatoren markieren Drafts mit `ENTWURF – Nicht zur Einreichung` (`backend/app/exports/generators/common.py:14`, `backend/app/exports/generators/docx.py:52`, `backend/app/exports/generators/markdown.py:34`).

## Blocker-Darstellung

Backend-Exports enthalten offene Punkte aus OpenIssues und ReviewFindings über `grouped_open_points` (`backend/app/exports/generators/common.py:58`). Technical Evidence exportiert OpenIssues, Evidence, ReviewFindings, HumanDecisions und Reliability-Metadaten (`backend/app/exports/generators/technical_evidence.py:49`).

## Kopierbereite Felder

UI-Readiness berechnet `kopierbereit`, `platzhalter`, `beleg_fehlt`, `ueberarbeiten` (`lib/export-view.ts:84`, `lib/export-view.ts:142`). Die Readiness ist Darstellungslogik, nicht Backend-Policy.

## Zeichenlimits / Platzhalter / Stale Review

Zeichenlimits werden serverseitig in Review/Approval geprüft (`backend/app/review/checks.py:204`, `backend/app/review/service.py:347`). Platzhalter werden in Drafts geprüft (`backend/app/review/checks.py:185`, `backend/app/review/service.py:345`). Stale Review wird über Recheck Required und Scope Hash dargestellt (`backend/app/review/package.py:347`, `backend/app/review/service.py:422`).

## Auditierbarkeit

Backend-Exports werden persistiert und auditiert (`backend/app/db/models.py:998`, `backend/app/exports/service.py:136`). Copy-Vorgänge werden nicht persistiert; es gibt nur Session-State für `copiedAt` (`components/portal-transfer/portal-transfer.tsx:46`). Ein Copy-Override-/Risk-Acceptance-Audit wurde nicht gefunden.

## Schwächen und Risiken

| Risiko | Status | Codebeleg |
|---|---|---|
| Draft-Export trotz Blockern möglich | Bewusst implementiert | `backend/app/exports/eligibility.py:6` |
| Copy trotz Blockern/Platzhaltern möglich | Bewusst advisory | `lib/portal-transfer.ts:80` |
| Copy nicht auditierbar | Nicht implementiert | `components/portal-transfer/portal-transfer.tsx:46` |
| Copy readiness nicht serverseitig | Nicht implementiert | `lib/export-view.ts:142` |
| Vollständige Innolink-Struktur fehlt | Teilweise | `lib/portal-transfer.ts:112` |
| Export Step benennt sekundäre Artefakte stärker als Innolink-Übernahme | UX-Gap | `components/export/live-export.tsx:97` |

