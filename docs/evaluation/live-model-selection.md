# Live-Model-Selection — Modellroute je Agentenrolle (A1/A2/A3)

**Status Voll-Benchmark: `not_run` (Live-Evaluation ausstehend — Checkpoint A:
Modell-IDs + Preise). Live-Pilot: siehe §12.**
Dieses Dokument wird nach den Dev-/Holdout-Läufen und dem Blind-Scoring mit den
Messdaten gefüllt. Es enthält nie Rohtexte der Modelle — nur Status, Zählwerte,
Metriken, Modell-IDs und Hashes. Es gibt keine Aussage «Modell X ist am besten»
ohne Messdaten; Safety-/Factuality-Gates haben Vorrang vor Textscores.

## 1. Datum und Umgebung

| Eigenschaft | Wert |
|---|---|
| Datum Dev-Läufe | _ausstehend_ |
| Datum Holdout-Lauf | _ausstehend_ |
| Umgebung | Windows 11, `backend/.venv`, frische Temp-SQLite je Lauf (`%TEMP%`) |
| Runner | `scripts/run_role_model_eval.py` (`backend/app/evaluation/role_model_eval.py`) |
| Prompt-SHA (Freeze, Dev == Holdout) | _ausstehend_ |
| Preistabellen-Version (`price_version`) | _ausstehend_ |
| Opt-in-Guards | `CI` ungesetzt · `RUN_REAL_PROVIDER_SMOKE=true` · `AI_EVAL_MODE=real` · Keys in `backend/.env` · Ceiling-Routen: `AGENT_QUALITY_CEILING_ENABLED=true` |

## 2. Kandidaten und exakte Modell-IDs

Routen-Aliase aus `final_backend_contracts_v1_1/agents_v1_1.yaml`
(`model_catalog`), aufgelöst über `AGENT_MODEL_*_ID` in `backend/.env`
(Werte werden beim Lauf aus dem Manifest übernommen):

| Rolle | Kandidaten-Route | env-Setting | Aufgelöste Modell-ID |
|---|---|---|---|
| A1 | `openai_gpt_56_luna_candidate` | `AGENT_MODEL_GPT_56_LUNA_ID` | _ausstehend_ |
| A1 | `anthropic_haiku_45_candidate` | `AGENT_MODEL_CLAUDE_HAIKU_45_ID` | _ausstehend_ |
| A2 | `anthropic_sonnet_5_candidate` | `AGENT_MODEL_CLAUDE_SONNET_5_ID` | _ausstehend_ |
| A2 | `openai_gpt_56_terra_candidate` | `AGENT_MODEL_GPT_56_TERRA_ID` | _ausstehend_ |
| A2 (Ceiling) | `anthropic_fable_5_candidate` | `AGENT_MODEL_CLAUDE_FABLE_5_ID` | _ausstehend_ |
| A2 (Ceiling) | `openai_gpt_56_sol_candidate` | `AGENT_MODEL_GPT_56_SOL_ID` | _ausstehend_ |
| A3 | `openai_gpt_56_terra_candidate` | `AGENT_MODEL_GPT_56_TERRA_ID` | _ausstehend_ |
| A3 | `anthropic_sonnet_5_candidate` | `AGENT_MODEL_CLAUDE_SONNET_5_ID` | _ausstehend_ |
| A3 | `openai_gpt_56_sol_candidate` | `AGENT_MODEL_GPT_56_SOL_ID` | _ausstehend_ |

**Kandidatenbegrenzung (Auftrag):** Der Primärvergleich läuft je Rolle mit genau
**zwei** Kandidaten — A2: `anthropic_sonnet_5_candidate` vs.
`openai_gpt_56_terra_candidate`; A3: dieselben beiden Routen. Die
Ceiling-Routen (`anthropic_fable_5_candidate`, `openai_gpt_56_sol_candidate`)
sind `evaluation_only`, brauchen `AGENT_QUALITY_CEILING_ENABLED=true` und sind
nie Teil der Primärauswahl (separater, optionaler Referenzlauf).

## 3. Rollen-/Skill-/Promptversionen

Je Invocation persistiert (`AgentInvocation`): `role_id`, `role_version`,
`skill_id`, `skill_version`, `prompt_version`, `contract_version` — Quelle:
`final_backend_contracts_v1_1/role_skills_v2.yaml` + sha256-gepinnte
Prompt-Assets (`backend/tests/test_prompt_snapshots.py`). Der Vergleichslauf
friert die Prompts über den manifestierten Prompt-SHA ein; Drift bricht den
Lauf ab.

## 4. Datensatzbeschreibung

