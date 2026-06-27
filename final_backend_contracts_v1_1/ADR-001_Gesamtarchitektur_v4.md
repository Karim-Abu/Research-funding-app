# ADR-001: Gesamtarchitektur der evidenzbasierten Proposal-Unterstützung

- **Version:** v4
- **Datum:** 21.06.2026
- **Status:** accepted for Evaluation-Beta implementation
- **Entscheidungsverantwortung:** Karim
- **Externe Bestätigungen weiterhin offen:** institutionelle Providerfreigabe, Retention/Löschung und produktives Hosting
- **Gültigkeitsbereich:** Evaluation-Beta für Innosuisse «Create Innovation Project» mit Umsetzungspartner; Zielbild für einen späteren institutionellen Pilot

## Kontext (Context)

Die Anwendung soll Forschungs- und Umsetzungspartner bei der strukturierten Vorbereitung eines Innosuisse-Innovationsprojekts unterstützen. Der Antragsprozess verbindet heterogene Dokumente, strukturierte Partner- und Finanzdaten, fachliche Argumentation, Portalvorgaben, Evidenz, Qualitätsprüfung und menschliche Freigaben. Eine reine Textgenerierung reicht nicht aus.

Die Lösung soll:

- PDF-, DOCX-, TXT- und kontrolliert importierte Webquellen normalisieren,
- Projektfakten, Widersprüche, Lücken und Belegkandidaten extrahieren,
- offizielle und kuratierte Innosuisse-Anforderungen versioniert prüfen,
- alle im UI-Snapshot bekannten Portalobjekte katalogisieren,
- strukturierte Projekt-, Partner-, Zeitplan-, Arbeitspaket-, Meilenstein-, Stunden-, Budget- und Risikodaten verwalten,
- evidenzbasierte, editierbare Entwürfe für tatsächlich beschreibbare Portalfelder erzeugen,
- Lösung, Innovation, Abgrenzung, WHY-NOW, Nutzen, Marktlogik und Umsetzung argumentativ unterstützen,
- typische Proposal-Risiken, unbelegte Claims, Widersprüche und fehlende Quantifizierung markieren,
- explizit ausgelöste öffentliche Kompetenz-, Publikations- und Track-Record-Recherche unterstützen,
- Fortschritt, offene Punkte, Reviewstatus und Kosten transparent zeigen,
- Human-in-the-loop wirksam, aber ausnahmebasiert und reibungsarm umsetzen,
- Audit-, Versions-, Policy-, Regel-, Agenten-, Tool- und Kostenhistorien nachvollziehbar speichern,
- DOCX-, Markdown- und technische Evidenzartefakte erzeugen,
- keine automatische Einreichung ins Innolink-Portal und keine Bewilligungsprognose durchführen.

Die Anwendung ist kein autonomer Proposal-Generator. LLM-Ausgaben sind Vorschläge, Entwürfe oder beratende Findings. Harte Regeln, finale Freigaben, Datenklassifikation, Budgetausnahmen, Partnerrealität, Innovationshöhe und Förderplausibilität bleiben deterministisch beziehungsweise menschlich kontrolliert.

### Bestehende Rahmenbedingungen

- Next.js/TypeScript/Tailwind/shadcn-Frontend ist vorhanden.
- Python/FastAPI, LangGraph, Pydantic, Validatoren und python-docx bilden die Backendbasis.
- Die Evaluation-Beta wird durch eine Person mit KI-gestützter Entwicklungsunterstützung umgesetzt.
- OpenAI, Anthropic und Firecrawl stehen als externe Dienste zur Verfügung.
- Für die Evaluation werden öffentliche oder vollständig synthetische Daten verwendet.
- Interne und vertrauliche Daten benötigen explizite Data-Policy-, Provider- und Loggingkontrollen.
- Azure ist ein mögliches Pilot-/Produktionsziel, nicht Voraussetzung für die Evaluation.
- Der Portalstand ist ein versionierter, UI-verifizierter Snapshot. Nicht erfasste dynamische Portalzustände werden nicht erfunden.

