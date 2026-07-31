# Message-Katalog — Regel-/Partnermeldungen (R2.6) + KI-Blockgründe (R4.2)

> **STATUS: FREIGEGEBEN** — Owner-Approve am 2026-07-07 (Chat, Option
> «Approve — verdrahten»). Verdrahtet in `backend/app/rules/messages.py`;
> Textänderungen laufen über diesen Katalog + erneutes Owner-Approve
> (Prompt-Pack-Arbeitsregel 7: Claude Code verdrahtet nur).

## Zweck

Ersetzt die generischen Partner-Meldungen aus `rules/handlers.py::h_exists`
(«Kein passender Partner vorhanden.» / «Partnerangaben unvollständig — Prüfung
nicht abschliessend.») durch entity-spezifische Texte. Die Zweig-Semantik
(mapping_key: `true` / `missing` / `false`) bleibt unverändert — `missing`
benennt die fehlende Angabe und rät nie pass/fail.

Quellen je Text: Regel aus `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml`
(source_ref = rule_id); die drei mit * markierten Texte stammen wörtlich aus dem
Prompt-Pack R2.6 (Owner-Vorlage).

## Katalog

### INNO.PARTNER.IMPLEMENTATION.MIN1_CH — «Mindestens ein Umsetzungspartner mit Schweiz-Bezug» (blocker)

| Zweig | Meldungstext (DE) | Quelle |
|---|---|---|
| `false` | *«Kein Umsetzungspartner mit Schweiz-Bezug erfasst.» | Prompt-Pack R2.6 (Owner) |
| `missing` | «Angaben zum Umsetzungspartner unvollständig (Schweiz-Bezug/Wertschöpfung offen) — Prüfung nicht abschliessend.» | abgeleitet aus rule condition (`swiss_value_creation`), ENTWURF |
| `true` | «Umsetzungspartner mit Schweiz-Bezug erfasst.» | abgeleitet aus Regel-Titel, ENTWURF |

### INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE — «Mindestens ein beitragsberechtigter Schweizer Forschungspartner» (blocker)

| Zweig | Meldungstext (DE) | Quelle |
|---|---|---|
| `false` | *«Kein beitragsberechtigter Schweizer Forschungspartner erfasst.» | Prompt-Pack R2.6 (Owner) |
| `missing` | «Beitragsberechtigung des Forschungspartners noch nicht bestätigt — Prüfung nicht abschliessend.» | abgeleitet aus rule condition (`research_eligibility_status`), ENTWURF |
| `true` | «Beitragsberechtigter Schweizer Forschungspartner erfasst.» | abgeleitet aus Regel-Titel, ENTWURF |

### INNO.PARTNER.INDEPENDENCE.FINANCIAL_20 — «Finanzielle Unabhängigkeit und 20-Prozent-Schwelle» (blocker)

| Zweig | Meldungstext (DE) | Quelle |
|---|---|---|
| `missing` (keine Angaben) | *«Finanzielle Unabhängigkeit benötigt menschliche Prüfung.» | Prompt-Pack R2.6 (Owner) |
| `missing` (unbestätigt) | *«Finanzielle Unabhängigkeit benötigt menschliche Prüfung.» | Prompt-Pack R2.6 (Owner) |
| `at_or_above_threshold` | «Beteiligung erreicht oder überschreitet die 20-Prozent-Schwelle — menschliche Prüfung erforderlich.» | abgeleitet aus Regel-Titel/condition (threshold aus Registry, nicht hartkodiert), ENTWURF |
| `below_threshold_and_confirmed` | «Finanzielle Unabhängigkeit bestätigt; Beteiligungen unter der Schwelle.» | abgeleitet aus Regel-Titel, ENTWURF |

## Nicht Teil dieses Katalogs (bestehende spezifische Texte bleiben)

`INNO.PARTNER.INDEPENDENCE.PERSONNEL`, `INNO.BUDGET.*`, `INNO.DURATION.*`,
`INNO.APPLICATION.COMPLETE_AND_TRACEABLE`, `INNO.SCIENTIFIC_INTEGRITY.REVIEW`
haben bereits spezifische, nicht-generische Texte in `handlers.py` — R2.6
ändert sie nicht (Scope: generischer Partner-Blocker).

## Abnahme

