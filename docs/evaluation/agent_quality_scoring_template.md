# Agent Quality Scoring Template (EVAL.4)

Diese Vorlage ist ausschliesslich für **menschliche Reviewer** gedacht. Claude/die KI
darf diese Vorlage **niemals selbst ausfüllen** — die Scores sind eine fachliche
Einschätzung eines Menschen, kein automatisch berechneter Wert. Der
[supervisor_eval_report.md](supervisor_eval_report.md) enthält dieselbe Tabellenstruktur
nur mit `TODO`-Platzhaltern; diese Datei liefert die Bewertungs-Skala dazu.

Bewertet wird ausschliesslich der **Feldentwurf** (`suggested_text`), nie interne
Prompts/Rohantworten. Referenz für den Kontext: `r5_9_real_integrated_draft_report.md` /
`supervisor_eval_report.md`.

## Skala (1–5) je Kriterium

### field_fit — passt der Entwurf zur Feldfrage?
1. Entwurf verfehlt die Feldfrage vollständig oder beantwortet ein anderes Feld.
2. Entwurf berührt das Thema, aber grosse Teile der Feldfrage bleiben unbeantwortet.
3. Entwurf deckt die Feldfrage grundsätzlich ab, mit spürbaren Lücken.
4. Entwurf deckt die Feldfrage vollständig ab, kleinere Unschärfen.
5. Entwurf deckt die Feldfrage vollständig und präzise ab (inkl. aller Pflicht-Abschnitte).

### specificity — wie konkret/spezifisch ist der Text?
1. Nur generische Floskeln, austauschbar mit jedem anderen Projekt.
2. Überwiegend generisch, vereinzelt projektspezifische Details.
3. Mischung aus generischen und projektspezifischen Aussagen.
4. Überwiegend projektspezifisch, wenige generische Restformulierungen.
5. Durchgehend konkret und projektspezifisch, soweit die Eingabedaten das zulassen.

### factuality — enthält der Text erfundene Fakten/Zahlen?
1. Enthält klar erfundene/unbelegte Fakten, Zahlen oder Zusagen (kritisch).
2. Enthält mindestens eine unklare, nicht als Platzhalter markierte Behauptung.
3. Überwiegend korrekt, aber Grenzfälle bei Formulierungen (z. B. zu bestimmt klingend).
4. Alle Behauptungen sind entweder belegt oder klar als offen/Platzhalter markiert.
5. Vorbildlich: jede unbelegte Aussage ist explizit als Platzhalter/`missing_input`
   gekennzeichnet, keine impliziten Zusagen.

### missing_input_handling — wie transparent werden Lücken markiert?
1. Lücken werden verschwiegen oder stillschweigend mit plausiblem Text überdeckt.
2. Manche Lücken sind markiert, andere fehlen ohne Kennzeichnung.
3. Die meisten Lücken sind markiert, Formulierung teils unklar.
4. Alle wesentlichen Lücken sind klar als Platzhalter/`missing_input` gekennzeichnet.
5. Lücken sind nicht nur markiert, sondern mit konkretem Hinweis, welche Angabe fehlt.

### language_quality — Sprache, Ton, Lesbarkeit
1. Unverständlich, fehlerhaft oder für einen Förderantrag ungeeigneter Ton.
2. Verständlich, aber holprig oder stellenweise unprofessionell.
3. Solide, professionelle Standardsprache mit kleineren Schwächen.
4. Klar, professionell, gut lesbar.
5. Klar, professionell, prägnant — ohne Marketing-Übertreibung.

## Bewertungstabelle (leer — von Reviewern auszufüllen)

### Provider: openai

| field_id | field_fit | specificity | factuality | missing_input_handling | language_quality | reviewer_notes |
| --- | --- | --- | --- | --- | --- | --- |
| INTRO.APP.NAME | | | | | | |
| INTRO.APP.NAME_EN | | | | | | |
| INTRO.APP.ABSTRACT | | | | | | |
| INTRO.APP.EXECUTIVE_SUMMARY | | | | | | |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | | | | | | |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | | | | | | |
| SOL.INNOVATION_SOLUTION.EDITOR | | | | | | |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | | | | | | |

### Provider: anthropic

| field_id | field_fit | specificity | factuality | missing_input_handling | language_quality | reviewer_notes |
| --- | --- | --- | --- | --- | --- | --- |
| INTRO.APP.NAME | | | | | | |
| INTRO.APP.NAME_EN | | | | | | |
| INTRO.APP.ABSTRACT | | | | | | |
| INTRO.APP.EXECUTIVE_SUMMARY | | | | | | |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | | | | | | |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | | | | | | |
| SOL.INNOVATION_SOLUTION.EDITOR | | | | | | |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | | | | | | |

## Regeln

- Nur ein Mensch trägt Werte ein. Kein automatisches Scoring durch die KI.
- Deterministische Felder (NAME, NAME_EN) werden trotzdem bewertet — hier vor allem
  `field_fit`/`factuality` (z. B. wurde der richtige Titel übernommen, nichts erfunden).
- Ein Feld mit Status `failed` bekommt keine Scores (leer lassen), stattdessen einen
  `reviewer_notes`-Eintrag mit dem Grund (z. B. Verweis auf den Feld-/Struktur-Fehler).
- Diese Datei wird nicht automatisch aus Laufzeitdaten neu generiert — sie ist eine
  stabile Vorlage, die pro Review-Runde manuell kopiert/ausgefüllt werden kann.
