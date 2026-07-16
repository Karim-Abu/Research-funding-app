# Blinde Human-Rubrik A3 (Critic) — 8 Kriterien, je 1–5 Punkte

Gilt für das Blind-Scoring der Rollen-Modell-Evaluation
(`scripts/run_role_model_eval.py blind --role a3`). Bewertet werden
anonymisierte Finding-Listen («Model A/B/C/…», randomisierte Reihenfolge) zu
identischen, eingefrorenen Entwürfen — je Fall eine Baseline-Variante und eine
absichtlich fehlerhafte Variante (injizierte unbelegte Zahlen).

**Regeln:** wie A2-Rubrik (nur Menschen, `mapping.json` erst nach Abschluss,
`review_time_min`/`rework_needed` je Einheit, `fatal_suspicion` bei
Fatal-Verdacht). Wichtig bei der `flawed`-Variante: Ein Kandidat, der die
injizierte unbelegte Zahl NICHT meldet, hat einen falschen Konsens — das fliesst
zusätzlich hart in die deterministische Metrik `false_consensus` ein.

CSV-Spalte → Kriterium (Skala 1–5):

| Spalte | Kriterium | 1 (ungenügend) | 3 (brauchbar) | 5 (exzellent) |
|---|---|---|---|---|
| `crit_1_baseline_kpi_luecken` | Erkennt Baseline-/KPI-Lücken | übersieht fehlende Baselines/Messmethoden | erkennt die offensichtlichen | erkennt alle inkl. Validierungszeitpunkt |
| `crit_2_methodology_abstraction` | Erkennt Methodology Abstraction | akzeptiert vage Methodik | benennt vage Stellen teilweise | deckt jede unkonkrete Methodik-Aussage auf |
| `crit_3_schwache_sota_differenzierung` | Erkennt schwache SOTA-Differenzierung | akzeptiert generisches SOTA | erkennt es grob | benennt präzise, was am SOTA-Vergleich fehlt |
| `crit_4_unbelegte_marktclaims` | Erkennt unbelegte Marktclaims | übersieht unbelegte Zahlen/Claims | erkennt die grössten | erkennt alle inkl. Einsparungs-/Umsatzannahmen |
| `crit_5_partner_rollenluecken` | Erkennt Partner-/Rollenlücken | übersieht fehlende Partner-Evidenz | erkennt sie teilweise | benennt Lücken in Eignung/Rollen/Evidenz vollständig |
| `crit_6_scope_wp_risk_probleme` | Erkennt Scope-/WP-/Risk-Probleme | ignoriert Umfangs-/Risikofragen | erkennt einzelne | systematische Sicht auf Scope/Arbeitspakete/Risiken |
| `crit_7_gruppierung_statt_alertflut` | Gruppiert statt Alert-Flut | Duplikat-/Splitterflut | überwiegend gebündelt | eine klare, priorisierte Aufgabe je Problem |
| `crit_8_konkrete_naechste_aktion` | Liefert konkrete nächste Aktion | keine umsetzbare Empfehlung | teils konkret | jede Meldung mit konkretem, richtigem nächsten Schritt |
