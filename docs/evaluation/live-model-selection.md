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

### 5b. Harte A2-Disqualifikationen (Auftrag)

Ein Kandidat mit bestätigter harter DQ scheidet für die Rolle aus. Die fünf
Kriterien mappen auf bestehende Detektoren
(`role_model_scoring.a2_hard_disqualifications`; im Summary als
`hard_dq_fields`/`hard_dq_by_name`):

| DQ | Quelle | Adjudikation |
|---|---|---|
| `dq_invented_fact` (erfundene Zahl/Organisation/Patent-ID) | `fatal_invented_number` / `fatal_invented_partner` / `fatal_invented_patent` | menschlich (Regex-Verdacht) |
| `dq_wrong_language` (falsche Antragssprache) | Gate 4 `language_consistent` | menschlich (`language_ok` im Blindbogen ist massgeblich; Kurztexte < 30 Wörter → Heuristik `not_run`) |
| `dq_review_notes_in_prose` (Portalfragen/Review-Notizen in finaler Prosa) | Gate 7 `no_review_notes_as_prose` | menschlich |
| `dq_char_limit` (Zeichenlimit verletzt) | Gate 3 `char_limit` | hart |
| `dq_schema_error` (Schemafehler) | Gate 1 `valid_output_schema` | hart |

Erfundene Quellen (`fatal_invented_source`) und die übrigen Fatal-Detektoren
(Leak, Evidence-ID, stiller Fake, fremde Portalsektion) bleiben zusätzlich als
`fatal_candidate`-Ausschlusskandidaten bestehen. A3 hat zusätzlich den
Zähler `funding_decision_claims` (kein Finding darf einen Förderentscheid
formulieren — deterministischer Regex-Check + Rubrik).

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

**Anwendung des Entscheids:** ausschliesslich über `AGENT_MODEL_*_ID` in
`backend/.env` + diese Dokumentation. Die `role_routes` in
`agents_v1_1.yaml` (Frozen Contract) bleiben unverändert; eine Umstellung der
Contract-Primaries erfolgt — wenn überhaupt — erst NACH dem Holdout-Ergebnis
als separate, freigabepflichtige Änderung. Es gibt keine Pauschalaussage
«Modell X ist generell besser» — die Auswahl gilt je Rolle, gestützt auf
Holdout-Qualität, Faktentreue (DQ-/Fatal-Stand), Kosten und Latenz.

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

## 12. Live-Pilot (Owner-Auftrag 2026-07-16)

Begrenzter A2/A3-Vergleich VOR dem Voll-Benchmark — Ziel: nachweisen, dass
echte KI-Ausgaben für A2 Drafting und A3 Critic konkret, plausibel,
Innosuisse-spezifisch und als erster Arbeitsentwurf brauchbar sind.

**Protokoll und Limits** (`scripts/run_role_model_eval.py pilot`, eigenes
Verzeichnis `backend/var/evaluation/role_model_eval_pilot/`):

- Beide Provider-Smokes laufen als **A2-Mini-Smoke** (echtes
  `PortalFieldDraftBundle@v1`-Schema + produktive Validierung, kurzer
  synthetischer Text, `max_output_tokens=25000`; OpenAI `reasoning.effort=low`,
  Anthropic forced tool use ohne effort-Feld). **529-Policy:** transiente
  Providerfehler (overloaded/rate-limit/timeout) sind kein Qualitätsfehler —
  max 4 Gesamtversuche mit Backoff ~10/~30/~60 s + Jitter, `Retry-After` hat
  Vorrang; jeder HTTP-Request zählt zum Call-Cap. **Nach den Smokes STOPP +
  Zwischenbericht.**
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
- Session-Limits (additiv, kein Zähler-Reset): **max 60 echte Provider-Calls,
  max CHF 40 gesamt, max CHF 5 pro Invocation**; vor jedem Call konservative
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
- **Stoppregeln:** nach Phase 2 Blind-Pack erzeugen und zwingend STOPP —
  keine automatische Score-Befüllung, keine automatische Modellwahl, keine
  Registry-/Produktivroutenänderung; der Owner scort selbst. Entscheidung
  getrennt für A2 und A3 — nie ein «Gesamtsieger».

**Ergebnisse:** _ausstehend — aus
`backend/var/evaluation/role_model_eval_pilot/pilot_summary.json` nach
Blind-Ingest._ Limitationen des Piloten: 2 Felder, Einzel-Rater,
Workflow-Smoke ohne Gold-Referenz, Ganzfeld-Bewertung (Kernabschnitte
3.1/4.2 im Fokus der Rubrik).

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
