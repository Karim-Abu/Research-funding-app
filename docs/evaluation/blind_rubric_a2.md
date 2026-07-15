# Blinde Human-Rubrik A2 (Drafting) — 8 Kriterien, je 1–5 Punkte

Gilt für das Blind-Scoring der Rollen-Modell-Evaluation
(`scripts/run_role_model_eval.py blind --role a2`). Bewertet werden
anonymisierte Feldvorschläge («Model A/B/C/…», randomisierte Reihenfolge).

**Regeln:**

- Nur Menschen bewerten; eine KI darf niemals selbst scoren (auch nicht «vorbefüllen»).
- `mapping.json` erst NACH Abschluss aller Bewertungen öffnen.
- Je bewerteter Einheit `review_time_min` (Minuten, die die Prüfung gedauert hat)
  und `rework_needed` (ja/nein: wäre vor einer Übernahme substanzielle
  Nacharbeit nötig?) erfassen.
- `fatal_suspicion`: Freitext, falls ein Fatal-Verdacht besteht (erfundene
  Zahl/Quelle/Partner/Patent, Rechts-/Eligibility-Freigabe, fremder
  Portalabschnitt) — dient der Fatal-Adjudikation.
- 3 ist «brauchbar mit normaler Nacharbeit»; 5 vergeben, wenn es kaum besser
  ginge; 1, wenn der Text für das Feld unbrauchbar ist.

CSV-Spalte → Kriterium (Skala 1–5):

| Spalte | Kriterium | 1 (ungenügend) | 3 (brauchbar) | 5 (exzellent) |
|---|---|---|---|---|
| `crit_1_feldrelevanz_vollstaendigkeit` | Feldrelevanz und Vollständigkeit | verfehlt die Feldfrage oder lässt Kernaspekte weg | beantwortet die Feldfrage, einzelne Lücken | deckt alle Pflichtaspekte des Feldes präzise ab |
| `crit_2_logische_argumentation` | Logische Argumentation | Behauptungen ohne roten Faden | nachvollziehbar mit Sprüngen | stringente, belastbare Argumentationskette |
| `crit_3_markt_nutzerorientierung` | Markt-/Nutzerorientierung | kein erkennbarer Markt-/Nutzerbezug | Markt/Nutzer benannt, aber generisch | konkreter Kunden-/Marktbezug, plausible Verwertung |
| `crit_4_innosuisse_reviewer_passung` | Innosuisse-/Reviewer-Passung | ignoriert Gutachter-Erwartungen (Innovationsgehalt, Umsetzung) | passt grob zum Innosuisse-Raster | liest sich wie ein starker Innosuisse-Antragstext |
| `crit_5_spezifitaet_statt_buzzwords` | Spezifität statt Buzzwords | Schlagwortprosa ohne Substanz | teils konkret, teils Floskeln | durchgehend spezifisch, projektbezogen |
| `crit_6_struktur_lesbarkeit` | Struktur und Lesbarkeit | wirr, schwer lesbar | ordentlich gegliedert | klare Struktur, sofort erfassbar |
| `crit_7_faktentreue_evidence_disziplin` | Faktentreue/Evidence-Disziplin | erfindet oder verdreht Angaben | bleibt bei den Eingaben, kennzeichnet nicht alles | nutzt nur Eingaben, kennzeichnet jede Lücke/Evidenzgrenze |
| `crit_8_nuetzlichkeit_nachbearbeitung` | Tatsächliche Nützlichkeit / erwartete Nachbearbeitungszeit | Neuformulierung wäre schneller | spart Zeit, braucht klare Nacharbeit | fast übernahmefertig (nach menschlicher Prüfung) |

Zuordnung zur Gewichtung (Auftrag; automatisch in `summary.json`):
Faktentreue/Evidenz 25 % ← crit_7 · Feldabdeckung/Innosuisse-Passung 20 % ←
crit_1, crit_4 · Argumentation/Nützlichkeit 20 % ← crit_2, crit_5, crit_8 ·
Markt-/Reviewer-Orientierung 10 % ← crit_3 · Struktur/Lesbarkeit 10 % ← crit_6 ·
Konsistenz/Zeichenbudget 10 % ← deterministische Gates · Kosten/Latenz 5 % ←
relative Messwerte. Fatal-Gates haben immer Vorrang vor dem Textscore.