- [x] Owner hat jeden ENTWURF-Text geprüft (ohne Änderungen übernommen)
- [x] Freigabe erteilt am: 2026-07-07 durch: Owner (Chat-Approve, Session repair-v2/R2)

---

# R4.2 — KI-Verfügbarkeits-Reason-Codes (Owner-Microcopy, wörtlich aus Prompt-Pack)

> **STATUS: FREIGEGEBEN** — Texte stammen wörtlich aus dem Owner-Prompt-Pack R4.2
> («Owner-approved Microcopy für R4.2»). Verdrahtet in
> `backend/app/fields/reason_codes.py` (Backend) und `lib/redraft.ts` (Frontend).
> Der API-`code` bleibt `ai_unavailable`; `reason_code` + `reason_text_de` kommen
> zusätzlich. Der Alttext «KI-Vorschläge sind für diese Datenklasse oder Umgebung
> nicht verfügbar.» darf nicht mehr ohne Code erscheinen (Grep-Test).

| reason_code | reason_text_de | CTA |
|---|---|---|
| `nda_locked` | «Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert.» | «Verarbeitungsmodus prüfen» |
| `mode_deterministic_only` | «Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt.» | «Verarbeitungsmodus ändern» |
| `provider_unavailable` | «Es ist kein freigegebener KI-Provider konfiguriert.» | «Provider-Konfiguration prüfen» |
| `run_mode_mismatch` | «Der aktuelle Analysemodus passt nicht zum Feldvorschlag.» | «Analysemodus prüfen» |
| `missing_sources` | «Für einen belastbaren Vorschlag fehlen passende Quellen.» | «Quelle hinzufügen» |
| `field_not_supported` | «Für dieses Feld ist noch kein Abschnittsvorschlag verfügbar.» | — (kein CTA seit 2026-07-23; der frühere «Strukturvorlage nutzen»-Button fokussierte nur den Editor und suggerierte eine nicht existierende Aktion) |

Nachtrag 2026-07-25 (Owner-Freigabe via genehmigten Plan «UI-Bereinigung —
Dichte, Wiederholungen und lange Erklärtexte»). Fünf Leitregeln: R1 ein
Erklärsatz je Abschnittskopf · R2 eine Information je Ansicht genau einmal ·
R3 ein Aufklapper je Karte · R4 Backend-Listen max. 3 sichtbar · R5 Statuslabels
nur aus zentralen Maps. Kein Text mit rechtlichem/epistemischem Gehalt wurde
gestrichen — nur zusammengezogen, gekürzt oder an den Ort der Handlung verschoben.