| Split | Fall | Beschreibung |
|---|---|---|
| Development | F1 QUALIMON | Industrie-KI, 2 Budget-Blocker, 20 Gold-Findings ([Fallakte](cases/F1_synthetic_case.md), [Gold](cases/F1_gold.json)) |
| Development | F2 TERRAFLUX | Smart-City-Bewässerung, älteres Innolink-Schema, keine Budget-Blocker ([Fallakte](cases/F2_terraflux_case.md), [Gold](cases/F2_gold.json)) |
| Holdout | H1 VOLTRACK | Batterie-Logistik, genau 1 Budget-Blocker, **nie für Prompt-Tuning** ([Fallakte](cases/H1_synthetic_case.md), [Gold](cases/H1_gold.json)) |

Alle Fälle sind synthetisch (Testdaten-Policy R0.4); keine NDA-Daten, keine
unbereinigten personenbezogenen Daten an direkte APIs.

## 5. Automatische Metriken

Definitionen: [`metrics.md`](metrics.md) (A1-Metriken, 10 A2-Gates,
Fatal-Gates, A3-Metriken). Ergebnisse je Rolle/Kandidat (Dev und Holdout
getrennt): _ausstehend — aus `backend/var/evaluation/role_model_eval/summary.json`._

### 5a. Drei Statusdimensionen je Sample

Technische Vertragsvalidität, produktive Eignung und menschliche Bewertbarkeit
sind drei verschiedene Fragen. Sie zu vermischen hiess: ein echtes
Modellverhalten (etwa ein erfundener Referenz-Identifier) blockiert die
technische Kalibrierung, und ein technisch valider Text bleibt der
Blindbewertung vorenthalten — genau die Textqualität, die beurteilt werden
soll. Jedes A2-/A3-Sample führt deshalb (`role_model_scoring.sample_status_dimensions`):

| Dimension | Wahr, wenn |
|---|---|
| `technical_valid` | echter Provider · kein Fake-Fallback · JSON syntaktisch gültig · erwartetes Schema gültig · caller-bound Routing · Usage und Kosten vollständig |
| `production_eligible` | `technical_valid` **und** keine harte Inhalts-DQ (erfundene Zahlen/Partner/Patente/Quellen, unbekannte Evidence-Anchors oder Research-Source-IDs, falsche Sprache, Review-Notizen in finaler Prosa, Zeichenlimit) |
| `human_evaluable` | `technical_valid` **und** ein lesbarer, zum Zielabschnitt gehörender Text bzw. ein lesbares Finding-Bundle (nicht leer, nicht fremdfeldbezogen, nicht strukturell unbrauchbar) |

Ein technisch valider Output mit `dq_unsupported_reference` ist damit
`technical_valid=true`, `production_eligible=false`, `human_evaluable=true`.
Die **technische Kalibrierung** (§12) prüft ausschliesslich `technical_valid`;
inhaltliche DQs bleiben vollständig erhalten, werden je Modell berichtet und
gehen in die gestufte Auswahl (§9) ein — sie werden nie gelöscht, abgeschwächt
oder als technischer Fehler umklassifiziert.

### 5b. Harte A2-Disqualifikationen (Auftrag)

Ein Kandidat mit bestätigter harter DQ scheidet für die Rolle aus
(`role_model_scoring.a2_hard_disqualifications`; im Summary als
`hard_dq_fields`/`hard_dq_by_name`). Reason-Codes sind **ehrlich getrennt**: was
an einem fachlichen oder kontextabhängigen Gate scheitert, bekommt seinen
eigenen Code — `dq_schema_error` bedeutet ausschliesslich ungültiges JSON oder
eine echte Schemaverletzung, nie „irgendein Fehler“.

| DQ | Quelle (Reason-Code des Orchestrators/Gateways bzw. Gate) | Adjudikation |
|---|---|---|
| `dq_invented_fact` | `fatal_invented_number` / `_partner` / `_patent` | menschlich (Regex-Verdacht) |
| `dq_unsupported_numeric_claim` | `invented_numeric_token` | menschlich |
| `dq_unsupported_partner_claim` | `invented_partner_name` | menschlich |
| `dq_unsupported_patent_claim` | `invented_patent_identifier` | menschlich |
| `dq_wrong_field_id` | `section_target_mismatch` (historisch; seit der Caller-Bindung nicht mehr erreichbar) | hart |
| `dq_wrong_section` | Modellinhalt widerspricht der Caller-Bindung (`routing_metadata_mismatch`) | menschlich (inhaltliche Prüfung) |
| `dq_no_candidate_for_field` | `no_candidate_for_field` | hart |
| `dq_tool_contract_error` | `provider_output_not_json` | hart |
| `dq_invalid_target_section` | `invalid_target_section` | hart |
| `dq_wrong_language` | Gate 4 `language_consistent` | menschlich (`language_ok` im Blindbogen ist massgeblich; Kurztexte < 30 Wörter → Heuristik `not_run`) |
| `dq_review_notes_in_prose` | Gate 7 `no_review_notes_as_prose` | menschlich |
| `dq_char_limit` | Gate 3 `char_limit` / `character_limit_exceeded` | hart |
| `dq_missing_structure` | `mandatory_structure_missing`, `section_*`-Strukturcodes | hart |
| `dq_empty_output` | `empty_suggested_text` | hart |
| `dq_unsupported_reference` | `unknown_evidence_anchor` / `unknown_research_source` / `unknown_open_issue` / `new_claim_without_source` | hart |
| `dq_truncated_output` | `provider_output_truncated` (Provider meldet `max_tokens`) | hart |
| `dq_schema_error` | `provider_output_schema_invalid` / `output_schema_not_implemented` | hart |

