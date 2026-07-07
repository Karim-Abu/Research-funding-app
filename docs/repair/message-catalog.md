# Message-Katalog — Regel-/Partnermeldungen (R2.6)

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