| Ort | Alt | Neu |
|---|---|---|
| Recherche-Kopf | 3 Absätze (Brief-Herkunft · Datenschutz · Freigabe-Vorbehalt) | 1 Absatz: «Queries entstehen nur aus dem geprüften öffentlichen Recherchebrief. Keine Rohprojektidee, Partnernamen, Budgets oder Kontaktangaben eintragen.» |
| Recherche Freigabe-Vorbehalt | im Kopf | verschoben ans Brief-Formular über die Freigabe-Buttons (Wortlaut unverändert) |
| Editor-Wrapper Recherche | «Marktquellen werden im gemeinsamen Recherchearbeitsbereich … Ein Snippet allein ist kein Beleg.» | entfällt (5. Disclaimer über derselben Fläche) |
| Query-Zeile Firewall | «Firewall: freigegeben · Risiko niedrig» | «Risiko niedrig» (nur bei `allow`; `block`/`needs_human` unverändert) |
| Ergebniskarte Metazeile | Quellenqualität · Fundstelle · Stützung | Quellenqualität · Fundstelle · (Stützung nur solange nicht übernommen) · «Passt zu: …» |
| Ergebniskarte Aufklapper | «Weitere Angaben» + «Fundstelle aus abgerufener Seite» + «Technische Details» | «Fundstelle aus abgerufener Seite» + «Technische Details» («Weitere Angaben» in die Metazeile aufgelöst) |
| Fundstellen-Aufklapper | Zusatzsatz «Fundstelle exakt abgerufen – fachliche Stützung nicht bestätigt.» | entfällt (Statuszeile sagt es bereits) |
| Anforderungszeile | Begründung gekürzt in der Kopfzeile **und** voll unter «Systembefund» | gekürzte Vorschau nur im zugeklappten Zustand |
| Anforderungsdetail Chips | immer 2 Chips (Beleg + Prüfung) | nur Chips, die die Kopfzeile nicht schon nennt |
| Anforderungsdetail Fusszeile | «Befunde erscheinen automatisch in der Qualitätsprüfung. Bestätigung und Korrektur erfolgen dort.» je Zeile | entfällt je Zeile (steht einmal in der Fussleiste; CTA «In Qualitätsprüfung öffnen» bleibt) |
| Regelgrundlage | wortgleiches Zitat je Registry-Dokument einmal | wortgleiche Zitate zusammengefasst, Quellen mit «·» genannt, Eintrag mit offizieller URL gewinnt |
| Belege-Tab (Entwurf) | `LINK_EXPLANATION` 3 Sätze/280 Zeichen | 1 Satz «Eine Verknüpfung ordnet diesem Entwurf eine Fundstelle zu — sie bestätigt nicht den gesamten Text.» + Aufklapper «Wofür zählt eine Verknüpfung?» mit der Wirkungskette (Wortlaut aus Nachtrag 2026-07-23 erhalten) |
| «Weitere Belege verknüpfen» | alle Anker als Karten | 5 sichtbar + «Alle N Belege anzeigen» |
| A2-Pending | «… Ihr Entwurf bleibt unverändert, bis Sie den Vorschlag prüfen und übernehmen.» | «… Ihr Entwurf bleibt unverändert.» |
| A2-Erklärer | «… Fakten bleiben erhalten, fehlende Angaben werden separat ausgewiesen, und nichts wird ohne Ihre Prüfung übernommen.» | «… vorhandene Fakten bleiben erhalten, nichts wird ohne Ihre Prüfung übernommen.» |
| A2 HITL-Fusszeile | «Vorschläge werden nie automatisch übernommen — Sie prüfen, übernehmen oder verwerfen selbst.» | «Vorschläge werden nie automatisch übernommen.» |
| A2 Feldliste | «Abschnittsvorschläge unterstützen aktuell …» | «Verfügbar für Abstract, Executive Summary, …» |
| Abschnittsmarker-Hinweis | 3 Teilsätze | «Die Abschnittsmarker (z. B. 3.1) wurden verändert — abschnittsweises Bearbeiten ist deaktiviert. Stellen Sie die Markerzeilen wieder her; der gesamte Text bleibt editierbar.» |
| Format-Cache-Hinweise | 2 lange Varianten | je ein Satz; «Innolink übernimmt reinen Text.» |
| `SUPPORT_LADDER_HINT` | 3 Teilsätze | «‹Textstelle gefunden› heisst nur: Der Text ist in der Quelle auffindbar — die fachliche Bewertung bleibt bei Ihnen.» |
| Evidenz-Erklärung | `VERIFIED_EXPLANATION` + `EVIDENCE_VERIFIED_HINT` (zwei Fassungen) | nur `EVIDENCE_VERIFIED_HINT` (die Langfassung wurde nie gerendert) |
| Markt Evidenzlücken | `research_gaps` **und** `judgment.open_evidence_gaps` (im Sheet 2× im selben Dialog) | genau eine Liste je Fläche über `marketGaps()`; 3 sichtbar + «Weitere N Lücken anzeigen» |
| Markt Veraltet | «Suchraum geändert — bitte neu erstellen.» / «… — neu erstellen» / «Suchraum geändert» | einheitlich `MARKET_STALE_BADGE` = «Suchraum geändert — neu erstellen» |
| Markt Marktbild | wortgleiche Werte in zwei Rubriken (z. B. Marktgrösse **und** Nachfrage) | zeilenübergreifende Dedupe in `marketPictureFrom` |
| Markt Sheet Marktbild | «Marktinformationen (Grösse, Segmente, Trends, Nachfrage) — keine Wettbewerber.» | «Marktinformationen — keine Wettbewerber.» |
| Markt Sektion Untertitel | «Nur aus live abgerufenen, vollständig importierten und inhaltlich positiv geprüften öffentlichen Quellen — …» | «Nur aus geprüften öffentlichen Quellen — kein automatischer Eintrag in den Antrag.» |
| Vergleichsbasis | «Vergleichsbasis» + «Dagegen wird verglichen.» + «Deine Projektidee» | «Vergleichsbasis» + «Deine Projektidee — dagegen wird verglichen.» |

