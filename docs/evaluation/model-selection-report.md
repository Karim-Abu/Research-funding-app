# Model-Selection-Report — Modellroute je Agentenrolle (A1/A2/A3)

**Status: `not_run` (Live-Evaluation ausstehend — Checkpoint A: Keys + Preise).**
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

## 6. Blinde Human-Rubrik

Rubriken: [`blind_rubric_a2.md`](blind_rubric_a2.md) (8 Kriterien) und
[`blind_rubric_a3.md`](blind_rubric_a3.md) (8 Kriterien); anonymisiert
(Model A/B/C/…), randomisierte Reihenfolge, ≥2 Wiederholungen je Modell/Feld;
Review-Zeit und Rework je Einheit erfasst. Ergebnisse: _ausstehend._

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
Contract-Primaries wäre eine separate, freigabepflichtige Änderung.

## 10. Bekannte Limitationen

Siehe [`Known_Limitations.md`](Known_Limitations.md) (Abschnitt
Rollen-Modell-Evaluation): Boundary-Proxy, Sprachheuristik, Einzel-Rater,
Regex-Adjudikation, Preisfenster.

## 11. Reproduzierbarkeit

```powershell
# Voraussetzungen: Keys + AGENT_MODEL_*_ID + Preise in backend/.env
$env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
backend\.venv\Scripts\python.exe scripts\run_provider_preflight.py
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a1
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a2
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a3
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py blind --role a2
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py blind --role a3
# Blindbögen menschlich ausfüllen, dann ingest --role a2/a3 --scores <csv>
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a1 --cases H1 --allow-holdout
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a2 --cases H1 --allow-holdout
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py run --role a3 --cases H1 --allow-holdout
backend\.venv\Scripts\python.exe scripts\run_role_model_eval.py report
```

Kostenloser Probelauf des gesamten Zyklus: gleiche Befehle mit `--fake`
(Samples als `fake_dryrun` markiert — nie eine Live-Aussage).
