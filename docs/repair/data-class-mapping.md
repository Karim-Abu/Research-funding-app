# Datenklassen v2 — Owner-Mapping-Tabelle (R4.1)

> **Stand: Owner-Review 2026-07-08 eingearbeitet — Freigabe zum Commit ausstehend.**
> Erstellt am 2026-07-08 als Voraussetzung für R4.1 (GO-Auflage 1: erst Tabelle, dann
> Owner-Review, keine Codeänderung vor Freigabe). Abgeleitet aus dem bestehenden Code —
> diese Tabelle **ändert keine** Backend-Semantik, sie macht das Mapping explizit und
> ergänzt den neuen UI-Modus «NDA / gesperrt» (D3).
>
> Quellen: `lib/data-classification.ts` (FLAT_TO_CLASSIFICATION),
> `backend/app/security/data_class.py` (derive_data_class),
> `backend/app/security/policy_matrix.py` (Tool-Matrix, fail-closed),
> `backend/app/agents/data_policy.py` (evaluate),
> `lib/intake-store.ts` (Legacy-Normalisierung),
> `docs/security/Data_Classification_and_Tool_Policy.md` (M9J).

## 1. Zielmodell

- Die UI bietet **vier** wählbare Vertraulichkeitsstufen: Öffentlich (D0), Intern (D1),
  Vertraulich (D2), **NDA / gesperrt (D3, neu)**.
- **Unknown ist kein wählbarer Modus.** Fehlende/unklare Einstufung ist der
  fail-closed-Default: alles blockiert, bis klassifiziert ist.
- **Webresearch ist keine eigene Datenklasse und kein eigener Modus.** Sie ist eine
  Eigenschaft der Klasse gemäss `policy_matrix` (§3/§5). Der bestehende Run-Schalter
  «Web» darf die Matrix nur weiter einschränken, nie lockern.
- **Kein stiller Downgrade:** die restriktivste Einstufung gewinnt (bestehende Semantik
  `resolve_effective_classification` / `mostRestrictiveDataClass`).

## 2. UI-Modus → Backend-Klassifikation (Haupttabelle)

| UI-Option | Flacher FE-Wert (`DataClass`) | sensitivity | origin | processing_mode | web_research_mode | nda_applies | → BE-Klasse (`derive_data_class`) |
|---|---|---|---|---|---|---|---|
| Öffentlich | `public` | `public` | `synthetic` | `cloud_assisted` | `validated_public` | `false` | **D0_PUBLIC** |
| Intern | `internal` | `internal` | `real_project` | `deterministic_only` | `off` | `false` | **D1_INTERNAL** |
| Vertraulich | `confidential` | `confidential` | `real_project` | `local_only` | `off` | `false` | **D2_CONFIDENTIAL_IDEA** |
| **NDA / gesperrt (neu)** | `nda` | `confidential` | `real_project` | `deterministic_only` | `off` | **`true`** | **D3_NDA_BLOCKED** |
| *(keine Auswahl / unbekannter Wert)* | `""` — nicht wählbar | — | — | — | — | — | **UNKNOWN** (fail-closed, blockiert) |

Anmerkungen:
- Die Zeilen D0–D2 sind der **unveränderte Bestand** aus `FLAT_TO_CLASSIFICATION`;
  nur die D3-Zeile ist neu. `public → origin: synthetic` bleibt für MVP/Beta bestehen
  (Owner-Entscheid §7.3); die Trennung `public_synthetic`/`public_external` ist
  **Post-MVP**.
- `web_research_mode=off` bedeutet: **keine direkte/unrestriktive Webresearch** für
  dieses Projekt. Es bedeutet **nicht**, dass der separate sanitized Pfad (§5)
  ausgeschlossen ist — dieser ist policy-gesteuert (Matrix + Firewall + Approval),
  nicht über dieses Projektfeld.
- `derive_data_class` bleibt unverändert: `nda_applies=true` → D3 (gewinnt über alles);
  `public` + nicht-öffentlicher origin → UNKNOWN (fail-closed); unbekannte sensitivity →
  UNKNOWN.

## 3. Eigenschaften je Klasse: KI-Vorschläge und Webresearch

Autoritativ ist `policy_matrix.py` (fail-closed) plus `data_policy.evaluate`; die UI
zeigt diese Eigenschaften nur an und darf sie nie lockern.

