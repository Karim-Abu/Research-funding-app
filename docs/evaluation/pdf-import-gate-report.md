# PDF-Import-Gate-Report (R3.GATE — korrigiert und nachgetestet)

Status: **Gate-Test korrigiert; Narrative-Mapping v2 lokal nachgetestet am
2026-07-13.** Entscheid E-01 («R3 bauen») bleibt nach der Reparatur tragfähig.

Referenzen: `docs/repair/decision-log-needed.md` (E-01), `spike/REPORT.md`,
`docs/evaluation/testdata-policy.md`.

## Zweck und Datensicherheit

Der Gate-Test bewertet, ob ein digitaler Innolink-PDF-Export deterministisch auf
die acht unterstützten Draft-Felder abgebildet werden kann. Das private
Testobjekt umfasst 26 Seiten. Dieser Report enthält keine Antragstexte,
Projektkennungen, Namen oder Antragsnummern, sondern nur Status und sichere
Zählwerte.

Eine exakte Textfundstelle belegt nur, dass ein Ausschnitt im PDF existiert. Sie
belegt weder die inhaltliche Richtigkeit noch die fachliche oder rechtliche
Tragfähigkeit einer Aussage. Deshalb werden Struktur-Coverage und
Zuordnungs-Correctness getrennt bewertet.

## Messungen

1. **Messung 1 — ursprünglicher Spike:** synthetisch entwickelte Anchor-Logik.
2. **Messung 2 — Portal-Vokabular:** zusätzliche Labels und globale Stopper,
   weiterhin «bis zum nächsten unterstützten Anker».
3. **Messung 3 — `innolink-narrative-v2`:** explizite Start-/Stop-Headings je
   Feld und Unterabschnitt, bereinigter Antragstellertext, sichtbare
   Altstruktur-Migration. Kein LLM und kein OCR.

Bewertungsskala:

| Kategorie | Bedeutung |
|---|---|
| `correct` | Antwortbereich korrekt begrenzt und korrekt zugeordnet |
| `partial` | Nutzbarer Antragstellerinhalt vorhanden, aber Zuordnung verlangt fachliche Prüfung |
| `uncertain` | Kein direkt nutzbarer Text oder bewusst mehrdeutige Zuordnung |
| `missed` | Vorhandener Bereich nicht erkannt |
| `false-positive` | Fremdinhalt wurde dem Feld zugeordnet |

Als `usable` zählen nur `correct` und `partial`. `uncertain` bleibt sichtbar und
wird nie automatisch übernommen.

## Korrigierter Befund

Die frühere Messung 2 hatte Management Summary sowie die langen Composite-Blöcke
zu positiv bewertet. Die korrigierte und die reparierte Bewertung lautet:

| # | Feld-ID | Messung 2 korrigiert | Messung 3 | Begründung ohne Rohtext |
|---|---|---|---|---|
| 1 | `INTRO.APP.NAME` | missed | uncertain | v2 erkennt genau einen Dokumentkopf-Kandidaten und verlangt Prüfung. |
| 2 | `INTRO.APP.NAME_EN` | correct | correct | Explizites Label und expliziter Folgestopper. |
| 3 | `INTRO.APP.ABSTRACT` | correct | correct | 297 Zeichen, Ende vor Management Summary. |
| 4 | `INTRO.APP.EXECUTIVE_SUMMARY` | **false-positive** | correct | Antwortbereich ist leer; v2 liefert 0 Zeichen und stoppt vor Context. |
| 5 | `ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS` | uncertain | correct | Leerer Bereich bleibt leer und endet vor Value Creation. |
| 6 | `VC.BUSINESS_TARGETS_MODEL.EDITOR` | **partial** | correct | Vorher Portalfragen/Hilfetext im Großblock; v2 liefert 3 getrennte Abschnitte. |
| 7 | `SOL.INNOVATION_SOLUTION.EDITOR` | **partial** | partial | v2 liefert 8 Zielmetadaten; alte Lizenz-/Background-IP-Antwort bleibt bewusst gemeinsam unsicher für 4.5.2/4.5.3. |
| 8 | `PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION` | uncertain | correct | Leerer Bereich bleibt leer und stoppt vor Budget-/Kostenbereichen. |

