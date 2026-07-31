---
title: "Markt-UI — finale Verifikation"
date: 2026-07-26
commit: 7f09c1f
branch: stabilize/eval3-final-01
status: green
tags: [eval3, market-ui, verification]
---

# Markt-UI — finale Verifikation

Der Markt-UI-Umbau (`aedee80`, `7f09c1f`) wird hier auf dem finalen Branch
verifiziert. Vorgeschichte: Während des Stabilisierungslaufs war der Baum
zeitweise nicht übersetzbar (12 `tsc`-Fehler in `live-market-comparison.tsx`);
der Lauf wurde deshalb pausiert. Dieser Stand ist wieder vollständig grün.

## 1. Gates

| Gate | Befehl | Ergebnis | Artefakt |
|---|---|---|---|
| TypeScript | `pnpm exec tsc --noEmit` | **pass** (Exit 0, keine Fehler) | — |
| Vitest (vollständig) | `pnpm exec vitest run` | **pass** — **79 Dateien / 653 Tests**, 0 Fehler | `runs/MARKET-UI-01/junit.xml` |
| ESLint | `pnpm lint` | **pass** (Exit 0) | `runs/MARKET-UI-01/lint.log` |
| Production Build | `rm -rf .next && pnpm build` | **pass** — kompiliert in 9,8 s | `runs/MARKET-UI-01/build.log` |

Zum Vergleich: EVAL3-PRE-01 zählte 78 Dateien / 631 Tests. Der Umbau hat
**22 Tests hinzugefügt**, keiner wurde entfernt.

## 2. Geprüfte Bereiche

| Testbereich | Testpfad | Ergebnis | bekannte Grenze |
|---|---|---|---|
| Marktvergleichsübersicht (Quellen) | `test/market-comparison-section.test.tsx` | pass | Zustände nur über MSW-Fixtures, nicht live |
| Detail-Sheet (Ergebnis / Gefundene Lösungen / Was noch fehlt) | `test/market-comparison-sheet.test.tsx` | pass | — |
| Editor-Rail | `test/live-market-comparison.test.tsx` | pass | — |
| Markt-Viewmodel (`marketUiState`, `marketGaps`, `marketPictureFrom`) | `test/market-view.test.ts` | pass | — |
| Reliability-Viewmodel | `test/reliability-view.test.ts` (neu, +68 Zeilen) | pass | — |
| Markt-Blocks (`MarketPictureList`, `MarketGapList`) | über Sheet-/Section-Tests | pass | keine eigene Unit-Datei |
| Quellen-/Evidenzanzeige | `test/live-evidence.test.tsx`, `test/support-status-badge.test.tsx` | pass | — |
| Leere und limitierte Zustände | `market-comparison-section.test.tsx` (`limited`, `insufficient_external_evidence`, `item_count 0`) | pass | — |
| Belegte vs. unbelegte Vergleichszellen | `market-comparison-sheet.test.tsx` (`source_backed` vs. `needs_review`), Sperr-Block für unzulässige Aussagen | pass | — |
| Navigation Recherche ↔ Marktvergleich | `test/public-research-panel.test.tsx`, `e2e/market-comparison.spec.ts` | pass (Unit) / siehe Gate (E2E) | — |
| Zeichen-/Unicode-Behandlung | `test/research-text.test.ts`, `e2e/…` Unicode-Pfad | pass | — |
| Fehler- und Loading-Zustände | `market-comparison-section.test.tsx` (`generating`, `error`, `disabledReason`) | pass | — |
| Responsive Darstellung | **nicht automatisiert geprüft** | `not-executed` | Screenshots existieren nur aus opt-in Specs (`RUN4B_VISUAL`), Stand 2026-07-23 — also **vor** diesem Umbau |

## 3. Ehrliche Grenzen

- **Responsive Darstellung wurde in diesem Lauf nicht geprüft.** Die vorhandenen
  Screenshots unter `docs/assets/run4b/` zeigen den Stand vom 2026-07-23 und
  bilden den aktuellen Umbau **nicht** ab. Sie werden hier bewusst nicht als
  Nachweis geführt. Ein visueller Nachweis würde `RUN4B_VISUAL=1` mit laufenden
  Servern erfordern.
- Die Markt-Blocks haben keine eigene Unit-Testdatei; sie sind indirekt über
  Sheet und Section abgedeckt.
- Markt-Zustände sind über MSW-Fixtures geprüft, nicht gegen einen echten
  Provider — das ist die dokumentierte Betriebsart des Gates
  (Fake-Provider, siehe [[Provider_Mode_Matrix]]).

## 4. Ergebnis

Alle vier Pflicht-Gates sind grün. Das Stopp-Kriterium des Auftrags
(«bei TypeScript- oder Build-Fehlern stoppen») greift **nicht** — die
nachfolgenden Final-Gates durften ausgeführt werden.

Weiter: [[FINAL_INTEGRATION_BASELINE]] · [[EVAL3_FINAL_01_REPORT]]
