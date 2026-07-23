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