**Wichtig (Owner-Klarstellung A):** D1 und D2 sind **nicht dauerhaft «KI verboten»**.
Ohne bestätigte ProviderPolicy bleiben sie fail-closed/deterministisch (Ist-Zustand).
Zielzustand: **kontrollierte KI ist für D1/D2 möglich, wenn die ProviderPolicy (R4.3)
dies erlaubt** (z. B. Azure/Enterprise-Pfad mit Vertragsbasis). Direkte Consumer-APIs
(OpenAI/Anthropic) bleiben für **echte** D1/D2-Daten blockiert. D2 braucht dabei
strengere Schutzmassnahmen als D1 (Enterprise Boundary, Auftragsverarbeitung,
explizite Freigabe).

| BE-Klasse | KI-Vorschläge (A2/Cloud-LLM) | Webresearch |
|---|---|---|
| D0_PUBLIC | möglich — nur nach expliziter Cloud-Bestätigung (M9D.2) und nur über einen laut ProviderPolicy (R4.3) erlaubten Provider | erlaubt (validated public) |
| D1_INTERNAL | **Ist:** fail-closed/deterministisch (keine bestätigte ProviderPolicy; `A2_DRAFTING` in der Matrix nicht gelistet → blocked). **Ziel:** kontrollierte KI über ProviderPolicy-erlaubten Pfad; direkte Consumer-APIs für echte D1-Daten bleiben blockiert | sanitized Pfad (§5): nur sanitisierte Query + menschliche Freigabe (Search Query Firewall) |
| D2_CONFIDENTIAL_IDEA | **Ist:** fail-closed/deterministisch. **Ziel:** kontrollierte KI **nur wenn ProviderPolicy (R4.3) es bestätigt**, mit strengeren Schutzmassnahmen als D1; direkte Consumer-APIs für echte D2-Daten bleiben blockiert | sanitized Pfad (§5): nur sanitisierte Query + menschliche Freigabe; Live-Provider zusätzlich hinter `D2_WEB_RESEARCH_ENABLED` (Default off) |
| D3_NDA_BLOCKED | blockiert — **auch der Fake-Provider** (GO-Auflage 2); zusätzlich kein Browser-Cache (§6) | blockiert |
| UNKNOWN | blockiert (fail-closed) | blockiert |

### 3.1 Notiz für R4.3: ProviderPolicy muss data_class × data_mode unterscheiden

Die ProviderPolicy (R4.3) muss später **data_class und data_mode** unterscheiden:

- **F1 synthetic** (= D2-Struktur als **synthetische Simulation**, origin
  `synthetic`/`anonymized`) **darf** für eine OpenAI/Anthropic-Evaluation erlaubt
  werden, wenn `AI_EVAL_MODE=real` gesetzt ist **und** eine Owner-Freigabe vorliegt.
- **Echte D2-Daten** (origin `real_project`) bleiben für `direct_openai`/
  `direct_anthropic` blockiert — unabhängig von gesetzten API-Keys.
- **D3/Unknown bleibt immer blockiert**, für jeden Provider und jeden data_mode.

## 4. Migrationszuordnung Bestandswerte (alt → neu)

### 4.1 Flache Werte (Intake-Session, UI, FE-Gates)

| Alter Wert | Bisherige Interpretation | Neue Interpretation | Begründung |
|---|---|---|---|
| `public` | public → D0 | `public` → D0 | unverändert |
| `internal` | internal → D1 | `internal` → D1 | unverändert |
| `confidential` | confidential → D2 | `confidential` → D2 | unverändert |
| `nda` (Legacy-Intake) | wurde auf `confidential` (D2) normalisiert | **`nda` → D3** | NDA-Marker darf nicht verloren gehen; restriktivste Einstufung gewinnt — die bisherige Normalisierung war ein stiller Marker-Verlust |
| `public_synthetic`, `public_external` (Legacy-Intake) | → `public` | → `public` (D0) | unverändert; Trennung der beiden Werte ist Post-MVP (§7.3) |
| leer / unbekannter Wert | → `""` (Auswahl erzwungen) | → `""` (Auswahl erzwungen); ohne Auswahl gilt UNKNOWN fail-closed | unverändert, jetzt explizit dokumentiert |

### 4.2 Bestandsprojekte in der Datenbank

- Projekte tragen die vollständige 5-Feld-`DataClassification` (Contract unverändert).
  **Keine DB-Migration nötig** — `derive_data_class` interpretiert Bestandsdaten
  unverändert (D0/D1/D2 wie bisher; `nda_applies=true` war schon immer D3).
