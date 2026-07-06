# Testdata Policy

Diese Policy gilt fuer alle Evaluationsfaelle, Fixtures, Goldstandards und Smoke-Daten im Repository.

## Grundsatz

- Keine echten vertraulichen Rohdaten im Repo.
- Keine NDA-Daten im Repo.
- Keine Rohideen, Rohprompts, Rohdokumente oder Partnerdaten als Fixture.
- Keine API-Keys, Tokens, Zugangsdaten oder Provider-spezifischen Secrets.
- Synthetische oder oeffentliche Daten muessen klar als solche gekennzeichnet sein.

## Anonymisierte Fixtures

Anonymisierte Fixtures duerfen erst ins Repo, wenn eine menschliche Review bestaetigt:

- keine Partnernamen,
- keine Budgetzahlen aus realen Projekten,
- keine proprietaeren Details,
- keine rueckfuehrbaren Projekttitel,
- keine Textpassagen aus vertraulichen Originaldokumenten.

Die Review muss ausserhalb des Fixtures dokumentiert werden. Ohne Review bleibt das Material ausserhalb des Repositories.

## Evaluation

- R0/F1 startet nur mit synthetischem Material.
- Echte D2-Daten sind kein Thesis-Kern und bleiben bis zu einer expliziten Owner-Freigabe ausserhalb des Repos.
- Evidence Coverage ist nicht Evidence Correctness; Testdaten duerfen diesen Unterschied nicht verwischen.
- Websearch darf nicht mit Rohideen, Partnernamen, Budgetzahlen oder proprietaeren Details erfolgen.

## Commit-Gate

Vor jedem Commit mit Testdaten:

- Diff auf Secrets und vertrauliche Marker pruefen.
- Bestaetigen, dass Fixtures synthetisch/oeffentlich oder reviewed anonymisiert sind.
- Keine Datei committen, die aus einem echten Antrag oder einem NDA-Dokument kopiert wurde.