**Fachlicher Fix im selben Zug (P1, Ehrlichkeit):** Das Detail-Sheet stellte
Marktaussagen (z. B. «Swiss biotech sector revenue 2023») über die
Fallback-Tabelle unter der Spalte «Wettbewerber / Lösung» dar, sobald keine
Lösungskandidaten vorlagen. Marktaussagen werden dort jetzt wie in der
Quellen-Sektion herausgefiltert (`candidateTypeOf`); bleibt die Tabelle leer,
erscheint der ehrliche Hinweis, dass nur Marktaussagen gefunden wurden.

Nachtrag 2026-07-24c (Owner-Freigabe via genehmigten Plan «Markt- &
Konkurrenzvergleich — Absturz + Arbeitsbereich»):
- P0-Absturz behoben: `market/executor._persist` warf beim Anlegen externer
  Evidence-Anchors/-Links `NOT NULL constraint failed: evidence_anchors.run_id`
  (Dev-DB-Drift; die ORM führt `run_id` bereits als nullable, externe
  Marktanker haben legitim keine run_id). Fix = lokale DB reconciled
  (`run_id` in `evidence_anchors` + `evidence_links` nullable), Backup
  `app.db.bak-market-runid-2026-07-24`. Zusätzlich loggt der Executor seine
  Exceptions jetzt (`logger.exception`), statt sie blind als
  `MARKET_EXECUTION_FAILED` zu verschlucken.
- EIN einheitliches Status-Viewmodel (`marketWorkspaceStatus`) für Quellen-Karte,
  Editor-Rail und Sheet — nie mehr «Fehlgeschlagen» (Karte) und «Nicht
  analysiert» (Rail) gleichzeitig. Labels: «Noch nicht erstellt» (grau) ·
  «Letzter Versuch fehlgeschlagen» (rot, Hinweis «Bitte erneut erstellen.») ·
  «Zu wenige geprüfte Quellen» (orange) · «Begrenzte Evidenz» (orange) ·
  «Veraltet — neu erstellen» (orange) · «Zur Prüfung bereit» (grün, nur mit
  Einträgen) · sonst «Keine belegten Einträge» (orange).
- Marktbild (`deriveMarketPicture`, nur quellengestützte Einträge): Punkte
  «Lösungsarten», «Kundengruppen», «Typische Funktionen», «Marktsignale»,
  «Kundenprobleme» (leere Punkte entfallen); offene Lücken bleiben als «Offene
  Evidenzlücken». Im Sheet als Sektion «Marktbild», in der Rail als Top-2-Zeilen.
- Bereitschaftszeile ohne «n von 2»-Ratio: «{n} geeignete Quellen ausgewählt —
  bereit für einen belastbaren Vergleich.» / «1 geeignete Quelle ausgewählt —
  mindestens 2 empfohlen für einen belastbaren Vergleich. Als Nächstes: …» /
  «Noch keine geeigneten Quellen — als Nächstes: …».
- Sichtbarer Grund am deaktivierten «Marktvergleich öffnen»: «Noch kein
  Vergleich mit Einträgen — unter Quellen erstellen.» bzw. «Letzter Versuch
  fehlgeschlagen — unter Quellen erneut erstellen.» (Tooltip allein reicht
  nicht, CLAUDEX §5).

Nachtrag 2026-07-24b (Owner-Freigabe via genehmigten Plan «Prüf-Dialog v2»):
- Opt-out-Review: alle Änderungen vorausgewählt; Zähler «x von n Änderungen
  ausgewählt»; EIN Primärbutton «Übernehmen» (Name unverändert/E2E-stabil),
  der Zweitbutton «Ausgewählte übernehmen (n)» entfällt. Micro-Copy:
  «Sind alle Änderungen ausgewählt, wird der Vorschlag exakt übernommen;
  sonst genau Ihre Auswahl.»
- Streichungen: links reine Referenz (durchgestrichen, ohne Klickelemente);
  rechts kompakte Kontrollzeile mit Badge «Streichung» + Checkbox
  (aria «Streichung übernehmen: <Satz>»).
- Aufklapper neu: «Begründung und Faktenbilanz» (bündelt Begründung +
  Erhaltene Fakten / Entfernte oder umformulierte Claims / Neue Claims).

