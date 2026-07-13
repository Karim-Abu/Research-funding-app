# Decision Log — Entscheidungen des Product Owners / Thesis-Autors

Alle Entscheide sind in R0 zu treffen (Ausnahmen markiert). Ohne Entscheid gilt der genannte Default. «Empfehlung» ist begründeter Vorschlag, kein Fakt.

| ID | Entscheidung | Optionen | Empfehlung | Blockiert | Default ohne Entscheid |
|---|---|---|---|---|---|
| E-01 | PDF-Gate: Import bauen? | Nachtest mit echtem Innolink-PDF; ≥ ~60 % Mapping-Quote = bauen, sonst streichen [Doc: Spike] | Test sofort durchführen; Entscheid dem Ergebnis folgen | R3 vs. R3' | R3' (Fallback), Import gestrichen mit Spike-Begründung |
| E-02 | Provider-Policy für D2 | a) nur Fake/Local (Thesis-Demo); b) Enterprise-Cloud mit Auftragsverarbeitung; c) lokales Modell; d) Kombination je Datenklasse | Arbeits-Default schärfen: Thesis zunächst fake/local oder direkte APIs nur mit synthetischen/öffentlichen Daten; echte D2-Daten nur Enterprise/Azure-Zielarchitektur. owner-confirmation-required, nicht finale Entscheidung. | Wirkung von R4, ganz R5-Realbetrieb, R8-Suche | Arbeits-Default: fake/local für Thesis-Kern; direkte APIs nur synthetisch/öffentlich; echte D2-Daten erst nach Owner-Freigabe und Enterprise/Azure-Zielarchitektur. Nicht final entschieden. |
| E-03 | Feldstufe für Beta | A = 8 Felder; B = +INTRO.PREV.SYNERGY, +INTRO.IP.FINDINGS + Attachment-Gates + Submit-Readiness-Checkliste; C = später | B, wenn Zeitbudget nach R6 grün ist; sonst A | Teile von R5/R7b | A |
| E-04 | WP-Minimalstruktur | ja (Titel, Dauer, Stunden je Partner, Konsistenz-Checks) / nein (Limitation dokumentieren) | nein für Thesis-Abschluss, ausser Betreuung verlangt WP-Prüfungen | optionaler R7b-Slice | nein |
| E-05 | Echte Websearch im Scope | ja (Provider gemäss E-02, z. B. Firecrawl-Key vorhanden als Option [Code: settings]) / nein (Fake + URL-/Datei-Quellen) | Arbeits-Default schärfen: echte Websearch nicht im Thesis-Kern. owner-confirmation-required, nicht finale Entscheidung. | R8-Suchpfad | Arbeits-Default: keine echte Websearch im Thesis-Kern; Fake-Provider + manuell hinzugefügte Quellen, ehrlich gelabelt. Nicht final entschieden. |
| E-06 | Security-Level supervised beta | a) nur synthetisch/anonymisiert; b) echte D2-Daten | Arbeits-Default schärfen: supervised beta zuerst nur synthetisch/anonymisiert. Echte D2-Daten erst nach bestandenem D2-Gate. owner-confirmation-required, nicht finale Entscheidung. | R9-Gate-Umfang | Arbeits-Default: nur synthetisch/anonymisiert. Nicht final entschieden. |
| E-07 | Beta-Betreuungsmodell | wer superviset, Vorfallsmeldung, Nutzerkreis, Dauer | schriftlich vor erstem Beta-Nutzer | Beta-Start | keine Beta |
| E-08 | Evaluationsdaten | welcher echte Antrag darf anonymisiert verwendet werden; wer anonymisiert; wer prüft | 1 echter anonymisierter Fall anstreben; ohne ihn Wirkungsclaim als Hypothese/Limitation führen | R9-Auswertung, Thesis-Claim | nur synthetische Fälle |
| E-09 | Sprachstrategie Feldtexte | Zielsprache je Feld (DE/EN) gemäss Portalanforderung — anhand offizieller Unterlagen klären, nicht raten [Annahme] | prüfen und je Feld in Registry hinterlegen | R5-Vorschlagssprache | Vorschlagssprache = aktuelle Feldsprache; kein Zwang |
| E-10 | Azure-/Enterprise-Zielarchitektur dokumentieren | ja (als Post-MVP-Kapitel: Key Vault, Managed Identity, Postgres, Region) / nein | ja — als Doku-Kapitel, nicht als Implementierung; stärkt Beta-D2-Pfad und Thesis-Ausblick | nichts (reine Doku) | nein |
| E-11 | Partnerrecherche im Scope | ja / nein | Arbeits-Default schärfen: Partnerrecherche nicht im aktuellen Scope; HITL-Konzept nur als Ausblick/Backlog. owner-confirmation-required, nicht finale Entscheidung. | — | Arbeits-Default: nein, Partnerrecherche bleibt ausserhalb des aktuellen Scopes. Nicht final entschieden. |
| E-12 | Testdaten-Policy freigeben | Policy-Text (Anonymisierungsregeln, Repo-Verbot für Rohdaten, Review-Pflicht) | in R0 unterschreiben | erster Goldfall, Gate-PDF-Fixture | keine Fixtures mit realem Bezug |
| E-13 | Gate-Freigaben | R9-Beta-Gate und ggf. D2-Gate formal freigeben | Owner-Unterschrift auf Gate-Report | Beta-Start | keine Beta |

Zeitkritisch: E-01, E-02, E-12 in Woche 1 (R0). E-03/E-04/E-05 spätestens vor R5-Start. E-06–E-08, E-13 vor R9-Abschluss.

## Entschieden (Nachträge)

### E-02 — ENTSCHIEDEN am 2026-07-08 (Owner-Bestätigung, Session repair-v2/R4-Planung)

Der Arbeits-Default ist bestätigt und maschinell durchgesetzt (R4.3,
`backend/app/config/provider_policy.py`, `docs/security/provider-policy.md`):
fake/local bleibt Default; direkte OpenAI/Anthropic-Consumer-APIs nur für D0
(öffentlich/synthetisch); echte D2-Daten nur über die Azure/Enterprise-
Zielarchitektur (dokumentiert, nicht implementiert); D3/Unknown blockiert.

### Nachtrag 2026-07-08 — KI-Opt-in für D1/D2 (Owner-Entscheid, Session repair-v2/R4.3)

D1/D2-Projekte dürfen KI nutzen, aber nur: (a) über den **lokalen**
Verarbeitungspfad (heute Fake-Provider, keine externen Calls; contract-konform
via internal/confidential × local_only = allowed), (b) nach **manuellem
Einschalten** im Analyse-Dialog und (c) mit **deutlicher Warnung inkl.
Verstanden-Bestätigung** (`local-ai-confirm-v1`, eine Bestätigung pro
Durchlauf). **D3 (NDA) und Unknown bleiben immer blockiert — auch für den
Fake-Provider.** Dieser Entscheid ersetzt für den lokalen Fake-Pfad die
frühere Auflage «D2 × fake/local nur synthetic/anonymized»; für direkte
OpenAI/Anthropic-APIs gilt die synthetic/anonymized-Beschränkung weiterhin
(`AI_EVAL_MODE=real`, Mapping-Tabelle §3.1).