Erfundene Quellen (`fatal_invented_source`) und die übrigen Fatal-Detektoren
(Leak, Evidence-ID, stiller Fake, fremde Portalsektion) bleiben zusätzlich als
`fatal_candidate`-Ausschlusskandidaten bestehen. A3 hat zusätzlich den
Zähler `funding_decision_claims` (kein Finding darf einen Förderentscheid
formulieren — deterministischer Regex-Check + Rubrik).

### 5c. Erlaubt-Basis des Halluzinations-Gates (AllowedFactsManifest)

Die Frage „ist diese Zahl erfunden?“ ist nur gegen das beantwortbar, was das
Modell **tatsächlich gesehen hat**. Vor jedem Modellaufruf entsteht darum ein
`AllowedFactsManifest` (`app/agents/allowed_facts.py`) aus genau den Komponenten
des finalen Requests — aktueller Feldtext, die nach Budgetierung wirklich
verwendeten Fragmente, strukturierte Projektfakten, bekannte Partner,
Budgetwerte, akzeptierte Research-Fakten, Antragstellerangaben und offene
Angaben (`ctx.visible_components` + `INPUT`-Payload). Weder der gekürzte
Kontextstring allein noch der volle Fallkorpus sind die Basis: was der Budget
gekappt hat, gilt nicht als belegt.

**Eine einzige kanonische Implementierung.** Produktionsgate und Evaluation
lesen dieselbe Erlaubt-Basis und dieselben Detektoren
(`allowed_facts.analyze_claims`); die Evaluation hat keine zweite Wahrheit mehr.
Der frühere Evaluations-Korpus (`_a2_input_corpus`, Exakt-Token-Vergleich) ist
ersatzlos entfallen — er hat bekannte Fixture-Angaben als Erfindung markiert
und hätte unsichtbare Angaben als belegt durchgelassen. Für die Ganzfeld- und
Abschnittsläufe wird das Manifest aus dem realen Request rekonstruiert
(`_a2_field_manifest` / `_a2_manifest_and_language`, reiner Lesevorgang).

Normalisierung (deterministisch): `10'000` = `10’000` = `10 000` = `10000`;
`45.5 %` = `45,5 %` = `45.5%` = `45,5 Prozent`; `CHF 100'000` = `100000 CHF`;
`40–60 %` sind die zwei bekannten Werte 40 und 60; Organisationen sind
gross-/kleinschreibungs-, interpunktions- und umlautvariantentolerant
(`Zürich`/`Zurich`/`Zuerich`). Der Schlüssel ist der Zahlen**wert**, nicht die
Einheit — Einheiten- und Kontexttreue prüfen die inhaltlichen Gates und das
menschliche Review. Echt mehrdeutige Schreibweisen (`1.234` = 1234 oder 1.234)
liefern beide Lesarten; ein Treffer genügt.

Keine Abschwächung: eine wirklich neue Zahl/Organisation/Patent-ID bleibt eine
DQ. Eine aus bekannten Werten **rein deterministisch** berechenbare Zahl (Summe,
Differenz, Produkt, prozentualer Anteil) ist kein Beleg, aber auch keine
Erfindung — sie wird als `derived_numeric_claim` markiert, erzeugt die Warnung
`contains_derived_numeric_claims` und geht ins menschliche Review. Regressions-
tests: `backend/tests/test_allowed_facts.py`, `backend/tests/test_a2_sections.py`.

### 5c-2. Kanonische Antragssprache (kein stiller Deutsch-Default)

