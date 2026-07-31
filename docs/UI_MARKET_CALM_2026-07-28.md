# Markt- & Konkurrenzvergleich — ruhigere Oberfläche (Dichte, Typografie, Aufklapper)

Stand: 28. Juli 2026
Scope: **frontend-only**. Keine Backend-, Contract-, DTO-, Routen- oder
Migrations-Änderung. Keine neuen Dependencies. Keine neuen Statuszustände —
`marketUiState`, `marketGaps`, `marketPictureFrom` und die Backend-Urteilslogik
bleiben unangetastet.

Anlass (Owner-Rückmeldung zu drei Screenshots): Dialog und Quellen-Karte zeigten
zu viel Text auf einmal, fast alles in 11 px, Sekundäres gleichrangig neben der
Antwort. Genannte Beispiele: die generische Liste «Nicht zulässige Aussagen» und
die «Vergleichsbasis» dominierten die Fläche, obwohl das **Ergebnis** relevant
ist.

## 1. Leitentscheide

| # | Entscheid |
|---|---|
| D1 | **Antwort zuerst.** Der Ergebnissatz steht in 14 px; Suchumfang, nächster Schritt, Belege und Listen in 12 px. Kein `text-[11px]` mehr auf den grossen Markt-Flächen. |
| D2 | **Kontext und Generisches hinter einen Aufklapper.** Vergleichsbasis (zugeklappt, Titelzeile nennt Projekt + Innovationsfeld), «Nicht zulässige Aussagen (n)», Marktbild, Lückenliste auf der Übersichtskarte. Nichts entfernt — alles einen Klick entfernt vollständig lesbar. |
| D3 | **Ein Aufklapper-Muster.** Neu `MarketDisclosure` (`market-blocks.tsx`): natives `<details>`, Chevron statt Browser-Dreieck, Anzahl in der Titelzeile, einheitliche Fläche. Ersetzt vier handgeschriebene Varianten. |
| D4 | **Kein Satz zweimal.** War die zulässige Formulierung wortgleich mit dem Ergebnissatz, stand derselbe lange Satz zweimal im Dialog. Jetzt trägt die Übernahmezeile nur noch den Hinweis «Der Ergebnissatz oben — unverändert übernehmbar.» + Button. |
| D5 | **Der Ergebnissatz kommt aus `marketUiState`,** nicht mehr direkt aus `judgment.rationale`. Bei veraltetem Suchraum oder zu schmaler Quellenlage stand im Dialog sonst weiter der alte Befund, während das Badge oben «Veraltet» sagte. Dialog und Quellen-Karte zeigen damit denselben Satz. |

## 2. Reihenfolge im Dialog (`market-comparison-sheet.tsx`)

Titel + Status-Badge (eine Zeile) → Hypothesen-Hinweis → *Vergleichsbasis
(zugeklappt)* → **Ergebnis** (Satz, Suchumfang, nächster Schritt,
Überschneidungen, übernehmbare Aussage, *Sperrliste zugeklappt*) → **Gefundene
Lösungen** (Kandidaten, danach *Marktbild zugeklappt*) → **Was noch fehlt**
(3 Lücken sichtbar, Rest hinter «Weitere n …») → Fusszeile.

Das Status-Badge wandert in die Kopfzeile (vorher ein eigener Block über dem
Inhalt). Das Marktbild steht jetzt **unter** den Lösungen: Marktstatistik ist
Kontext, nicht Befund.

## 3. Quellen-Karte (`market-comparison-section.tsx`)

Unverändert: Kopfzeile, Erklärsatz, «Verglichen mit», Fortschrittszeile,
Deaktivierungsgrund, «Details öffnen». Geändert: Ergebnisblock in 14/12 px, und
die Lückenliste liegt hinter «Offene Evidenzlücken (n)» — die Anzahl genügt auf
der Übersicht, der nächste Schritt steht im Ergebnisblock darüber.

## 4. Textänderungen (Nachtrag zum Message-Katalog)

