# Architektur der feldbezogenen LLM-Vorschläge

Stand: 21. Juli 2026
Version: RUN 3C Phase 1, offline

## Geltungsbereich

RUN 3C erweitert den bestehenden A2-/Redraft-Pfad. Es gibt keinen zweiten
LLM-Gateway, keinen zusätzlichen Evidence-Speicher und keine Websuche aus dem
Vorschlagspfad. Die in diesem Dokument beschriebenen Sicherheits- und
Korrektheitsprüfungen wurden offline mit Testadaptern geprüft. Eine Aussage zur
Qualität echter Modellausgaben ist daraus ausdrücklich nicht ableitbar.

## Einziger Erzeugungs- und Annahmepfad

```text
Feld + Basisversion + Modus + ausgewählte Anchor-IDs
  -> bestehender A2-Redraft-Service
  -> SuggestionContextBuilder
  -> bestehender Gateway und bestehende Providerroute
  -> FieldSuggestionOutput@v1
  -> unabhängige serverseitige Claim-Prüfung
  -> DraftSuggestion + SuggestionContextManifest@v1 + OpenIssues
  -> menschliche Vollübernahme
  -> bestehender Draft-Update-Pfad
  -> genau eine neue DraftVersion
```

Der Generator führt weder eine Recherche aus noch wechselt er bei Fehlern den
Provider. Ein Live-Aufruf darf niemals auf einen Fake-Adapter zurückfallen.
Phase 1 führt überhaupt keinen echten LLM-Aufruf aus.

## SuggestionContextBuilder

`field_drafting_context` bleibt der zentrale Kontextdienst. Bestehende A2-
Aufrufer nutzen den kompatiblen Legacy-Wrapper; neue, idempotente UI-Aufrufe
aktivieren den manifestgebundenen Pfad.

Der Kontext enthält nur:

- den aktuellen Feldtext und seine Basis-DraftVersion;
- bestätigte strukturierte Daten des eingefrorenen Run-Snapshots;
- feldbezogene Requirements und Rules aus Portalmetadaten und YAML-Registry;
- Application Evidence aus der eingefrorenen primären Antragversion;
- explizit ausgewählte, aktuelle, geprüfte und sichere Supporting-/External-
  Anchors;
- offene, für Feld oder Requirement relevante Issues;
- höchstens fünf aktuelle, source-backed und feldrelevante Market-Findings,
  deren Anchor-IDs ebenfalls für diesen Kontext erlaubt sind.

Ausgeschlossen werden insbesondere Search-Snippets, alte SourceVersionen,
Generated Outputs, Review-Kommentare, fremde Projekte oder Workspaces,
ungeprüfte beziehungsweise quarantänisierte Inhalte und eine vollständige
MarketComparison.

Die Priorisierung und Kürzung sind deterministisch. Im manifestgebundenen Pfad
wird nur an Satzgrenzen gekürzt. Passt ein Anchor nicht vollständig, wird er
als Einheit entfernt, in `omitted_anchor_ids` festgehalten und auch aus der
Grounding-Erlaubnisliste sowie dem strukturierten Provider-Input entfernt.

## Metadatenmanifest

`SuggestionContextManifest@v1` speichert keine Dokument- oder Kontextvolltexte.
Es friert folgende Identitäten und Versionen ein:

- Workspace, Projekt, Run, Feld und Basis-DraftVersion;
- Primary-Application-SourceVersion;
- Requirement-/Rule-Registry und Feldinstruktions-Hash;
- Modus, Sprache, Prompt- und Output-Schema-Version;
- ausgewählte, tatsächlich zugelassene und ausgelassene Anchor-IDs;
- SourceVersion-IDs und optionale MarketComparison-ID;
- Requirement-/Rule-IDs, Komponenten-Hashes und Gesamt-Context-Hash.

Der eigentliche Vorschlagstext bleibt wie bisher in `DraftSuggestion`. Das
Manifest dient Reproduzierbarkeit, Scoping und Staleness, nicht als zweiter
Inhaltsspeicher.

## Strukturierte Ausgabe und Grounding

`FieldSuggestionOutput@v1` umfasst Vorschlagstext, Änderungszusammenfassung,
verwendete Anchor-/Rule-IDs, validierte `missing_inputs`, Warnungen, die
providerseitige Claim-Map, Unicode-Zeichenzahl, Limitstatus und Sprache.