Die erwartete Sprache kommt aus der Fallkonfiguration, in dieser Reihenfolge
(`role_model_scoring.resolve_expected_language`): **1.** explizites
`case_language` im Gold · **2.** Draft-/Portalfeldsprache (`A2Context.language`
— dieselbe Quelle, die das Produktionsgate nutzt) · **3.**
Projektantragssprache · **4.** dokumentierte automatische Erkennung als letzter
Fallback. Ist keine Quelle auflösbar, bricht die Bewertung ab, statt still
Deutsch anzunehmen. Gepinnt: **F1 = `en`** (der eingefrorene Antragstext ist
englisch), F2 = `de`, H1 = `de`. Der frühere Default `expected_language="de"`
hat die englischen F1-Ausgaben beider Modelle als Sprachfehler disqualifiziert —
die Fixture selbst fiel durch dieses Gate.

### 5d. Routing-Metadaten: Caller-Bindung (`routing_metadata_source`)

`field_id` und `target_section` kennt der Aufrufer — das Modell muss sie nicht
erraten. Im Einzelfeld-/Einzelabschnittslauf setzt der Caller sie nach
erfolgreicher Schemavalidierung deterministisch aus dem Request (A2:
`field_drafting._bind_routing_metadata`; A3: `run_a3_evidence_consistency(...,
bound_routing=…)`); Artefakte führen `routing_metadata_source=caller_bound`. Ein
A3-Finding verschwindet damit nie mehr wegen einer fehlenden Modell-ID; der
Filter prüft weiterhin Severity, Finding-Schema, Kategorie und inhaltliche
Mindestfelder, und `all_findings_filtered` bleibt `not_evaluable` (nie
`false_consensus`).

Technische Bindung ≠ fachliche Treue: widerspricht der Modellinhalt der Bindung,
wird das als `model_routing_hint_mismatch` gezählt und für A2 als eigener
`dq_wrong_section` geführt — nie still als korrekt überschrieben. Ein Text, der
inhaltlich einen anderen Abschnitt bedient, scheitert unverändert an der
Strukturprüfung.

## 6. Blinde Human-Rubrik

Rubriken: [`blind_rubric_a2.md`](blind_rubric_a2.md) (8 Kriterien) und
[`blind_rubric_a3.md`](blind_rubric_a3.md) (8 Kriterien); anonymisiert
(Model A/B/C/…), randomisierte Reihenfolge, ≥2 Wiederholungen je Modell/Feld;
Review-Zeit und Rework je Einheit erfasst. Der Ingest trennt seit S3 Dev- und
Holdout-Zeilen (`per_candidate_split`) — die Auswahl stützt sich auf die
H1-Zeilen. Ergebnisse: _ausstehend._

**Mapping auf die 6 Auftrag-Kriterien (A2):** Feldrelevanz → `crit_1`;
Struktur und roter Faden → `crit_6` (+`crit_2` Argumentationslogik);
Marktorientierung/Reviewer-Passung → `crit_3`+`crit_4`; Projektspezifität →
`crit_5`; Faktentreue → `crit_7`; erwarteter Nachbearbeitungsaufwand →
`crit_8` + `review_time_min`/`rework_needed`. A3-Auftragskriterien: relevante
Schwächen erkannt → `crit_1`–`crit_6`; False Positives →
`false_positive_rate` (deterministisch); Gruppierung statt Alert-Flut →
`crit_7`; konkrete nächste Aktion → `crit_8`; kein Förderentscheid →
`funding_decision_claims` (deterministisch) + `fatal_suspicion`-Spalte.

## 7. Kosten und Latenz

Kosten pro akzeptablem Output (nur `cost_status=priced`, sonst Tokens pro
akzeptablem Output), Latenz Mittel ± Stdabw., Varianz über Wiederholungen:
_ausstehend._ Preisquellen (offizielle Preisseiten, USD→CHF-Kurs, Datum):
_ausstehend._

## 8. Fehlerbeispiele (redigiert)

_ausstehend — nur redigierte Beschreibungen (Kategorie, Feld, Gate), nie
Rohtexte._

## 9. Auswahl je Rolle und Fallback

| Rolle | Gewählte Route | Fallback | Begründung |
|---|---|---|---|
| A1 Extraction | _ausstehend_ | _ausstehend_ | _ausstehend_ |
| A2 Drafting | _ausstehend_ | _ausstehend_ | _ausstehend_ |
| A3 Critic | _ausstehend_ (Provider ≠ A2-Sieger) | _ausstehend_ | _ausstehend_ |

**Gestufte Entscheidung — kein einzelner Durchschnittsscore.** Die Reihenfolge
ist bindend; ein späteres Kriterium kippt ein früheres nicht.

