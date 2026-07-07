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

## Sensible Marker (CI-Check R0.4)

Der CI-Check `scripts/check_testdata_markers.py` durchsucht die Fixture-Verzeichnisse
(`spike/fixtures/`, `backend/tests/reliability_fixtures/`, `docs/evaluation/cases/`)
nach den hier gepflegten Markern und schlaegt bei jedem Treffer fehl.

Regeln fuer den Katalog:

- Ein Marker je Zeile; Gross-/Kleinschreibung wird ignoriert.
- Zeilen, die mit `#` beginnen, und Leerzeilen werden ignoriert.
- Hierher gehoeren z. B. reale Partnernamen der Beispielprojekte, reale
  Projektcodenamen, reale Personennamen oder eindeutige Budgetkennungen.
- Die Marker selbst sind sensibel genug, um NICHT in oeffentliche Repos zu
  gehoeren — vor dem Eintragen pruefen, ob das Repo-Sichtbarkeitsniveau passt.

<!-- marker-katalog:start -->
```text
# TODO(Owner): Sensible Marker eintragen (reale Partnernamen, Projektcodenamen, ...).
# Katalog ist initial leer; leerer Katalog ergibt einen gruenen Check.
```
<!-- marker-katalog:end -->

### Allowlist (Begruendungspflicht)

Dateien, die einen Marker legitim enthalten duerfen (z. B. dokumentierte
Negativ-Testfixtures), stehen hier mit Pfad relativ zur Repo-Wurzel und
verpflichtender Begruendung im Format `pfad :: Begruendung`.
Eintraege ohne Begruendung lassen den Check fehlschlagen.

<!-- marker-allowlist:start -->
```text
# TODO(Owner): Allowlist-Eintraege im Format "pfad/zur/datei :: Begruendung".
```
<!-- marker-allowlist:end -->
