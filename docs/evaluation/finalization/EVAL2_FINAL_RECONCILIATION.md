---
title: "EVAL2 — Finalabgleich"
date: 2026-07-26
commit: 7f09c1f
branch: stabilize/eval3-final-01
status: final
tags: [eval2, reconciliation, final]
---

# EVAL2 — Finalabgleich

Fortschreibung von [[EVAL2_IMPLEMENTATION_RECONCILIATION]] (EVAL3-PRE-01,
2026-07-25) auf den eingefrorenen Stand `7f09c1f`.

**Die PRE-01-Fassung bleibt unverändert erhalten.** Dieses Dokument nennt nur,
was sich seither geändert hat — und was ausdrücklich gleich geblieben ist.

## 1. Was sich geändert hat

| FDC | Bereich | PRE-01 | FINAL-01 | Grund |
|---|---|---|---|---|
| FDC-14 | Markt-/Konkurrenzvergleich | `implemented`, Frontend-WIP nicht committet | **`implemented`, vollständig verifiziert** | Umbau als `aedee80` + `7f09c1f` integriert; tsc/lint/build grün, 653 Vitest-Tests inkl. neuer Markt- und Reliability-Viewmodel-Tests |
| FDC-20 | Provider-/Policy-Gateway | `partially-tested` — zwei A2-Tests und `test_live_readiness` rot | **`tested-pass`** | Ursache war die USD-first-Umstellung; Tests auf Katalog-Modell-IDs armiert (`068603f`), keine Assertion abgeschwächt |
| FDC-23 | Laufzeit- und Kostentransparenz | `partially-implemented`, `partially-tested` | **`implemented`, `tested-pass`** | `claude-haiku-4-5-20251001` katalogisiert; die A1-Route ist wieder bepreisbar und meldet nicht länger `live_price_metadata_missing` |
| — | *neu* Halluzinationsschutz | in PRE-01 als Reihenfolgeabhängigkeit fehlgedeutet | **`product-defect` behoben** | UUID-Ziffern und Telemetrie flossen in die Erlaubt-Basis; `_facts_only` filtert sie (`cf668c9`) |

## 2. Was unverändert gilt

| FDC | Status | Begründung |
|---|---|---|
| **FDC-06** — auswählbare KI-Textvarianten | **`not-found`** | Weiterhin ein Vorschlag je (Draft, `base_version_id`, `target_section`); `get_proposed_for` nutzt `db.scalar`, «Neuen Vorschlag erzeugen» **ersetzt**. Bewusst nicht nachträglich implementiert. |
| **FDC-13** — 64 Portal-Quality-Gates | **`contract-only`** | `loader.py:222` liest nur `official_core_rules`; `QG.`/`XF.` kommen im Code nicht vor. Bewusst nicht implementiert. |
| FDC-13b — implementierte Quality-Ebene | `implemented`, `tested-pass` | `review/checks.py` + Rubric v0, nie blockierend — eine **andere** Ebene, kein Ersatz für FDC-13. |
| FDC-01…05, 07…12, 15…19, 21, 22 | unverändert `implemented` / `tested-pass` | Keine Änderung am jeweiligen Codepfad; alle zugehörigen Tests im Finallauf grün. |

## 3. Endstand über alle 23 Designbereiche

| Implementierungsstatus | Anzahl |
|---|---|
| `implemented` | **21** |
| `contract-only` | 1 (FDC-13) |
| `not-found` | 1 (FDC-06) |

| Teststatus | Anzahl |
|---|---|
| `tested-pass` | **21** |
| `n/a` (nicht implementiert) | 2 |

Kein Bereich steht mehr auf `partially-tested`.

## 4. Was dieser Abgleich nicht behauptet

- **`tested-pass` heisst:** die genannten Tests liefen im Finallauf und waren
  grün. Es heisst nicht, dass der Designbereich fachlich vollständig geprüft ist.
- Die zwei offenen Bereiche (FDC-06, FDC-13) sind **Scope-Entscheidungen**,
  keine Defekte — und wurden nicht nachträglich implementiert, um die Bilanz zu
  verbessern.
- Die Trennung von Implementierung, Testexistenz und Testergebnis aus PRE-01
  gilt unverändert weiter.

Belege: [[EVAL3_FINAL_01_REPORT]] · [[MARKET_UI_FINAL_VERIFICATION]] ·
[[MVP_REQUIREMENT_BASELINE]] · [[FINAL_STABILIZATION_FINDINGS]]
