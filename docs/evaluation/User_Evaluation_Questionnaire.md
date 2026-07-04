# User Evaluation Questionnaire

Evaluator-facing instrument for a **supervised beta** session. The evaluator-facing questions
are in German (the UI is German); the scaffolding is English to match the other evaluation
docs. This is a **blank template** — record **real** answers only. **Do not fabricate data.**
Timed manual-vs-assisted measures are captured in
[Baseline_Comparison_Template.md](Baseline_Comparison_Template.md); this questionnaire captures
the evaluator's **perceptions and judgements** and complements it (no duplication).

Rating scale unless stated otherwise: **1 = trifft gar nicht zu … 5 = trifft voll zu**
(1 = strongly disagree … 5 = strongly agree). "k. A." = keine Angabe / not applicable.

---

## A. Consent & background (before the session)

- [ ] Ich wurde über Zweck, Ablauf und die **Grenzen des Systems** informiert (siehe Disclosure
      im Session-Protokoll) und nehme freiwillig teil.
- [ ] Mir ist bewusst, dass ausschließlich **synthetische/öffentliche** Demodaten verwendet
      werden und ich **keine echten vertraulichen Inhalte** eingebe.

| Feld | Angabe |
|------|--------|
| Teilnehmer-ID (pseudonym) | |
| Datum | |
| Rolle / Hintergrund (z. B. Forschende:r, Innovationsverantwortliche:r, Admin) | |
| Erfahrung mit Innosuisse-Anträgen (keine / etwas / viel) | |
| Erfahrung mit dem Instrument "Innovationsprojekt mit Umsetzungspartner" (keine/etwas/viel) | |
| Provider-Modus der Sitzung | deterministisch / fake (kein echter Key) |

---

## B. Per-task ratings

Fill one block per demonstrated task (Editor, Review Center, Reliability Quality Summary,
Export, Project-B blocked path). Repeat the table as needed.

**Task:** ________________________________

| # | Aussage | 1 | 2 | 3 | 4 | 5 | k. A. |
|---|---------|---|---|---|---|---|-------|
| B1 | **Nützlichkeit** — Diese Funktion hat mir bei der Antragsarbeit geholfen. | | | | | | |
| B2 | **Vertrauen / Nachvollziehbarkeit** — Ich konnte nachvollziehen, worauf eine Aussage/ein Befund beruht (Beleg/Fundstelle). | | | | | | |
| B3 | **Evidenz-Suffizienz** — Die Einschätzung "belegt / schwach / nicht belegt" war für mich plausibel. | | | | | | |
| B4 | **Prüf-/Review-Aufwand** — Der Aufwand, das Ergebnis zu prüfen, war angemessen. | | | | | | |
| B5 | **Verständlichkeit** — Hinweise, Blocker und Statusanzeigen waren verständlich (ohne technische Codes). | | | | | | |

Kurzkommentar zur Task (optional): ________________________________________________

---

## C. Manual vs. system-assisted value

Perceptions here; the **timed/objective** measures (time to first draft, requirements
identified, etc.) go into [Baseline_Comparison_Template.md](Baseline_Comparison_Template.md).

| # | Aussage | 1 | 2 | 3 | 4 | 5 | k. A. |
|---|---------|---|---|---|---|---|-------|
| C1 | Mit Systemunterstützung würde ich einen ersten belegorientierten Entwurf **schneller** erreichen als rein manuell. | | | | | | |
| C2 | Das System hat mich auf **fehlende Belege oder schwache Aussagen** hingewiesen, die ich manuell evtl. übersehen hätte. | | | | | | |
| C3 | Das System hat mich auf **Fördervoraussetzungen** hingewiesen, die ich manuell evtl. übersehen hätte. | | | | | | |
| C4 | Die Systemunterstützung hat meinen **Prüfaufwand insgesamt gesenkt** (statt erhöht). | | | | | | |

- Wo war die Unterstützung am wertvollsten? ________________________________________
- Wo hat sie **keinen** Mehrwert gebracht oder gestört? ____________________________

---

## D. Usability (Kurzform)

| # | Aussage | 1 | 2 | 3 | 4 | 5 |
|---|---------|---|---|---|---|---|
| D1 | Ich könnte mir vorstellen, dieses System regelmäßig zu nutzen. | | | | | |
| D2 | Das System war unnötig komplex. *(umgekehrt gepolt)* | | | | | |
| D3 | Das System war einfach zu bedienen. | | | | | |
| D4 | Ich brauchte viel Vorwissen, um es zu bedienen. *(umgekehrt gepolt)* | | | | | |
| D5 | Ich habe der Statusanzeige zur Freigabe (blockiert / bereit / veraltet) vertraut. | | | | | |

---

## E. Privacy perception

| # | Aussage | 1 | 2 | 3 | 4 | 5 | k. A. |
|---|---------|---|---|---|---|---|-------|
| E1 | Mir war klar, welche Daten das System verarbeitet und welche es **nicht** nach außen gibt. | | | | | | |
| E2 | Die Erklärung, dass rohe vertrauliche Suchanfragen **nicht gespeichert/gesendet** werden (nur die bereinigte, freigegebene Anfrage), war nachvollziehbar. | | | | | | |

> Disclosure-Hinweis für den Facilitator: deterministische Bereinigung ist **Risikoreduktion,
> keine Geheimhaltungsgarantie**; D2-Live-Recherche bleibt standardmäßig aus
> ([Search_Query_Firewall.md](../security/Search_Query_Firewall.md)).

---

## F. Open questions

- **F1 — Falsche/schwache Ausgaben:** Haben Sie eine Aussage oder einen Befund gesehen, der
  falsch, zu stark oder schlecht belegt war? Welche(n), und woran haben Sie es gemerkt?
  ______________________________________________________________________________
- **F2 — Reliability-Befunde:** Wo haben Sie den Reliability-Hinweisen **zugestimmt** bzw.
  **widersprochen**? ___________________________________________________________
- **F3 — Technischer Evidenz-Export:** Würden Sie dem `technical_evidence`-Export für ein
  **Audit** vertrauen? Warum / warum nicht? ____________________________________
- **F4 — Größte Stärke:** _______________________________________________________
- **F5 — Größtes Risiko / größte Schwäche:** ___________________________________
- **F6 — Was würden Sie zuerst verbessern?** ___________________________________

---

## G. Facilitator note (post-session)

- Beobachtete Diskrepanz zwischen Rating und Verhalten (falls vorhanden): ______________
- Verweis auf den zugehörigen `EvaluationRunSummary` (Teilnehmer-ID / Pfad): ___________

> Auswertung: Ratings immer **gemeinsam mit dem `EvaluationRunSummary`** des Runs lesen — hohe
> `evidence_coverage` bei niedriger `evidence_sufficiency_pass_rate` ist ein **Risikosignal**,
> kein Erfolg. Siehe [Thesis_Evaluation_Mapping.md](Thesis_Evaluation_Mapping.md).
