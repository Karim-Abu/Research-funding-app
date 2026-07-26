# BACKEND-01 — Fehlschläge

Vollständiger Lauf: **1514 Tests, 6 failures, 0 errors, 4 skipped, 550.0 s, Exit 1.**

Gezielter, unveränderter Wiederholungslauf der 6 Fehlschläge (Flakiness-Prüfung,
`rerun_failures.log`): **4 von 6 reproduzieren, 2 bestehen isoliert.**

| Test | Voll-Suite | isoliert | Einordnung |
|---|---|---|---|
| `test_live_readiness.py::test_fresh_persisted_route_preflight_expires` | FAIL | FAIL | **deterministisch** — `assert row.pricing_version == "test-v1"` erhält `'2026-07-25.1'` (= `PRICE_TABLE_VERSION` aus HEAD). Der Test erwartet eine gepatchte Version, bekommt die echte. |
| `test_eval2_real_smoke.py::test_run_llm_case_with_fake_adapter_meters_schema_failure` | FAIL | FAIL | **deterministisch** |
| `test_live_llm_phase2_full_dry_run.py::test_phase2_prepare_web_resume_llm_full_offline_dry_run` | FAIL | FAIL | **deterministisch** |
| `test_a2_generation.py::test_preflighted_synthetic_live_a2_is_truthfully_model_generated` | FAIL | FAIL | **deterministisch** |
| `test_a2_generation.py::test_missing_input_metadata_cannot_introduce_a_new_number` | FAIL | PASS | **reihenfolgeabhängig** (Zustandsleck in der Voll-Suite) |
| `test_demo_seed.py::test_isolated_test_db_requires_exactly_two_demo_projects` | FAIL | PASS | **reihenfolgeabhängig** |

Es wurde **nichts repariert** und **kein Test angepasst**. Die Fehlschläge bleiben
als Ergebnis dieses Laufs stehen.
