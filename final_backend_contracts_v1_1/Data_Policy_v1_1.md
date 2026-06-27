# Data Policy v1.1

## Evidenzbasierte Proposal-Unterstützung für Innosuisse-Innovationsprojekte

- **Version:** 1.1.0
- **Datum:** 21.06.2026
- **Status:** approved for Evaluation-Beta
- **Maschinenlesbare Fassung:** `data_policy_v1_1.yaml`
- **Aktives Environment:** `evaluation_beta`
- **Institutioneller Pilot:** modelliert, aber inaktiv

## 1. Zweck

Die Policy entscheidet vor jedem Modell-, Tool-, URL-, Research-, Export- und Loggingvorgang, ob die Verarbeitung erlaubt, bestätigungspflichtig oder blockiert ist. Eine Nutzerbestätigung allein kann keine institutionell nicht freigegebene Providerroute aktivieren.

## 2. Klassifikationsdimensionen

- Sensitivität: `public | internal | confidential`
- Herkunft: `public_source | synthetic | anonymized | real_project`
- Processing Mode: `deterministic_only | cloud_assisted | local_only`
- Web Research Mode: `off | validated_public`
- NDA-Flag
- Policy Environment

`synthetic` und `anonymized` sind Herkunftswerte, keine Sensitivitätsstufen.

## 3. Grundsätze

1. Deny by default.
2. Restriktivste Klassifikation gewinnt.
3. Fehlende Klassifikation wird `confidential`.
4. Keine automatische Herabstufung oder Anonymisierung.
5. Externer Payload wird minimiert.
6. Quellen sind untrusted data.
7. Keine automatische Trainings-/Fine-Tuning-Nutzung.
8. Jede Entscheidung erzeugt `ControlResult`.
9. Ein Run friert die Policy-Version ein.
10. Providerfreigabe wird nur serverseitig ausgewertet.

## 4. Evaluation-Beta

| Sensitivität | Lokal/deterministisch | Cloud-KI | Validated Public Research |
|---|---:|---:|---:|
| Public | erlaubt | erlaubt | explizit erlaubt |
| Internal | erlaubt | `allowed_with_confirmation`, aber nur bei institutionell genehmigter Route | nur öffentliche, sanitised und bestätigte Query/URL |
| Confidential | erlaubt | blockiert | blockiert |
| NDA | lokal erlaubt | blockiert, sofern keine separate Vertragsfreigabe | blockiert |

### Origin Override

Für `origin=real_project` gilt im aktiven Evaluation-Environment:

- Cloud-Verarbeitung bleibt blockiert, solange keine institutionelle Providerroute freigegeben und der Environment-Override aktiviert ist.
- Die direkte OpenAI-/Anthropic-Route ist aktuell nur für öffentliche beziehungsweise synthetische Evaluationsdaten aktiv.

Damit sind die generische `internal=allowed_with_confirmation`-Regel und die operative Evaluationseinschränkung widerspruchsfrei.

## 5. Institutioneller Pilot

`institutional_pilot` bleibt `proposed_inactive`. Aktivierung verlangt mindestens:

- institutionelle Datenschutz-/Rechtsfreigabe,
- genehmigte Providerroute,
- Retention-/Residency-Entscheid,
- Identitäts-/Zugriffskontrolle,
- Logging-/Löschkonzept,
- Security- und Incident-Prozess.

Erst dann kann `internal + real_project + cloud_assisted` wirksam `allowed_with_confirmation` sein.

## 6. Provider

### OpenAI direct

- aktiv für public/synthetic Beta-Daten,
- internal nur bei freigegebener Route und allen Preconditions,
- confidential/NDA blockiert,
- Retention/Region müssen pro Deployment dokumentiert werden.

### Anthropic direct

- gleiches Grundrouting,
- modell-/featureabhängige Retention beachten,
- Fable 5 nur als optionale public/synthetic Reviewroute; direkte API verlangt 30-Tage-Retention und Runtime-Verfügbarkeit muss geprüft werden.

### Firecrawl

- nur orchestrator-controlled public search/fetch,
- keine privaten/authentifizierten Systeme,
- keine Tokens/Credentials in URLs,
- keine confidential/NDA Queries,
- Ergebnisse sind Kandidaten und werden erst nach Import als SourceVersion genutzt.

### Azure Foundry

- geplant, inaktiv,
- Aktivierung erst nach institutioneller, regionaler und modellbezogener Prüfung.

## 7. Öffentliche Kompetenz-/Publikationsrecherche

Zulässig:

- institutionelle Profile,
- öffentliche Forschungsgebiete und Rollen,
- Publikationsmetadaten,
- öffentlich beschriebene Projekte,
- professionelle Kompetenzen und Track Record.

Nicht zulässig:

- sensible Merkmale,
- nicht berufsbezogenes Profiling,
- private Kontaktdaten ohne Zweck,
- Login-Bereiche,
- automatische Partnerauswahl,
- automatische Kontaktaufnahme.

Die Recherche wird nur durch `lead_admin` explizit gestartet. Der Orchestrator kontrolliert Suche und Fetch. A1 verarbeitet nur lokal importierte Ergebnisse.

## 8. Validated Public URL Controls

Jede URL und jeder Redirect muss:

- HTTPS verwenden,
- ohne eingebettete Credentials/Tokens sein,
- auf öffentliche DNS-/IP-Ziele auflösen,
- Loopback, private, link-local und Metadata-Ziele vermeiden,
- dem erklärten professionellen/Projektzweck entsprechen,
- geeigneten Inhaltstyp und technische Grösse besitzen,
- nach Redirect erneut validiert werden.

„Alle öffentlichen Quellen“ bedeutet somit keine statische Domainliste, aber auch keinen beliebigen Netzwerkzugriff.

## 9. Logging

- keine Secrets oder API-Keys,
- Public: lokale Inhaltsprotokollierung nur wenn nötig,
- Internal: minimierte Inhalte; geteilte Logs nur Metadaten/Hashes,
- Confidential: keine Fulltext-Prompts/-Responses,
- jeder externe Call speichert Route, Modell, Policy-Version, Klassifikation, Hashes, Nutzung, Kosten und ControlResult.

## 10. Retention und Löschung

Es existieren keine bestätigten FHNW-Fristen. Deshalb werden keine Fristen erfunden.

Status:

```text
needs_institutional_decision
```

Bis dahin:

- Evaluationsdaten bleiben lokal und projektbezogen löschbar,
- Source-/Exportartefakte benötigen nachvollziehbare Referenzen,
- Auditdaten sind nicht automatisch Trainingsdaten,
- produktive Purge-Semantik ist Post-Beta und wird erst nach Retentionentscheid verbindlich.

## 11. Reklassifizierung

- nur `lead_admin`,
- explizite HumanDecision/Kommentar/Audit,
- keine automatische Herabstufung,
- `anonymized` bedeutet nicht automatisch `public`,
- Reklassifizierung darf Providerfreigabe nicht umgehen.

## 12. Policy-Ergebnis

```text
allowed
allowed_with_confirmation
blocked
```

Jedes Ergebnis enthält:

- effektive Klassifikation,
- Environment,
- Providerroute,
- Reason Code,
- benötigte Bestätigung,
- angewandte Policy-Version,
- ControlResult-ID.