| # | A2 Drafting | A3 Critic |
|---|---|---|
| 1 | technische Zuverlässigkeit (`technical_valid`-Rate) | technische Zuverlässigkeit |
| 2 | Rate `production_eligible` | Recall relevanter Gold-Schwächen |
| 3 | harte DQ-Rate, insbesondere erfundene Fakten und ungültige Referenzen | False-Positive-Rate |
| 4 | Holdout-Ergebnis (H1) | keine erfundene Förder-, Rechts- oder FTO-Entscheidung |
| 5 | Human-Rubrik (blind) | Priorisierung und Handlungsfähigkeit |
| 6 | Nachbearbeitungsaufwand | Human-Rubrik (blind) |
| 7 | Kosten und Latenz | Kosten und Latenz |

**Anwendung des Entscheids:** ausschliesslich über `AGENT_MODEL_*_ID` in
`backend/.env` + diese Dokumentation. Die `role_routes` in
`agents_v1_1.yaml` (Frozen Contract) bleiben unverändert; eine Umstellung der
Contract-Primaries erfolgt — wenn überhaupt — erst NACH dem Holdout-Ergebnis
als separate, freigabepflichtige Änderung. Es gibt keine Pauschalaussage
«Modell X ist generell besser» und keine Gesamtmodell-Rangfolge — A2 und A3
werden getrennt entschieden.

## 10. Bekannte Limitationen

Siehe [`Known_Limitations.md`](Known_Limitations.md) (Abschnitt
Rollen-Modell-Evaluation): Boundary-Proxy, Sprachheuristik, Einzel-Rater,
Regex-Adjudikation, Preisfenster.

## 11. Reproduzierbarkeit (Voll-Benchmark)

Reihenfolge: **Dev- UND Holdout-Läufe zuerst, dann EIN Blind-Pack, EINE
Scoring-Session, EIN Ingest.** Zwischen Dev und Holdout findet kein
Prompt-Tuning statt (der manifestierte Prompt-SHA erzwingt das —
`prompt_sha_consistent` muss `true` bleiben). Achtung: `blind` erzeugt bei
jedem Aufruf ein NEUES `mapping.json` (Labels werden neu gemischt) — nie
`blind` erneut ausführen, nachdem das Scoring begonnen hat.

```powershell
# Voraussetzungen: Keys + AGENT_MODEL_*_ID + Preise in backend/.env
$env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
backend\.venv\Scripts\python.exe scripts\run_provider_preflight.py

# Dev (F1,F2) — Primärvergleich mit genau zwei Kandidaten je Rolle:
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a2 `
  --candidate anthropic_sonnet_5_candidate --candidate openai_gpt_56_terra_candidate
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a3 `
  --candidate openai_gpt_56_terra_candidate --candidate anthropic_sonnet_5_candidate

# Holdout (H1) — gleiche Kandidaten, gleicher Prompt-SHA:
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a2 `
  --candidate anthropic_sonnet_5_candidate --candidate openai_gpt_56_terra_candidate `
  --cases H1 --allow-holdout
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a3 `
  --candidate openai_gpt_56_terra_candidate --candidate anthropic_sonnet_5_candidate `
  --cases H1 --allow-holdout

# EIN Blind-Pack je Rolle (Dev+Holdout gemeinsam), menschlich scoren, ingest:
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py blind --role a2
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py blind --role a3
# … Bögen ausfüllen (nie KI), dann:
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py ingest --role a2 --scores <csv>
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py ingest --role a3 --scores <csv>
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py report
```

Kostenloser Probelauf des gesamten Zyklus: gleiche Befehle mit `--fake`
(Samples als `fake_dryrun` markiert — nie eine Live-Aussage). A1 analog mit
seinen zwei Kandidaten (`openai_gpt_56_luna_candidate`,
`anthropic_haiku_45_candidate`).

**Pilot-Reihenfolge** (jede call-ausführende Phase legt eine frische Temp-SQLite
an — `needs_db` im Runner muss die Phase kennen, sonst läuft der Lauf gegen
`backend/app.db`):

```powershell
$env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
cd backend   # Settings lesen .env CWD-relativ
..\backend\.venv\Scripts\python.exe ..\scripts\run_role_model_eval.py pilot --phase smoke
..\backend\.venv\Scripts\python.exe ..\scripts\run_role_model_eval.py pilot --phase so_smoke
..\backend\.venv\Scripts\python.exe ..\scripts\run_role_model_eval.py pilot --phase calibrate
# calibrate PASS ⇒ Voll-Lauf + Blind-Pack laufen automatisch, danach STOPP.
..\backend\.venv\Scripts\python.exe ..\scripts\run_role_model_eval.py pilot `
  --phase ingest --role a2 --scores <csv>
