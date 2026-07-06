# Decision Log — Entscheidungen des Product Owners / Thesis-Autors

Alle Entscheide sind in R0 zu treffen (Ausnahmen markiert). Ohne Entscheid gilt der genannte Default. «Empfehlung» ist begründeter Vorschlag, kein Fakt.

| ID | Entscheidung | Optionen | Empfehlung | Blockiert | Default ohne Entscheid |
|---|---|---|---|---|---|
| E-01 | PDF-Gate: Import bauen? | Nachtest mit echtem Innolink-PDF; ≥ ~60 % Mapping-Quote = bauen, sonst streichen [Doc: Spike] | Test sofort durchführen; Entscheid dem Ergebnis folgen | R3 vs. R3' | R3' (Fallback), Import gestrichen mit Spike-Begründung |
| E-02 | Provider-Policy für D2 | a) nur Fake/Local (Thesis-Demo); b) Enterprise-Cloud mit Auftragsverarbeitung; c) lokales Modell; d) Kombination je Datenklasse | Für Thesis: a oder c; b nur mit dokumentierter Vertragsbasis. Direkte Anthropic/OpenAI-APIs (bestehende Settings-Keys [Code]) nur für synthetische/öffentliche Daten — nie für echte D2-Inhalte | Wirkung von R4, ganz R5-Realbetrieb, R8-Suche | a) Fake/Local; UI und Thesis kennzeichnen das ehrlich |
| E-03 | Feldstufe für Beta | A = 8 Felder; B = +INTRO.PREV.SYNERGY, +INTRO.IP.FINDINGS + Attachment-Gates + Submit-Readiness-Checkliste; C = später | B, wenn Zeitbudget nach R6 grün ist; sonst A | Teile von R5/R7b | A |
| E-04 | WP-Minimalstruktur | ja (Titel, Dauer, Stunden je Partner, Konsistenz-Checks) / nein (Limitation dokumentieren) | nein für Thesis-Abschluss, ausser Betreuung verlangt WP-Prüfungen | optionaler R7b-Slice | nein |
| E-05 | Echte Websearch im Scope | ja (Provider gemäss E-02, z. B. Firecrawl-Key vorhanden als Option [Code: settings]) / nein (Fake + URL-/Datei-Quellen) | nein für Thesis-Kern; ja nur wenn E-02 ≠ a und Zeit nach R7 reicht | R8-Suchpfad | nein — R8 läuft mit Fake-Provider + manuell hinzugefügten Quellen, ehrlich gelabelt |
| E-06 | Security-Level supervised beta | a) nur synthetisch/anonymisiert; b) echte D2-Daten | a zuerst; b nur nach bestandenem D2-Gate (evaluation-and-beta-gates.md) | R9-Gate-Umfang | a |
| E-07 | Beta-Betreuungsmodell | wer superviset, Vorfallsmeldung, Nutzerkreis, Dauer | schriftlich vor erstem Beta-Nutzer | Beta-Start | keine Beta |
| E-08 | Evaluationsdaten | welcher echte Antrag darf anonymisiert verwendet werden; wer anonymisiert; wer prüft | 1 echter anonymisierter Fall anstreben; ohne ihn Wirkungsclaim als Hypothese/Limitation führen | R9-Auswertung, Thesis-Claim | nur synthetische Fälle |
| E-09 | Sprachstrategie Feldtexte | Zielsprache je Feld (DE/EN) gemäss Portalanforderung — anhand offizieller Unterlagen klären, nicht raten [Annahme] | prüfen und je Feld in Registry hinterlegen | R5-Vorschlagssprache | Vorschlagssprache = aktuelle Feldsprache; kein Zwang |
| E-10 | Azure-/Enterprise-Zielarchitektur dokumentieren | ja (als Post-MVP-Kapitel: Key Vault, Managed Identity, Postgres, Region) / nein | ja — als Doku-Kapitel, nicht als Implementierung; stärkt Beta-D2-Pfad und Thesis-Ausblick | nichts (reine Doku) | nein |
| E-11 | Partnerrecherche im Scope | ja / nein | nein (v1-Backlog bestätigt); HITL-Konzept als Ausblick dokumentieren | — | nein |
| E-12 | Testdaten-Policy freigeben | Policy-Text (Anonymisierungsregeln, Repo-Verbot für Rohdaten, Review-Pflicht) | in R0 unterschreiben | erster Goldfall, Gate-PDF-Fixture | keine Fixtures mit realem Bezug |
| E-13 | Gate-Freigaben | R9-Beta-Gate und ggf. D2-Gate formal freigeben | Owner-Unterschrift auf Gate-Report | Beta-Start | keine Beta |

Zeitkritisch: E-01, E-02, E-12 in Woche 1 (R0). E-03/E-04/E-05 spätestens vor R5-Start. E-06–E-08, E-13 vor R9-Abschluss.
