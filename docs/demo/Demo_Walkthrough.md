# Demo Walkthrough

Milestone 6.1 liefert zwei synthetische Demo-Projekte fuer eine Live-Vorfuehrung.
Die Daten werden nicht beim Start der Anwendung erzeugt. Sie werden explizit
ueber den Demo-Seed erstellt:

```powershell
cd backend
$env:APP_ENV="development"
$env:DEMO_DATA_ENABLED="true"
python -m app.demo.seed --reset
```

Ohne Reset:

```powershell
python -m app.demo.seed
```

## Anmeldung

Frontend im Live-Modus starten und mit Anna anmelden:

- E-Mail: `anna.keller@example.test`
- Passwort: `changeme-dev-lead`

## Dashboard

Nach dem Seed zeigt das Dashboard zwei Demo-Projekte:

- `KI-gestuetzte Entwicklung kreislauffaehiger Verbundwerkstoffe (Demo)`
- `Zustandsueberwachung fuer Produktionsanlagen (Demo)`

Beide Karten tragen ein Demo-Badge. Project A zeigt den naechsten Schritt
`Entwurf weiterbearbeiten`. Project B zeigt Anforderungen/Analyse pruefen,
weil der Forschungspartner absichtlich fehlt.

## Project A

Project A ist im Zustand `Entwurf in Bearbeitung`.

1. Im Dashboard `Entwurf weiterbearbeiten` oeffnen.
2. Der Live-Editor laedt die persistierten Template-Drafts.
3. Mehrere Draft-Versionen stammen aus echten User-Edits.
4. Mindestens zwei aktive Evidence-Links sind auf aktuelle User-Draft-Versionen gesetzt.
5. Nach Refresh bleiben Drafts und Links erhalten.
6. Das Review-Center zeigt die deterministischen Hinweise. Nach einer Bearbeitung
   ist `recheck_required=true`; eine erneute Pruefung setzt es zurueck. Ein
   bearbeiteter, platzhalterfreier Abschnitt kann feldweise freigegeben werden;
   eine weitere Bearbeitung macht die Freigabe wieder ungueltig (stale).

Project A ist nicht export- oder einreichbereit. Eine vollstaendige Run-Freigabe
bleibt blockiert, solange Platzhalter in unterstuetzten Pflichtfeldern offen sind.

## Project B

Project B ist im Zustand `Anforderungen offen`.

1. Im Dashboard die Project-B-Karte oeffnen.
2. Die Anforderungen-Seite zeigt die deterministische Vorpruefung.
3. Der fehlende beitragsberechtigte Forschungspartner erzeugt eine blockierende
   OpenIssue aus der Rule Engine.
4. Nach Refresh bleiben die Anforderungen erhalten.

Im Review-Center bleibt Project B blockiert: der fehlende beitragsberechtigte
Forschungspartner erzeugt eine blockierende Review-Finding, sodass keine Freigabe
moeglich ist. Project B impliziert keine Approval-, Export- oder
Submission-Bereitschaft.

## Reset

Der Reset loescht nur manifest-eigene Demo-Objekte und manifest-eigene
Storage-Dateien:

```powershell
python -m app.demo.seed --reset
```

In einer bestehenden Entwicklungsdatenbank bleiben nicht-demo Projekte erhalten.
In einer isolierten Testdatenbank muessen nach dem Seed genau zwei Projekte
existieren.