- Einzige sichtbare Änderung: Projekte mit `nda_applies=true` werden im UI neu als
  «NDA / gesperrt» angezeigt (`flatFromDataClassification` liefert `nda` statt des
  bisherigen Kollapses auf `confidential`). Das ist eine **Verschärfung** der Anzeige,
  kein Downgrade.
- `effective_data_classification` bestehender Runs bleibt unangetastet (kein Re-Compute).

## 5. Webresearch: direkter vs. sanitized Pfad (Owner-Klarstellung B)

Zwei getrennte Pfade — kein Widerspruch zwischen `web_research_mode=off` und
«sanitized + Approval»:

1. **Direkte/unrestriktive Webresearch** wird durch das Projektfeld
   `web_research_mode` gesteuert: nur D0 (`validated_public`); D1/D2/D3 stehen auf
   `off` → keine direkte Webresearch.
2. **Sanitized Webresearch** ist ein **separater, policy-gesteuerter Pfad** über
   `policy_matrix` (`REQUIRE_SANITIZED_APPROVAL`) → Search Query Firewall →
   menschliche Freigabe. **Ist-Zustand im Code:** dieser Pfad existiert
   (`app/security/search_query_firewall.py`, Approval-Flow, `test_privacy_firewall.py`);
   ein **Live**-Provider-Call für D1/D2 ist zusätzlich hinter
   `D2_WEB_RESEARCH_ENABLED` (Default **off**) — ohne Flag wird der Fake-Provider
   verwendet (dev/test) oder der Task blockiert. D3/Unknown: immer blockiert, auch
   sanitized.

Der bestehende Run-/Analyse-Schalter «Web» (`AnalyseSettings.web`,
`components/run/analyse-einstellungen-dialog.tsx`) bleibt der einzige Schalter und ist
**restrict-only**:

- Er kann Webresearch **ausschalten**, auch wenn die Klasse sie erlauben würde.
- Er kann Webresearch **nie einschalten**, wenn die Klasse sie blockiert
  (`isWebAllowed` = UI-Gate; Backend-Matrix + Firewall entscheiden final).
- Es wird **kein neuer** Projekt-Schalter gebaut (R4.1-Scope; UI-Gates ersetzen nie die
  Backend-Policy).

## 6. Browser-Storage-Regeln (Owner-Klarstellung D, umgesetzt in R4.4)

- **D0/public:** darf den Komfort-Cache nutzen (Rich-Editor-Formatierung,
  Intake-Session) — bestehendes Verhalten.
- **D1/D2/D3/Unknown:** dürfen **keine Rohinhalte** in sessionStorage/localStorage
  speichern — keine Projektidee, keine Draft-Texte, kein Tiptap-JSON, keine
  Budgetwerte, keine Partnernamen.
- **Technische IDs sind erlaubt** (z. B. `rf_active_project_id`, `rf_current_run_id`)
  sowie nicht-sensitive Metadaten wie die Vertraulichkeitsstufe selbst.
- D3/Unknown: gar kein Cache (auch keine Formatierung).

## 7. Owner-Entscheide (freigegeben am 2026-07-08)

1. **D3 `processing_mode` = `deterministic_only`** — freigegeben. Kein KI-Pfad
   irgendeiner Art für NDA-Material (strikter als D2s `local_only`).
2. **Flacher FE-Wert = `"nda"`** — freigegeben. Deckungsgleich mit dem
   Legacy-Intake-Wert; wird von den bestehenden Restricted-Markern
   (`isRichCacheAllowed`-Regex: `d3|nda|restricted|gesperrt|…`) bereits als gesperrt
   erkannt.
3. **`public → origin: synthetic` bleibt für MVP/Beta bestehen** — freigegeben, mit
   Hinweis: die spätere Trennung `public_synthetic`/`public_external` ist **Post-MVP**.
4. **UI-Microcopy der neuen Option** — freigegeben:
   - Titel: **«NDA / gesperrt»**
   - Beschreibung: **«Für NDA-geschützte oder rechtlich gesperrte Inhalte. Keine
     KI-Verarbeitung, keine Webrecherche, keine Browser-Zwischenspeicherung.»**
   - KI: **«nicht möglich»** · Webresearch: **«nicht möglich»**

---

*Nach Commit-Freigabe: Doku-Commit `docs(r4): data-class mapping v2 (owner-approved)`,
dann R4.1b (Codeänderungen gemäss Plan).*