```

## 12. Live-Pilot (Owner-Auftrag 2026-07-16)

Begrenzter A2/A3-Vergleich VOR dem Voll-Benchmark — Ziel: nachweisen, dass
echte KI-Ausgaben für A2 Drafting und A3 Critic konkret, plausibel,
Innosuisse-spezifisch und als erster Arbeitsentwurf brauchbar sind.

**Protokoll und Limits** (`scripts/run_role_model_eval.py pilot`, eigenes
Verzeichnis `backend/var/evaluation/role_model_eval_pilot/`):

- Beide Provider-Smokes laufen als **A2-Mini-Smoke** (echtes
  `PortalFieldDraftBundle@v1`-Schema + produktive Validierung, kurzer
  synthetischer Text, `max_output_tokens=25000`; OpenAI `reasoning.effort=low`,
  Anthropic ohne effort-Feld). **529-Policy:** transiente
  Providerfehler (overloaded/rate-limit/timeout) sind kein Qualitätsfehler —
  max 4 Gesamtversuche mit Backoff ~10/~30/~60 s + Jitter, `Retry-After` hat
  Vorrang; jeder HTTP-Request zählt zum Call-Cap. **Nach den Smokes STOPP +
  Zwischenbericht.**
- **Structured-Output-Smokes** (`--phase so_smoke`, Owner 2026-07-17): je ein
  kleiner Anthropic-Call gegen die zwei Kalibrierungsschemata
  (`PortalSectionDraftBundle@v1`, `ReviewFindingBundle@v1`) über
  `output_config.format` — Vorbedingung der Kalibrierung. Bestanden nur mit
  HTTP-Erfolg, bestätigter Modell-ID, ohne Tool-Envelope, schema-valide und
  mit vollständigen Usage-/Kosten-/Latenz-/Request-ID-Daten. Ein 4xx ist ein
  harter STOPP (Status, Error-Type, Request-ID, redigierte Meldung im
  Artefakt) — keine Rückkehr zu forced tool use ohne erneute Freigabe.
- **Kalibrierung** (`--phase calibrate`): F1, beide Kandidaten, Sections
  3.1+4.2, je 1 Replikation für A2 und A3 (8 Zellen). Geprüft wird
  ausschliesslich die **technische Vertragsvalidität** (§5a): 4/4 A2 und 4/4 A3
  `technical_valid`, Routing 8/8 `caller_bound`, Usage 8/8 bepreist, kein
  Fake-Fallback, keine Harness-/Scoring-Ausnahme. Inhaltliche DQs sind
  Modellbefunde und blockieren nicht. Bei PASS läuft der Voll-Lauf automatisch
  an, danach Blind-Pack + zwingender STOPP; bei FAIL: STOPP und technischer
  Bericht, kein Blind-Pack.
- **Offline-Neubewertung** (`--phase rescore`): korrigiertes Scoring auf
  gespeicherten Outputs — **null Provider-Calls**. Zulässig, weil Modellinput,
  Prompt, Schema, Providerparameter und Outputtext unverändert bleiben; die
  Erlaubt-Basis wird aus derselben Fallkonfiguration neu montiert
  (`manifest_source=rederived_offline`). Grenze: die Namensraum-Tags geseedeter
  IDs sind je Lauf zufällig, aus IDs stammende Ziffernfolgen im Manifest können
  darum abweichen — Inhaltszahlen, Partner und Patente sind identisch. Reichen
  die Artefakte nicht, wird die Kalibrierung vollständig neu ausgeführt.
- Phase `run` (erweiterte Phase 2, nur bei 2/2 Smoke-PASS): Dev F1+F2 und
  Holdout H1; **abgeleitete Pilot-Registry** (nur Pilotpfad):
  `max_output_tokens=25000` für die A2-/A3-Profile, Terra
  `reasoning_effort=high`, Sonnet adaptiver Modell-Standard,
  `max_cost_chf=5.00` je Invocation.
  - **A2:** Sonnet-5 vs. Terra auf den 2 Kernfeldern VC (Kern 3.1) und SOL
    (Kern 4.2), **2 Replikationen** je Modell×Fall — identischer Input,
    Promptversion, Field-Skill, Quellen, Zeichenbudget, Output-Schema;
    harte DQs vorgelagert.
  - **A3 (fairer Vergleich):** beide Modelle prüfen je Fall DENSELBEN
    eingefrorenen fehlerhaften Draft (injizierte unbelegte Zahlen),
    2 Replikationen je Modell×Fall — Gold-Scoring inkl. `false_consensus`
    gültig; nie Rangfolge aus unterschiedlichen A2-Ausgangstexten.
  - **Workflow-Smoke:** genau 2 Cross-Läufe (Sonnet-A2→Terra-A3,
    Terra-A2→Sonnet-A3, F1/rep1) — Multi-Agent-Nachweis, nie alleinige
    A3-Rangfolge-Quelle (Gold-Scoring dort nicht anwendbar).
- Session-Limits (additiv, kein Zähler-Reset): **max 160 echte Provider-Calls,
  max CHF 80 gesamt, max CHF 8 pro Invocation**; vor jedem Call konservative
  Maximal-Reservierung, nach jedem Call Usage/Reasoning-Tokens/Latenz/Kosten/
  Request-ID/Termination-Reason aktualisiert (auch failed/incomplete/
  truncated/schema_invalid); unbekannte Kosten nie als 0. Kein stiller
  Fallback; nur synthetische Fälle (D0).
- Phase `blind`/`ingest --role a2|a3`: **getrennte Human-Rubriken** (je 1–5,
  blind, Model A/B). A2 (10): Projektspezifität · Abdeckung Portalfeld ·
  Innosuisse-/Reviewer-Passung · fachliche Plausibilität · Argumentationslogik ·
  Markt-/Nutzerorientierung · Präzision/Lesbarkeit ·
  Faktentreue/Evidenzdisziplin · Qualität der offenen Fragen ·
  Nachbearbeitungsaufwand. A3 (8): relevante Schwächen erkannt · geringe
  False-Positive-Rate · Priorisierung nach Relevanz · sinnvolle Gruppierung ·
  konkrete nächste Aktion · Evidence-/Unsicherheitsbewusstsein · kein
  Förder-/Rechts-/FTO-Entscheid erfunden · praktischer Nutzen für die
  Überarbeitung.
- **Blind-Pack-Aufnahme:** alle `technical_valid=true` **und**
  `human_evaluable=true` Outputs — ausdrücklich auch
  `production_eligible=false`, damit die sprachliche und fachliche
  Textqualität blind beurteilt werden kann. Ein an einem Inhaltsgate
  abgelehnter Vorschlagstext wird dafür aus dem Roh-Bundle geborgen
  (`suggestion_text_source=recovered_from_rejected_bundle`). Nicht aufgenommen:
  schema-invalide, leere, fremdfeldbezogene oder technisch nicht auswertbare
  Outputs. Der Bogen enthält **keine** Hinweise auf Modell, Provider, Kosten,
  Latenz, DQs, `production_eligible` oder Referenzfehler; Human-Scores und
  technische Befunde werden erst nach dem Ingest zusammengeführt.
- **Stoppregeln:** nach Phase 2 Blind-Pack erzeugen und zwingend STOPP —
  keine automatische Score-Befüllung, keine automatische Modellwahl, keine
  Registry-/Produktivroutenänderung, keine Promptoptimierung aus H1; der Owner
  scort selbst. Entscheidung getrennt für A2 und A3 — nie ein «Gesamtsieger».

**Provider-Vertrag je Route** (im Artefakt als `structured_output_mode`):
OpenAI = Responses `text.format` mit `strict: true`; Anthropic = Messages
`output_config.format` (`type: json_schema`) — **kein** forced tool use, kein
`emit_structured_output`, kein Envelope-Unwrapping, kein Prefill, keine
non-default Sampling-Parameter, kein manuelles `budget_tokens`,
`max_tokens=25000`, adaptiver Modell-Standard. Die Schema-Form liefert für beide
`providers/json_schema.strict_schema` (`additionalProperties: false`,
vollständige `required`-Listen, kein `default`); ein Guard-Test hält die zwei
Kalibrierungsschemata frei von Keywords, die Structured Outputs ablehnen. Der
frühere 4xx dieses Pfades entstand mit der überholten Feldform. Produktive
Registry, Primary-Routen und Gateway-Defaults bleiben unverändert — die native
Oberfläche kommt ausschliesslich über die Route-Capability
`structured_output_mode` der abgeleiteten Pilot-Registry.

**Archivierte Läufe** (Auditspur, nie Bewertungsgrundlage; Calls/Kosten bleiben
im kumulativen Budget): `invalid_harness_run_2026-07-16` (Harnessfehler) und
`invalid_harness_run_2026-07-16_calibration` (technischer Integrationslauf unter
dem alten Vertrag). Deren `mapping.json` wird nie weiterverwendet.

### 12a. Ergebnisse Voll-Lauf (2026-07-17) — Human-Rubrik ausstehend

Technische Kalibrierung **8/8 bestanden** (A2 4/4, A3 4/4 `technical_valid`,
Routing 8/8 caller-bound, Usage 8/8 bepreist, kein Fake-Fallback). Voll-Lauf:
F1+F2+H1 × Sections 3.1/4.2 × 2 Replikationen × 2 Kandidaten = 24 A2- und 24
A3-Zellen + 2 Workflow-Smokes. **Keine Providerfehler, keine Retries.**

| A2 (n=12 je Modell) | `anthropic_sonnet_5` | `openai_gpt_56_terra` |
|---|---|---|
| `technical_valid` | 12/12 | 12/12 |
| `production_eligible` | **1/12** (H1: 0/4) | **12/12** (H1: 4/4) |
| `human_evaluable` | 12/12 | 12/12 |
| harte DQ | `dq_unsupported_reference` 11 | — |
| Tokens in/out | 90 630 / 94 053 | 49 415 / 29 280 |
| Kosten · Median-Latenz | CHF 0.905 · 80.5 s | CHF 0.454 · 27.4 s |

| A3 fair (n=12 je Modell) | `anthropic_sonnet_5` | `openai_gpt_56_terra` |
|---|---|---|
| `technical_valid` | 12/12 | 12/12 |
| evaluierbar | 12/12 | 11/12 (1× `all_findings_filtered`) |
| Gold-Recall (injizierte Schwächen) | **34/36** | **27/33** |
| Findings (akzeptiert/empfangen) | 58/58 | 36/39 (3× `unknown_evidence_anchor`) |
| Findings ohne Treffer auf eine Injektion | 24 | 9 |
| `funding_decision_claims` | 0 | 0 |
| Tokens in/out | 43 773 / 57 373 | 18 983 / 18 846 |
| Kosten · Median-Latenz | CHF 0.534 · 48.6 s | CHF 0.266 · 17.7 s |

**Referenzdisziplin — beide Modelle, verschiedene Rollen.** Sonnet setzt in A2
die im Kontext sichtbaren Fakt-IDs (`rme-fact-…`) in `evidence_anchor_ids`
bzw. `research_source_ids`; advisory A1-Fakten sind aber weder Belege noch
Research-Quellen → `dq_unsupported_reference` (11/12). Terra zeigt dasselbe
Muster in A3: 3 Findings mit unbekannten Evidence-Anchors, eine Zelle dadurch
`not_evaluable`. Beides bleibt als Modellbefund stehen — keine automatische
Umschreibung, keine stille Entfernung, keine modellspezifische
Promptänderung vor dem Abschluss des Vergleichs.

«Findings ohne Treffer auf eine Injektion» ist eine **Obergrenze, keine
False-Positive-Rate**: der Fixed Draft trägt auch echte Schwächen ausserhalb der
injizierten. Die belastbare FP-Beurteilung liefert `crit_2` der Blind-Rubrik.

**Blind-Pack:** 24 A2-Einheiten (12/12 je Label) und 25 A3-Einheiten (23
`a3_fair` + 2 `a3_workflow_smoke`) — alle `technical_valid` **und**
`human_evaluable`, inklusive `production_eligible=false`. Geprüft: keine
Modell-, Provider-, Kosten-, Latenz-, DQ- oder Eignungshinweise in Bögen und
Markdown.

**Ergebnisse Human-Rubrik:** _ausstehend — Owner scort blind; danach
`pilot --phase ingest --role a2|a3`._ Limitationen des Piloten: 2 Felder,
Einzel-Rater, Workflow-Smoke ohne Gold-Referenz, Kernabschnitte 3.1/4.2 im
Fokus, Gold-Recall nur gegen die injizierten Schwächen.

### 12b. Quality-Ceiling (optionaler Folgeschritt — noch NICHT ausführen)

Nach dem Sonnet-/Terra-Bericht kann als separater, einzeln freizugebender
Schritt ein Ceiling-Referenzlauf folgen: `openai_gpt_56_sol_candidate`
(`AGENT_MODEL_GPT_56_SOL_ID`) und `anthropic_fable_5_candidate`
(`AGENT_MODEL_CLAUDE_FABLE_5_ID`), beide `evaluation_only` und nur mit
`AGENT_QUALITY_CEILING_ENABLED=true`. Voraussetzungen: Owner setzt die
Modell-IDs + Preis-Metadaten selbst (Regel: nie raten) und gibt Budget/Calls
separat frei. Bis dahin: keine Calls, keine IDs, keine Preise.

## 13. Supervised live flow (Anforderung 11)

Abschliessender begleiteter Live-Durchlauf nur mit synthetischem/anonymisiertem
Fall nach [`demo-runbook.md §6b`](../demo/demo-runbook.md): realer A2-Vorschlag →
reale Firecrawl-Query (Query-Freigabe) → eine Quelle übernehmen und inhaltlich
prüfen («stützt»/«stützt teilweise»/«stützt nicht») → Redraft mit sichtbarer
Research-Quelle («Verwendete Research-Quellen») → A3-Finding → Nutzer übernimmt
oder verwirft ausdrücklich. Evidenz:
`backend/var/evaluation/supervised_live/<datum>/`. Ergebnis: _ausstehend._