### Scope der Evaluation-Beta

Aktiv beziehungsweise vertraglich vorbereitet:

- ein Funding-Instrument-Profil für «Create Innovation Project»,
- alle 161 im UI-Snapshot bekannten Portalobjekte als Katalog,
- strukturierte Kernobjekte für Partner, Projekttermine, Arbeitspakete, Meilensteine, Stunden, Budget und Risiken,
- drei LLM-Agententypen mit mehreren Profilen,
- deterministische Regeln und Quality Gates,
- EvidenceCandidate/EvidenceAnchor/EvidenceLink,
- zentrale Control-&-Guardrail-Schicht,
- explizite, kontrollierte öffentliche Recherche,
- ein persistentes Hauptreview mit Recheck vor Freigabe,
- Export, Audit, Usage und Kostenkontrolle,
- vorprovisionierte Nutzerkonten und einfache asynchrone Zusammenarbeit.

Nicht zugesagt beziehungsweise Post-Beta:

- automatische Innolink-Einreichung,
- Echtzeit-Collaboration,
- externe Gastrollen,
- produktive Multi-Workspace-Segregation,
- freie autonome Webnavigation,
- automatische Partnerauswahl oder Kontaktaufnahme,
- Fine-Tuning oder automatische Trainingsdatenpipeline,
- vollständige Garantie für nicht erfasste Portalzustände,
- Bewilligungswahrscheinlichkeit.

## Entscheidungstreiber (Drivers)

| Treiber                          | Einfluss                                                                                                                              |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Specification-first**          | Agenten, Tools, Regeln, Controls, Zustände und API müssen vor Implementierung als prüfbare Verträge feststehen.                       |
| **Nutzermehrwert**               | Der grösste Nutzen ist ein vollständiger, evidenzbasierter und editierbarer Erstentwurf mit klaren offenen Punkten.                   |
| **Benutzerfreundlichkeit**       | Komplexität bleibt im Backend; die UI zeigt Aufgaben, Status und nächste Schritte statt Agenten- oder Modelltechnik.                  |
| **Portalorientierung**           | Strukturierte und narrative Antragsbestandteile werden explizit an Portalobjekte gebunden.                                            |
| **Evidence-first**               | Claims müssen auf versionierte Fundstellen zurückführbar oder sichtbar offen sein.                                                    |
| **Deterministische Korrektheit** | Zeichenlimits, Pflichtfelder, Zahlen, Budget, Partnerkonstellationen und Freigabegates dürfen nicht vom LLM entschieden werden.       |
| **HITL mit geringer Reibung**    | Menschen bearbeiten Ausnahmen, Blocker und kritische Findings; Routineprüfungen laufen automatisch.                                   |
| **Security & Guardrails**        | Quellen sind untrusted data; Tool-, Daten-, Kosten-, Schema- und Prompt-Injection-Kontrollen sind querschnittlich.                    |
| **Datenschutz**                  | Effektive Sensitivität ist die restriktivste Klassifikation aller Inputs; externe Verarbeitung ist environment- und providerabhängig. |
| **Auditierbarkeit**              | Run-Snapshot, Profile, Modelle, Regeln, Controls, Tools, Edits, Freigaben und Exporte müssen rekonstruierbar sein.                    |
| **Kosten und Latenz**            | Calls werden gebündelt, begrenzt, gecacht und nur bei fachlichem Mehrwert ausgeführt.                                                 |
| **Geringe Betriebskomplexität**  | Ein modularer Monolith ist für Einzelentwicklung und 10–15 Nutzer:innen angemessen.                                                   |
| **Provider-Flexibilität**        | Modellrouten bleiben austauschbar und werden per Rollenbenchmark bestätigt.                                                           |
| **Weiterentwicklung**            | PostgreSQL, Entra ID, Azure, Worker und granularere Zusammenarbeit sollen ohne Neuentwurf der Fachlogik möglich sein.                 |