Die frühere Messung-2-Quote war somit nicht 5/8, sondern **4/8 = 50 %**. Sie
durfte den Gate-Entscheid allein nicht tragen. Nach der expliziten
Grenzenreparatur erreicht Messung 3 **7/8 usable**; der verbleibende Titel ist
absichtlich `uncertain`.

## Coverage und Correctness

- **Struktur-Coverage:** acht unterstützte Feldkandidaten; Composite-Metadaten
  3 Abschnitte für Value Creation und 8 Einträge für Solution inklusive der
  gemeinsamen 4.5.2/4.5.3-Prüfzuordnung.
- **Zuordnungs-Correctness:** Abstract exakt begrenzt; Management Summary 0
  Zeichen; keine geprüfte Portalfrage und kein bekannter Hilfetext im
  Übernahmetext; leere Bereiche übernehmen keine Folgeabschnitte.
- **Nicht bewertet:** Förderfähigkeit, Belegqualität, FTO, IP-Schutzfähigkeit,
  Vertragswirkung und materielle Richtigkeit der Antragstellerangaben.

## Regression und Fail-closed

- Strukturgleiches synthetisches Mehrseiten-PDF deckt leere Bereiche,
  3.1–3.3, 4.1–4.6 und die Alt-IP-Migration ab.
- Degradierte PDFs bleiben `uncertain` beziehungsweise nicht gemappt.
- Verschlüsselte, gescannte und korrupte PDFs bleiben ohne OCR fail-closed.
- Audit und Logs enthalten nur IDs, Versionen, Status und sichere Zählwerte;
  weder bereinigte Kandidatentexte noch Originalausschnitte.

## Strukturierter Folgetest (`innolink-structured-v1`)

Der additive strukturierte Import wurde am selben privaten, 26-seitigen
Digital-PDF ausschließlich lesend geprüft. Es wurden keine Werte automatisch
in Project, Partner oder Budget persistiert. Der inhaltsfreie Befund:

| Kandidatengruppe | Anzahl | Befund |
|---|---:|---|
| Projektmetadaten | 5 | Titel, englischer Titel, Start, Ende und Dauer vorhanden |
| Partner | 3 | 1 Research- und 2 Implementation-Partner; alle prüfpflichtig |
| Budget | 5 | direkte Kosten, Own, Cash sowie Förderung ohne/mit Overhead getrennt |
| Strukturierte Antworten | 2 | Scientific Integrity und Management-Stunden vorhanden |

Alle drei Partner bleiben im privaten Gate bewusst `uncertain`, weil das
ältere Tabellenformat kein explizites Land ausweist. Adress- oder Namensdaten
werden nicht als Schweiz-Bezug, Wertschöpfung oder Eignung interpretiert. Die
beiden personellen und finanziellen Unabhängigkeitsgruppen sind als
Antragstellerangabe erkannt; daraus entsteht keine rechtliche Schlussfolgerung.

Der vollständig synthetische Golden-Import bestätigt zusätzlich den
HITL-Persistenzpfad: drei Partner und fünf Budgetangaben werden erst nach
Einzelbestätigung gespeichert; die vorhandene Budget-Vorprüfung berechnet
52,52 % Umsetzungspartneranteil und 6,46 % Cash-Anteil als erfüllt. Ein danach
erzeugter Lauf friert Projekt, drei Partner, Scientific Integrity und
Management-Stunden in einem unveränderlichen Snapshot ein. Eine spätere
Annahme markiert den alten Lauf als `recheck_required`, ohne dessen Snapshot zu
ändern.

## Verbleibende Risiken und manuelle Prüfung

- **n = 1 privates reales PDF:** weitere Portalexport-Varianten müssen bei
  Verfügbarkeit strukturell nachgetestet werden.
- Der Dokumentkopftitel bleibt prüfpflichtig, auch wenn das Muster eindeutig ist.
- Die alte Lizenz-/Background-IP-Antwort darf nicht automatisch auf 4.5.2 oder
  4.5.3 festgelegt werden. Eine menschlich bearbeitete Fassung ist erforderlich.
- Lange Antragstellerantworten werden deterministisch begrenzt, aber nicht als
  fachlich richtig oder ausreichend bewertet.

Owner-Signatur für den ursprünglichen Entscheid: 2026-07-07. Technischer
Reparatur-Nachtest: 2026-07-13.