Die Claim-Map des Modells ist nur eine zusätzliche Deklaration. Der Server
untersucht unabhängig den gesamten Vorschlagstext auf:

- Zahlen, Prozentwerte, Währungen, Datumswerte, Dauer- und TRL-Angaben;
- konkrete Organisationen, Akronymorganisationen und benannte Produkte;
- konkrete Markt-, Technologie- und Rechtsbehauptungen.

Jeder erkannte Claim wird satzweise gegen den Originaltext, bestätigte
strukturierte Fakten und die tatsächlich ausgewählten Anchor-Zitate geprüft.
Search-Snippets, Reviewtexte und providerseitige Behauptungen sind keine
Grounding-Quelle. Kritische unbelegte Claims erlauben höchstens einen
Reparaturversuch über dieselbe Gatewayroute. Danach endet die Operation mit
`failed_grounding_validation`; ein halbfertiger Vorschlag wird nicht
persistiert.

Sprachkonflikte und das Unicode-Codepoint-Limit werden serverseitig mit der
bestehenden Portal-Semantik geprüft.

## Missing Inputs und OpenIssues

Jeder Missing Input muss eindeutig an mindestens ein Requirement aus dem
Manifest gebunden sein. Die Zuordnung wird aus Registry-Metadaten abgeleitet,
nicht aus einer zweiten Innosuisse-Checkliste. Mehrdeutige Modellwerte dürfen
einmal repariert werden und werden danach fail-closed abgelehnt.

Der Issue-Fingerprint besteht aus Run, Feld, Requirement und normalisiertem
Missing-Input-Key. Dadurch gilt:

- Wiederholungen aktualisieren `last_seen_at`, erzeugen aber kein Duplikat;
- ein weiterhin fehlender Input bleibt `open`;
- ein nicht mehr fehlender Input wird `resolved`;
- ein ungültiger oder veralteter Ursprung wird `stale`;
- ein später erneut auftretender Mangel wird nachvollziehbar wieder geöffnet.

## Idempotenz, Annahme und Legacy-Kompatibilität

Neue UI-Aufrufe senden immer einen `Idempotency-Key`. Für Generate bleibt er
vorläufig optional, damit alte Clients weiter funktionieren. Gleicher Key und
gleiche normalisierte Payload liefern dieselbe AsyncOperation; eine abweichende
Payload ergibt `409 idempotency_conflict`.

Der neue scoped Accept-Endpunkt verlangt den Key und die Basisversion. Accept
prüft Manifest und Staleness erneut und nutzt danach den bestehenden Draft-
Update-Pfad. IdempotencyRecord und neue DraftVersion liegen in derselben
Transaktion; auch konkurrierende Replays erzeugen deshalb genau eine Version.

Manifestgebundene Vorschläge tragen `accept_mode=whole_suggestion_only`. Die
bestehende Satz-Diff- und Teilübernahmeimplementierung bleibt im Code und für
Legacy-Suggestions erhalten, wird für RUN-3C-Suggestions aber server- und
clientseitig ausgeblendet beziehungsweise abgelehnt.

## Staleness

Read und Accept prüfen zentral:

- Basis-DraftVersion;
- Run-Snapshot;
- primäre Antragversion;
- Requirement-/Rule-Registry und Feldinstruktion;
- Anchor-Verifikation und aktuelle SourceVersion;
- MarketComparison-Status und Stale-Grund.

Historische Vorschläge bleiben lesbar. Suggestion-Zeilen ohne Manifest werden
bei der Migration als `expired/historical_context_unavailable` markiert; ihr
vorheriger Status wird rollback-sicher bewahrt. Ein staler Vorschlag kann nicht
übernommen werden.

## Sicherheits- und Qualitätsgrenze

Die deterministische Extraktion reduziert bekannte Halluzinationsrisiken, ist
aber kein semantischer Wahrheitsbeweis. Insbesondere komplexe implizite Claims
und die fachliche Nützlichkeit einer Formulierung benötigen weiterhin
menschliche Bewertung. Echte LLM-Qualität gilt erst nach LIVE-02, LIVE-03 und
einer dokumentierten menschlichen Qualitätsbewertung als geprüft.