## Optionen (Options)

### Option 1: Streamlit-Monolith

Schnell lokal nutzbar, aber unzureichend für die gewünschte UX, API-Trennung, Persistenz und Zusammenarbeit.

### Option 2: Next.js + FastAPI mit eigener persistierter Zustandsmaschine

Technisch möglich und frameworkarm. Checkpointing, Interrupt/Resume, Wiederaufnahme und Trajektorien müssten jedoch vollständig selbst gebaut und getestet werden.

### Option 3: Modularer Monolith mit Next.js, FastAPI, LangGraph und deterministischen Fachmodulen

Ein Backend-Deployment mit klaren Paketgrenzen; LangGraph orchestriert den Run, während Regeln, Evidence, Controls, Agenten, Review und Export interne Module bleiben.

### Option 4: Microservices oder Container pro Agent

Unverhältnismässiger State-, Netzwerk-, Security- und Betriebsaufwand für die Projektgrösse.

### Option 5: Managed-Agent-Plattform als Primärarchitektur

Für einen späteren Pilot relevant, aber abhängig von institutioneller Subscription, Governance, Regionen und Plattformreife.

### Option 6: Generative App-Plattform als Hauptarchitektur

Schneller Prototyp, aber zweite technische Welt, Lock-in und geringere Datenfluss- und Thesis-Nachvollziehbarkeit.

## Entscheidung (Decision)

Gewählt wird **Option 3: ein modularer Monolith aus Next.js, FastAPI und LangGraph mit drei LLM-Agententypen, strukturiertem Antragsmodell, deterministischen Fachmodulen und einer expliziten Control-&-Guardrail-Schicht.**

### 1. Frontend

- Next.js, TypeScript, Tailwind CSS und shadcn/ui.
- Dünne Interaktions-, Status-, Editier- und Review-Schicht.
- Keine Secrets, fachlichen Regeln oder Providerentscheidungen im Browser.
- Alle Datenzugriffe über `/api/v1`.
- Progressive Disclosure: technische Details nur in Admin-/Detailansichten.

### 2. Backend und Paketgrenzen

Ein FastAPI-Service mit internen Modulen:

- Identity & Access,
- Projects & Structured Application Data,
- Sources & Normalization,
- Public Research,
- Runs & LangGraph Orchestration,
- Data Policy & Security,
- Control & Guardrails,
- Requirements & Rules,
- Evidence,
- Agents & Profiles,
- Review & Approval,
- Export,
- Usage & Audit.

Die Module kommunizieren über definierte Python-Schnittstellen, nicht über interne Netzwerkservices.

### 3. Strukturierter Antrag

Narrative Drafts und strukturierte Daten werden getrennt modelliert.

Strukturierte Kernobjekte:

- Partner und Vertreter,
- ProjectDates,
- WorkPackage und PartnerAllocation,
- Milestone und MilestoneGoal,
- PlannedHours,
- BudgetPlan, SalaryContribution, MaterialCost und CashContribution,
- RiskRegister und RiskEntry,
- PortalFieldValue für übrige strukturierte Felder.

LLMs dürfen strukturierte Identitäts-, Rechts-, Datums-, Stunden- oder Betragswerte nicht stillschweigend verändern. Sie dürfen fehlende Angaben markieren und narrative Erläuterungen vorschlagen.

### 4. LangGraph-Orchestrierung

LangGraph verwaltet:

- versionierten Run-Snapshot,
- deterministischen und agentischen Pfad,
- persistente Checkpoints,
- Review-Interrupt,
- gezielten Recheck nach Edits,
- Resume zur Finalisierung,
- Fehler-, Stop- und Fallbackzustände.

Der Reviewablauf lautet verbindlich:

```text
Human Edit / Decision
→ targeted recheck
→ aktualisiertes ReviewPackage
→ ReviewApproval
→ Resume/Finalize
```

Eine Freigabe vor abgeschlossenem Recheck ist unzulässig.

### 5. LLM-Agententypen

#### A1 – Project Input & Evidence Extraction

- extrahiert facts, Konflikte und fehlende Angaben,
- schlägt EvidenceCandidates vor,
- strukturiert explizit importierte öffentliche Kompetenz-/Publikationsresultate,
- definiert keine offiziellen Regeln und verifiziert keine eigene Evidence.

#### A2 – Field Drafting

- erzeugt nur für explizit `agent_writable=true` markierte Felder Entwurfskandidaten,
- nutzt bestätigte Fakten, verifizierte Evidence, strukturierte Projektdaten, Feldprofile, Requirements und offene Issues,
- besitzt fünf fachlich unterschiedliche Rubriken,
- verändert keine Zahlen, Identitäten, Rechtsbestätigungen oder Auswahlfelder.

#### A3 – Critic / Verifier

- erzeugt ausschliesslich beratende ReviewFindings,
- prüft Evidence/Consistency, Fit-Gap/Partnerrollen, Risk/Readiness und Innovation Challenge,
- überschreibt keine Regeln, Freigaben oder Fakten,
- optionaler Final Quality Review ist manuell, public/synthetic only und nie approval-setzend.

### 6. Agentenautorität

- A1: `proposal_requires_validation`
- A2: `draft_requires_human_review`
- A3: `advisory_finding`
- deterministische Regeln/Controls: `authoritative_within_rule_scope`
- Mensch: finale fachliche Entscheidung und Freigabe

### 7. Control-&-Guardrail-Schicht

Kanonische, versionierte Controls prüfen:

- Data Policy,
- Input-/Output-Schema,
- Source Trust und Prompt Injection,
- Tool Authorization,
- Kosten/Calls/Retry,
- Run-Snapshot und Version Locks,
- Datei-/Pfad-/URL-/SSRF-Sicherheit,
- Kontextminimierung,
- Evidence- und Approval-Gates,
- Exportklassifikation,
- Auditpersistenz.

Alle relevanten Aktionen erzeugen `ControlResult`. Unbekannte Control-IDs oder Schemas stoppen den Backend-Start.

### 8. Requirements, Regeln und Portalobjekte

- `requirements.yaml` ist der kanonische RequirementDefinition-Katalog.
- `innosuisse_innovation_project_v1_1.yaml` enthält Rules, Quality Gates, Cross-Field Rules und den Portalobjektkatalog.
- Unverifizierte Pflichten werden nicht als aktive Blocker ausgeführt.
- Jedes Portalobjekt trägt `field_kind`, `support_mode`, `agent_writable` und gegebenenfalls `structured_data_path`.
- A2 nutzt explizite Field-ID-Allowlists, keine pauschalen Präfixe.

### 9. Evidence

- Retrieval erzeugt Kandidaten.
- Nur `exact_normalized` kann automatisch `exact_verified` werden.
- Fuzzy/semantic benötigt HumanDecision für `human_verified`.
- EvidenceLinks sind target-spezifisch und können `active`, `stale` oder `removed` sein.
- Evidence-Status und menschliche Bestätigung bleiben getrennt.

### 10. Öffentliche Recherche

- nur explizit durch Projektleitung/Admin ausgelöst,
- Such-/Fetch-Schritte orchestrator-controlled,
- HTTPS, Public-DNS, SSRF, Redirect, Zweck- und Datenschutzprüfung,
- Resultate bleiben Kandidaten bis zum Import als SourceVersion,
- A1 verarbeitet nur lokal importierte Resultate,
- keine sensiblen Merkmale, privaten Profile, automatische Partnerauswahl oder Kontaktaufnahme.

### 11. Data Policy

Drei sichtbare Sensitivitäten:

- `public`
- `internal`
- `confidential`