- Dialog-Abschnitt «Was noch fehlt» trägt die Lückenliste jetzt ohne zweiten
  Titel «Offene Evidenzlücken» (der Abschnittskopf benennt sie). Auf der
  Quellen-Karte bleibt «Offene Evidenzlücken» als Aufklapper-Titel.
- «Untersuchter Suchfokus (öffentlich-sichere Recherche)» → «Suchfokus
  (öffentlich-sichere Recherche)».
- «Marktbild (Marktinformationen)» + Erklärsatz → eine Titelzeile «Marktbild
  (Marktinformationen, keine Wettbewerber)».
- Neu: «Diese Formulierungen sind durch den Suchumfang nicht gedeckt und nicht
  übernehmbar.» (im aufgeklappten Sperrblock), «Der Ergebnissatz oben —
  unverändert übernehmbar.»
- Unverändert gepinnt: alle Statuslabels (`MARKET_*`, `CONFIDENCE_LABELS`,
  «Textstelle gefunden», «Für den Antrag verwendbar», «Weitere Recherche nötig»,
  «Veraltet — neu erstellen»), `MARKET_HYPOTHESIS_NOTE`, `INSERT_BLOCKED_HINT`,
  Nächster-Schritt-Sätze, «Details öffnen», «Übernehmen», «Als Argument
  übernehmen», «Marktaussagen prüfen (n)», «Weitere n Lücken anzeigen».

## 5. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `components/editor/market-blocks.tsx` | neu `MarketDisclosure`; `MarketPictureList` mit fester Beschriftungsspalte; `MarketGapList` mit `collapsed`/`label`, `compact` entfernt (kein Aufrufer mehr) |
| `components/editor/market-comparison-basis.tsx` | `collapsible`-Variante, gemeinsamer `BasisBody`, 12 px statt 11 px, Bearbeiten-Link am Ende des Inhalts |
| `components/editor/market-comparison-sheet.tsx` | Struktur nach §2, `ResultCard` (ersetzt `JudgmentCard`), Sperrliste als Aufklapper, Dedupe des Ergebnissatzes, Typo-Ebenen |
| `components/quellen/market-comparison-section.tsx` | Ergebnisblock 14/12 px, Lückenliste zugeklappt, Marktbild-/Marktaussagen-Block auf `MarketDisclosure` |
| `test/market-comparison-sheet.test.tsx` | zwei neue Fälle (Sperrliste zugeklappt und vollständig; Ergebnissatz nicht doppelt), Basis-Fall prüft zusätzlich den zugeklappten Zustand, Lücken-Fall prüft den einen Titel |

## 6. Gates

```text
npx tsc --noEmit  → pass
npm run lint      → pass
npx vitest run    → pass (79 Dateien / 661 Tests, davon 2 neu)
npm run build     → pass
```

Visuelle Prüfung: temporäre Vorschauseite (`app/dev-market-preview`, danach
gelöscht) mit den Daten aus den Owner-Screenshots, `next dev -p 3100` im
Mock-Modus, Screenshots via Playwright — Dialog im Standardzustand, mit
geöffneten Aufklappern, Quellen-Karte zu/offen/mit Details. Playwright-E2E und
`scripts/verify_all.ps1` wurden **nicht** ausgeführt (brauchen Backend, Seed und
Live-Preflight); e2e-gepinnte Strings («Details öffnen», Testids) sind
unverändert.

## 7. Offen

- **P2** — Der Aufklapper «Weitere Details» in der Lösungslandschaft-Tabelle
  trägt weiter die native Browser-Markierung (in einer Tabellenzelle passt die
  gerahmte `MarketDisclosure`-Fläche nicht).
- **P2** — Die Editor-Rail (`live-market-comparison.tsx`) bleibt bei 11 px: sie
  ist real nur ~220–300 px breit. Bewusst nicht angeglichen.
- **P1 (unverändert offen, Backend)** — die langen Lückensätze entstehen in
  `backend/app/market/executor.py` / `judgment.py`; das Frontend kappt und
  gruppiert nur (siehe `UI_CLEANUP_2026-07-25.md` §8).