Nachtrag 2026-07-24 (Owner-Freigabe via genehmigten Plan «Live-Betrieb Feinschliff»):
- Abschnittsstruktur-Fehler (deterministisch, KEIN Retry-Angebot; Backend
  `sections.section_error_detail` = Frontend `REDRAFT_FAILURE_LABELS`):
  `section_marker_missing:<m>` → «Die Markerzeile ‹m› fehlt im Text. Stellen
  Sie die Zeile ‹m› wieder her oder wählen Sie einen vorhandenen
  Zielabschnitt.»; `section_marker_ambiguous:<m>` → «… kommt mehrfach vor …»;
  `section_markers_out_of_order` → «… nicht in der Reihenfolge der Vorlage …»;
  `section_target_unknown`/`section_markers_missing` → «Der gewählte Abschnitt
  ist für dieses Feld nicht verfügbar …». Dropdown-Hinweis: «‹m› — fehlt im
  Text» bzw. «… stellen Sie die Markerzeile wieder her, um diesen Abschnitt
  gezielt zu bearbeiten.»
- Prüf-Dialog: Aufklapper «Was der Vorschlag ändert — <Diff-Zusammenfassung>»
  und «Offen gelassene Fragen (n)»; Sammel-Auswahl «Alle Streichungen (n)» /
  «Alle neuen Sätze (n)» / «Alle Umformulierungen (n)»; Fusszeile
  «x von n Änderungen ausgewählt».
- Geführte Recherche: «Schritt 1 · Recherchebrief», «Schritt 2 · Suchanfragen
  freigeben und ausführen», «Schritt 3 · Ergebnisse prüfen und übernehmen»;
  Karten-Frage «Stützt diese Quelle Ihre Aussagen?»; Karten-Zeile
  «Quellenqualität: … · Fundstelle: … · Stützung: …» + Aufklapper «Weitere
  Angaben»; manueller Import als Aufklapper «Öffentliche Quelle manuell
  hinzufügen».
- Marktvergleich-Bereitschaft: «{n} von 2 empfohlenen geeigneten Quellen — als
  Nächstes: ‹Titel› inhaltlich prüfen (Stützt/Teilweise).» / «… ‹Titel›
  übernehmen und prüfen.» / «… der Vergleich kann erstellt werden; eine zweite
  geprüfte Quelle macht ihn belastbarer.» (Empfehlung, kein Gate);
  Leerzustand-Nutzen: «Das liefert der Vergleich: eine belegte Tabelle der
  Anbieter und Alternativen mit wörtlich verifizierten Zitaten · ‹Was das für
  den Antrag bedeutet› (bis zu fünf Konsequenzen) · ‹Verwendete Quellen›.»

Nachtrag 2026-07-23 (Owner-Freigabe via genehmigten Verbesserungsplan):
- `field_not_supported` ohne CTA (siehe Tabellenzeile); Hinweis auf unterstützte
  Felder bleibt direkt darunter im Editor.
- Quellen-Tab-Erklärung (LINK_EXPLANATION) ergänzt um den konkreten Nutzen:
  «… Verknüpfte Fundstellen fliessen in die Evidenz-Prüfbereiche (Abdeckung und
  Suffizienz), die Zuverlässigkeitsprüfung und die Kopierbereitschaft dieses
  Felds ein.»
- MARKET_RELEVANCE_HINT erklärt neu, warum der Tab leer ist und wo die Analyse
  verfügbar ist («Value Creation»/«Solution»).
- Markt-Empty-State (live): statische Checkliste + dauerhaft deaktivierter
  Button «Offene Marktfrage erstellen» entfernt; klare Voraussetzung (≥2
  geprüfte öffentliche Quellen) + Aktion «Quelle hinzufügen».
- Prüfbefunde: needs_input-Beschreibungen nennen den Anforderungstitel
  («Anforderung ‹X› benötigt zusätzliche Angaben …»); Sanktions-Beobachtung
  positiv formuliert («Keine Sanktion … — keine zusätzliche menschliche
  Prüfung nötig.»).

Hinweise:
- Interne Block-Reasons (Audit) bleiben unverändert; das Mapping intern → Code
  ist fail-closed (`provider_unavailable` als Default, nie ein codeloser Satz).
- `missing_sources` ist Teil des freigegebenen Katalogs; im Ist-Verhalten
  blockiert kein Pfad wegen fehlender Quellen — Emission folgt mit R5
  (Vorschlagsqualität an Quellen gebunden). FE/BE sind bereits verdrahtet.