Zusätzlich:

- Origin,
- Processing Mode,
- Web Research Mode `off | validated_public`,
- NDA-Flag,
- Policy Environment.

`internal + cloud_assisted` ist nur erlaubt, wenn die konkrete Route institutionell freigegeben, der Payload minimiert und der Run bestätigt ist. In der aktiven Evaluation-Beta sind direkte Provider für reale interne Projektinhalte operational blockiert, solange diese Freigabe fehlt.

### 12. API

- Fachliche Ressourcen, nie Agent- oder Toolendpunkte.
- HTTP-only Session und CSRF.
- Polling für asynchrone Jobs.
- Idempotency-Key für Run, Research, Recheck, Redraft und Export.
- Optimistische Versionskontrolle.
- typisierte HumanDecision-Requests.
- strukturierte Projektsetup-, Budget- und Risikoresourcen.
- ReviewPackage enthält OpenIssues, EvidenceLinks, Recheckstatus und Scope-Hash.

### 13. Persistenz und Deployment

Evaluation-Beta:

- SQLite,
- lokaler Source-/Export-Storage,
- Docker-basierte interne Ausführung,
- öffentliche/synthetische Evaluationsdaten.

Institutioneller Pilot:

- PostgreSQL,
- Object Storage,
- Entra ID,
- optional separater Worker,
- Azure/Foundry nur nach institutioneller Prüfung.

### 14. Referenzanträge

Bewilligter, abgelehnter und Trainingssample-Antrag sind **kein Trainingsdatensatz**. Zulässig sind nach Freigabe:

- lokale Goldstandard- und Regressionsevaluation,
- Struktur-, Evidence-, Rule- und Critic-Kalibrierung,
- anonymisierte Fehleranalyse.

Nicht zulässig ohne separates Governance-ADR:

- automatische Cloud-Retrieval-Nutzung,
- Few-Shot-Prompting,
- Fine-Tuning,
- Ableitung einer Bewilligungswahrscheinlichkeit.

## Konsequenzen (Consequences)

### Positive Konsequenzen

- klare Agent-/Regel-/Tool-/Human-Verantwortung,
- vollständigeres Antragsmodell statt reiner Textgenerator,
- nachvollziehbare Evidence und Review-Reife,
- sichere, explizite Webrecherche,
- geringer Backend-Betriebsaufwand,
- testbare und versionierte Verträge,
- provider- und deploymentfähige Weiterentwicklung,
- UI kann trotz interner Komplexität einfach bleiben.

### Negative Konsequenzen

- mehr Domain-, Schema- und API-Arbeit vor Agentenlogik,
- Source Normalization und Evidence Matching benötigen Goldset-Tests,
- volle Portalstruktur erhöht Implementierungsumfang,
- öffentliche Personenrecherche braucht zusätzliche Privacy- und Identity-Matching-Tests,
- SQLite und gemeinsame Workspace-Sicht bleiben Beta-Limitationen,
- institutionelle Cloud- und Retentionentscheide bleiben extern offen,
- LLM-Qualität bleibt probabilistisch und erfordert Benchmark sowie HITL.

### Erforderliche Folgemassnahmen

1. Domain Model v4 und alle v1.1-Registries als kanonisch bestätigen.
2. Pydantic-Verträge und Startup-Validator implementieren.
3. OpenAPI v1.1 linten und Clienttypen erzeugen.
4. Deterministischen E2E-Pfad vor LLM-Agenten implementieren.
5. Rollenbenchmark und Goldset-Evaluation durchführen.
6. Institutionelle Data-Policy-, Provider- und Retentionfragen separat klären.

## Status

**accepted for Evaluation-Beta implementation**

Diese Entscheidung gilt für die Backend-Implementierung. Institutionelle Cloud-, Retention- und Pilotentscheidungen bleiben ausdrücklich offen und verändern nicht den lokalen/public-synthetic Evaluationspfad.
