// Statischer Funktionskatalog für die Transparenzseite
// "Rollen & Verantwortung". Die zehn sichtbaren Rollen sind verständliche
// Funktionsansichten über drei KI-Rollen, deterministische Systemdienste und
// menschliche Freigaben – keine zehn autonomen Agenten.
import { WORKFLOW_STEPS, type WorkflowStepDef } from "./workflow"

export type RoleMode = "ki" | "regelbasiert" | "hybrid"
export type RoleCategory = "specialist" | "system"
export type RoleAvailability = "available" | "development" | "planned"
export type RoleIconKey =
  | "workflow"
  | "shieldCheck"
  | "search"
  | "fileSearch"
  | "link2"
  | "penLine"
  | "calculator"
  | "listChecks"
  | "clipboardCheck"
  | "fileOutput"

export type RoleModelInfo =
  | {
      kind: "none"
      description: string
    }
  | {
      kind: "model-route"
      primary: {
        provider: string
        model: string
      }
      fallback?: {
        provider: string
        model: string
      }
      scope?: string
    }

export const MODEL_ROUTE_NOTICE =
  "Welches Modell tatsächlich eingesetzt wurde, kann durch Verfügbarkeit und Ersatzrouten variieren und wird beim jeweiligen Lauf protokolliert."

export const MODE_LABELS: Record<RoleMode, string> = {
  ki: "KI-gestützt",
  regelbasiert: "Feste Regeln",
  hybrid: "KI + Regeln",
}

export const AVAILABILITY_LABELS: Record<RoleAvailability, string> = {
  available: "Verfügbar",
  development: "In Entwicklung",
  planned: "Geplant",
}

export interface KiTeamRole {
  id: string
  name: string
  category: RoleCategory
  mode: RoleMode
  iconKey: RoleIconKey
  specialization: string
  task: string
  worksWith: string
  outputSummary: string
  humanReview: string
  decisionBoundary: string
  dataAccess: string
  activeSteps: number[]
  availability: RoleAvailability
  /** Interne Zuordnung – nur im geschlossenen Bereich "Technische Details". */
  technicalComponents: string[]
  modelInfo: RoleModelInfo
  providerSummary: string
  technicalSource: string
  dataClassRule: string
}

export const kiTeamRoles: KiTeamRole[] = [
  {
    id: "workflow-koordinator",
    name: "Workflow-Koordinator",
    category: "system",
    mode: "regelbasiert",
    iconKey: "workflow",
    specialization:
      "Steuert Reihenfolge, Übergaben und Kontrollpunkte nach einem fest definierten Ablauf.",
    task:
      "Hält die Analyse- und Bearbeitungsschritte in der vorgesehenen Reihenfolge und übergibt Ergebnisse an den nächsten Kontrollpunkt.",
    worksWith:
      "Bearbeitungsstand, Freigaben und Ergebnissen der einzelnen Schritte.",
    outputSummary: "Klaren Prozessstatus und geordnete Übergaben.",
    humanReview:
      "Sie entscheiden an den vorgesehenen Kontrollpunkten, ob Inhalte bestätigt oder weiterbearbeitet werden.",
    decisionBoundary:
      "Trifft keine fachlichen, finanziellen oder inhaltlichen Entscheidungen.",
    dataAccess:
      "Sieht den Bearbeitungsstand und technische Übergaben, nicht automatisch alle Dokumentinhalte.",
    activeSteps: [1],
    availability: "available",
    technicalComponents: ["runs.graph", "runs.executor", "runs.phases"],
    modelInfo: {
      kind: "none",
      description:
        "Kein KI-Modell. Die Funktion folgt einer fest definierten Ablaufsteuerung.",
    },
    providerSummary: "Kein KI-Modell – deterministische Ablaufsteuerung.",
    technicalSource:
      "backend/app/runs/graph.py, backend/app/runs/executor.py, backend/app/runs/phases.py",
    dataClassRule:
      "Verarbeitet vor allem Zustands- und Übergabedaten innerhalb des Projektkontexts.",
  },
  {
    id: "suchanfragen-schutz",
    name: "Suchanfragen-Schutz",
    category: "system",
    mode: "regelbasiert",
    iconKey: "shieldCheck",
    specialization:
      "Prüft und abstrahiert Websuchanfragen, bevor externe Recherche startet.",
    task:
      "Plant Suchanfragen aus dem freigegebenen Recherchebrief, entfernt erkennbare sensible Angaben und verlangt vor realer Webrecherche eine ausdrückliche Freigabe.",
    worksWith:
      "Recherchebrief, Datenklasse und vorgeschlagenen Suchanfragen.",
    outputSummary: "Bereinigte, freigabefähige Suchanfragen.",
    humanReview:
      "Sie prüfen den sichtbaren Suchtext sorgfältig und genehmigen jede nach aussen gesendete Anfrage.",
    decisionBoundary:
      "Kann nicht garantieren, dass jede vertrauliche Bezeichnung erkannt wird; ohne Freigabe startet keine reale Websuche.",
    dataAccess:
      "Verarbeitet den Recherchebrief und den Text der geplanten Anfrage; vertrauliche Rohabfragen werden nicht gespeichert oder gesendet.",
    activeSteps: [1],
    availability: "available",
    technicalComponents: [
      "research.brief_service",
      "Search Query Firewall",
      "Search Query Approval Service",
    ],
    modelInfo: {
      kind: "none",
      description:
        "Kein KI-Modell. Schutzprüfung und Freigabelogik laufen regelbasiert.",
    },
    providerSummary: "Kein KI-Modell – lokale, deterministische Schutzprüfungen.",
    technicalSource:
      "backend/app/research/brief_service.py, backend/app/security/search_query_firewall.py, backend/app/security/approval_service.py",
    dataClassRule:
      "D1/D2-Anfragen benötigen eine sichtbare menschliche Freigabe; D3 und unbekannte Datenklassen werden blockiert.",
  },
  {
    id: "marktrecherche-assistent",
    name: "Marktrecherche-Assistent",
    category: "specialist",
    mode: "hybrid",
    iconKey: "search",
    specialization:
      "Bereitet freigegebene Suchanfragen vor und ordnet öffentliche Markt- und Wettbewerbsquellen.",
    task:
      "Plant allgemeine Recherchefragen, führt nur freigegebene Suchanfragen aus und strukturiert übernommene öffentliche Quellen zu prüfbaren Hinweisen.",
    worksWith:
      "Freigegebenen, abstrahierten Suchanfragen und öffentlichen, übernommenen Quellen.",
    outputSummary: "Öffentliche Quellen mit nachvollziehbaren Fundstellen.",
    humanReview:
      "Sie genehmigen Suchanfragen und prüfen jede Quelle sowie jede daraus abgeleitete Markt- oder Wettbewerbsaussage.",
    decisionBoundary:
      "Recherchetreffer bleiben Hinweise; die Funktion bestätigt keine Marktchancen, Partnereignung oder Förderwahrscheinlichkeit.",
    dataAccess:
      "Erhält nur freigegebenen Recherchekontext und öffentliche Quellen, nie die Rohidee.",
    activeSteps: [1],
    availability: "development",
    technicalComponents: [
      "RESEARCH_QUERY_PLANNER",
      "ResearchExecutor",
      "RESEARCH_EVIDENCE_SYNTHESIZER",
      "MC.market_comparison",
    ],
    modelInfo: {
      kind: "model-route",
      primary: {
        provider: "Anthropic",
        model: "Claude Sonnet 5",
      },
      fallback: {
        provider: "Anthropic",
        model: "Claude Haiku 4.5",
      },
      scope:
        "Nur die Strukturierung übernommener öffentlicher Quellen ist KI-gestützt. Planung, Schutzprüfung und Rechercheausführung bleiben regelbasiert.",
    },
    providerSummary:
      "Deterministische Planung und Schutzprüfung; KI-gestützte Strukturierung bereits übernommener öffentlicher Quellen.",
    technicalSource:
      "backend/app/market_research/planner.py, backend/app/research/brief_service.py, backend/app/market/executor.py",
    dataClassRule:
      "Externe Recherche nutzt nur freigegebene, abstrahierte Anfragen; die Quellenstrukturierung ist auf öffentlichen Kontext begrenzt.",
  },
  {
    id: "anforderungsanalyst",
    name: "Anforderungsanalyst",
    category: "specialist",
    mode: "ki",
    iconKey: "fileSearch",
    specialization:
      "Ordnet Projektfakten, fehlende Angaben und Widersprüche den bereits hinterlegten Anforderungen zu.",
    task:
      "Liest ausgewählte Projektquellen und schlägt strukturierte Fakten, Konflikte und offene Angaben für die registrierten Anforderungen vor.",
    worksWith:
      "Projektangaben, ausgewählten Quellenausschnitten und den hinterlegten Anforderungsdefinitionen.",
    outputSummary:
      "Strukturierte Projektfakten und offene Punkte zu den hinterlegten Anforderungen.",
    humanReview:
      "Sie bestätigen kritische Fakten und klären widersprüchliche oder fehlende Angaben.",
    decisionBoundary:
      "Definiert keine offiziellen Anforderungen und entscheidet nicht über die Förderfähigkeit.",
    dataAccess:
      "Sieht nur die für die Analyse ausgewählten Projektangaben und Quellenausschnitte innerhalb der erlaubten Datenklasse.",
    activeSteps: [3],
    availability: "available",
    technicalComponents: ["A1.project_fact_extraction"],
    modelInfo: {
      kind: "model-route",
      primary: {
        provider: "OpenAI",
        model: "GPT-5.6 Luna",
      },
      fallback: {
        provider: "Anthropic",
        model: "Claude Haiku 4.5",
      },
      scope:
        "Für Faktenerkennung und die strukturierte Zuordnung zu hinterlegten Anforderungen.",
    },
    providerSummary:
      "A1 – KI-gestützte Faktenerkennung; alle Ergebnisse bleiben unbestätigte Vorschläge.",
    technicalSource: "backend/app/agents/fact_extraction.py",
    dataClassRule:
      "Externe Verarbeitung ist nur in erlaubten Modi und mit minimiertem Kontext zulässig; vertrauliche oder NDA-Inhalte werden blockiert.",
  },
  {
    id: "evidenzpruefer",
    name: "Evidenzprüfer",
    category: "specialist",
    mode: "hybrid",
    iconKey: "link2",
    specialization:
      "Verknüpft Aussagen mit konkreten Fundstellen und kennzeichnet nicht bestätigte Belege.",
    task:
      "Schlägt passende Textstellen vor; feste Prüfungen kontrollieren anschliessend Zitatposition und Belegstärke.",
    worksWith:
      "Aussagen, ausgewählten Quellen, Fundstellen und bereits bestätigten Belegen.",
    outputSummary: "Fundstellen, Zitate und Evidenzstatus.",
    humanReview:
      "Sie bestätigen, ob eine gefundene Textstelle die Aussage fachlich tatsächlich stützt.",
    decisionBoundary:
      "Eine technisch gefundene Fundstelle ist nicht automatisch ein fachlicher Beweis.",
    dataAccess:
      "Sieht die zu prüfenden Aussagen und ausgewählte Quellenausschnitte innerhalb des aktuellen Analysekontexts.",
    activeSteps: [3],
    availability: "available",
    technicalComponents: [
      "A1.evidence_candidate_mapping",
      "evidence.verification",
      "reliability.sufficiency",
    ],
    modelInfo: {
      kind: "model-route",
      primary: {
        provider: "OpenAI",
        model: "GPT-5.6 Luna",
      },
      fallback: {
        provider: "Anthropic",
        model: "Claude Haiku 4.5",
      },
      scope:
        "Nur für das Vorschlagen möglicher Belegstellen; Zitat- und Belegstärkeprüfung bleiben regelbasiert.",
    },
    providerSummary:
      "A1 schlägt Kandidaten vor; exakte Zitatprüfung und Belegstärke werden deterministisch kontrolliert.",
    technicalSource:
      "backend/app/agents/evidence_mapping.py, backend/app/evidence/verification.py, backend/app/reliability/sufficiency.py",
    dataClassRule:
      "KI erhält nur freigegebene Fragmente; Verifikation und Belegstärke laufen lokal auf dem eingefrorenen Quellenstand.",
  },
  {
    id: "innovationstext-assistent",
    name: "Innovationstext-Assistent",
    category: "specialist",
    mode: "ki",
    iconKey: "penLine",
    specialization:
      "Erstellt feldgerechte Textvorschläge mit Innovations- und Umsetzungsfokus.",
    task:
      "Formuliert auf Basis des Feldkontexts, bestätigter Fakten und verfügbarer Belege editierbare Vorschläge für unterstützte Antragsfelder.",
    worksWith:
      "Feldkontext, bestätigten Projektfakten, Belegen und offenen Prüfpunkten.",
    outputSummary: "Editierbare Vorschläge pro Antragsfeld.",
    humanReview:
      "Sie übernehmen, bearbeiten oder verwerfen jeden Vorschlag ausdrücklich.",
    decisionBoundary:
      "Ändert keinen Feldtext automatisch und bestimmt nie den finalen Antragstext.",
    dataAccess:
      "Sieht nur den Kontext des jeweiligen unterstützten Antragsfelds und die dafür freigegebenen Fakten und Belege.",
    activeSteps: [4],
    availability: "available",
    technicalComponents: ["A2 Portal Field Drafting"],
    modelInfo: {
      kind: "model-route",
      primary: {
        provider: "Anthropic",
        model: "Claude Sonnet 5",
      },
      fallback: {
        provider: "OpenAI",
        model: "GPT-5.6 Terra",
      },
      scope: "Für feldbezogene, editierbare Textvorschläge.",
    },
    providerSummary:
      "A2 – KI-gestützte Textvorschläge; Vorschläge werden nie automatisch übernommen.",
    technicalSource:
      "backend/app/agents/field_drafting.py, backend/app/agents/field_drafting_context.py",
    dataClassRule:
      "Die Verarbeitung richtet sich nach Datenklasse und Modus; gesperrte Inhalte werden nicht an externe Modelle übergeben.",
  },
  {
    id: "budget-portalpruefer",
    name: "Budget- und Portalprüfer",
    category: "specialist",
    mode: "regelbasiert",
    iconKey: "calculator",
    specialization:
      "Prüft Pflichtfelder, Zeichenlimits, Partnerstruktur und Budgetregeln reproduzierbar.",
    task:
      "Wendet die hinterlegten Partner-, Budget- und Portalfeldregeln auf den aktuellen Projektstand an und zeigt Abweichungen nachvollziehbar an.",
    worksWith:
      "Projekt-, Partner-, Budget- und Portalfelddaten sowie versionierten Regeldefinitionen.",
    outputSummary: "Blocker und Hinweise mit Regelbezug.",
    humanReview:
      "Sie ergänzen fehlende Angaben und entscheiden über Budget-, Partner- und Ausnahmefragen.",
    decisionBoundary:
      "Prüft definierte Regeln, erteilt aber keine verbindliche Budgetfreigabe und entscheidet nicht über Partnereignung oder Förderfähigkeit.",
    dataAccess:
      "Sieht strukturierte Projekt-, Partner-, Budget- und Portalfelddaten innerhalb der kontrollierten Verarbeitung.",
    activeSteps: [2, 3, 6],
    availability: "available",
    technicalComponents: [
      "rules.engine",
      "review.checks",
      "review.copy_readiness",
    ],
    modelInfo: {
      kind: "none",
      description:
        "Kein KI-Modell. Die Prüfung verwendet versionierte, feste Regeln.",
    },
    providerSummary: "Kein KI-Modell – versionierte, deterministische Regeln.",
    technicalSource:
      "backend/app/rules/engine.py, backend/app/review/checks.py, backend/app/review/copy_readiness.py",
    dataClassRule:
      "Regelprüfungen laufen lokal auf strukturierten Projektdaten und dem eingefrorenen Regelstand.",
  },
  {
    id: "beleg-vollstaendigkeitspruefer",
    name: "Beleg- und Vollständigkeitsprüfer",
    category: "specialist",
    mode: "regelbasiert",
    iconKey: "listChecks",
    specialization:
      "Markiert unbelegte Aussagen, fehlende Angaben und formale Unvollständigkeit.",
    task:
      "Prüft Entwürfe reproduzierbar auf leere Pflichtfelder, Platzhalter, Zeichenlimits, veraltete Belege und definierte Evidenzrisiken.",
    worksWith:
      "Aktuellen Feldtexten, verknüpften Belegen, Pflichtfeldern und Review-Status.",
    outputSummary: "Konkrete Qualitätsfindings.",
    humanReview:
      "Sie beurteilen die fachliche Aussage, ergänzen Belege und lösen gemeldete Lücken.",
    decisionBoundary:
      "Erkennt definierte Muster und Lücken, bestätigt aber keine fachliche Wahrheit und erteilt keine finale Freigabe.",
    dataAccess:
      "Sieht aktuelle Entwurfstexte, Belegverknüpfungen und formale Feldinformationen innerhalb des Projekts.",
    activeSteps: [5],
    availability: "available",
    technicalComponents: [
      "review.checks",
      "review.rubric",
      "reliability.executor",
    ],
    modelInfo: {
      kind: "none",
      description:
        "Kein KI-Modell. Qualitäts- und Vollständigkeitsprüfungen laufen deterministisch.",
    },
    providerSummary:
      "Kein KI-Modell – deterministische Qualitäts-, Vollständigkeits- und Evidenzprüfungen.",
    technicalSource:
      "backend/app/review/checks.py, backend/app/review/rubric.py, backend/app/reliability/executor.py",
    dataClassRule:
      "Die Prüfungen laufen lokal auf dem aktuellen, projektgebundenen Entwurfs- und Belegstand.",
  },
  {
    id: "qualitaetskoordinator",
    name: "Qualitätskoordinator",
    category: "specialist",
    mode: "hybrid",
    iconKey: "clipboardCheck",
    specialization:
      "Bündelt Prüfergebnisse, Blocker und offene Punkte zu einer priorisierten Aufgabenliste.",
    task:
      "Führt deterministische Findings, Evidenzrisiken und rein beratende A3-Hinweise in einem nachvollziehbaren Qualitätsstatus zusammen.",
    worksWith:
      "Offenen Issues, Regelresultaten, Qualitätsfindings und dem aktuellen Review-Paket.",
    outputSummary: "Qualitätsstatus und geordnete nächste Schritte.",
    humanReview:
      "Sie bearbeiten Blocker, bewerten beratende Hinweise und erteilen die finale Freigabe.",
    decisionBoundary:
      "A3-Hinweise bleiben beratend; die Funktion setzt keine Freigabe und erklärt keinen Antrag als einreichbereit.",
    dataAccess:
      "Sieht aktuelle Entwürfe, Regelresultate, Belegstatus und offene Prüfpunkte im Review-Kontext.",
    activeSteps: [5],
    availability: "available",
    technicalComponents: [
      "review.package",
      "review.fix_queue",
      "A3.evidence_consistency",
    ],
    modelInfo: {
      kind: "model-route",
      primary: {
        provider: "OpenAI",
        model: "GPT-5.6 Terra",
      },
      fallback: {
        provider: "Anthropic",
        model: "Claude Sonnet 5",
      },
      scope:
        "Nur für beratende Kritik; Aggregation, Priorisierung und Freigabelogik bleiben regelbasiert.",
    },
    providerSummary:
      "Deterministische Aggregation ergänzt durch rein beratende A3-Kritik, sofern verfügbar und erlaubt.",
    technicalSource:
      "backend/app/review/package.py, backend/app/review/fix_queue.py, backend/app/agents/critic_review.py",
    dataClassRule:
      "Deterministische Aggregation läuft lokal; A3 wird nur bei erlaubtem Verarbeitungsmodus und zulässiger Datenklasse aufgerufen.",
  },
  {
    id: "export-assistent",
    name: "Export-Assistent",
    category: "specialist",
    mode: "regelbasiert",
    iconKey: "fileOutput",
    specialization:
      "Bereitet geprüfte Inhalte für Word, JSON und die manuelle Innolink-Übernahme vor.",
    task:
      "Erstellt aus dem eingefrorenen Arbeitsstand editierbare Exportdateien und eine Kopieransicht für die manuelle Übernahme.",
    worksWith:
      "Aktuellen Feldtexten, Review-Status, Freigaben und strukturierten Projektdaten.",
    outputSummary: "Editierbares Exportpaket ohne automatische Einreichung.",
    humanReview:
      "Sie bestätigen Export, Kopiervorgänge und die manuelle Übernahme nach Innolink.",
    decisionBoundary:
      "Synchronisiert nichts mit Innolink, reicht nichts ein und bestätigt keine erfolgreiche Portaleingabe.",
    dataAccess:
      "Sieht den für den Export eingefrorenen Projekt-, Feld- und Review-Stand.",
    activeSteps: [6],
    availability: "available",
    technicalComponents: [
      "exports.service",
      "create_export_artifact",
      "manual portal copy view",
    ],
    modelInfo: {
      kind: "none",
      description:
        "Kein KI-Modell. Die Exporterzeugung läuft regelbasiert und ohne Netzwerkzugriff.",
    },
    providerSummary: "Kein KI-Modell – deterministische Exporterzeugung ohne Netzwerkzugriff.",
    technicalSource:
      "backend/app/exports/service.py, backend/app/exports/tool.py, components/portal-transfer/",
    dataClassRule:
      "Exportdateien werden aus einem eingefrorenen Snapshot erzeugt; technische Exporte enthalten keine Rohprompts oder Provider-Payloads.",
  },
]

export interface PhaseAssignment {
  step: number
  roleIds: string[]
  result: string
  humanAction: string
}

export const phaseAssignments: PhaseAssignment[] = [
  {
    step: 1,
    roleIds: [
      "workflow-koordinator",
      "suchanfragen-schutz",
      "marktrecherche-assistent",
    ],
    result:
      "Projektkontext, Quellenbestand und freigegebene Suchanfragen",
    humanAction:
      "Datenklasse festlegen und Websuchanfragen freigeben.",
  },
  {
    step: 2,
    roleIds: ["budget-portalpruefer"],
    result: "Partner- und Budgetcheck mit offenen Punkten",
    humanAction:
      "Partnerangaben, Beiträge und Budgetabweichungen prüfen.",
  },
  {
    step: 3,
    roleIds: [
      "anforderungsanalyst",
      "evidenzpruefer",
      "budget-portalpruefer",
    ],
    result: "Requirement Matrix mit nachvollziehbaren Fundstellen",
    humanAction:
      "Kritische Anforderungen und Belegstellen fachlich bestätigen.",
  },
  {
    step: 4,
    roleIds: ["innovationstext-assistent"],
    result: "Editierbare Textentwürfe pro Antragsfeld",
    humanAction:
      "Textvorschläge übernehmen, bearbeiten oder verwerfen.",
  },
  {
    step: 5,
    roleIds: [
      "beleg-vollstaendigkeitspruefer",
      "qualitaetskoordinator",
    ],
    result: "Qualitätsbericht und priorisierte Aufgabenliste",
    humanAction:
      "Blocker bearbeiten und finale Feldtexte freigeben.",
  },
  {
    step: 6,
    roleIds: ["budget-portalpruefer", "export-assistent"],
    result: "Geprüftes Exportpaket für die manuelle Übernahme",
    humanAction:
      "Export und manuelle Übernahme ausdrücklich bestätigen.",
  },
]

export interface KiTeamPhase {
  step: WorkflowStepDef
  roles: KiTeamRole[]
  result: string
  humanAction: string
}

const rolesById = new Map(kiTeamRoles.map((role) => [role.id, role]))

export function getKiTeamPhases(): KiTeamPhase[] {
  return phaseAssignments.map((assignment) => {
    const step = WORKFLOW_STEPS.find(
      (workflowStep) => workflowStep.step === assignment.step
    )
    if (!step) {
      throw new Error(`Unbekannter Workflow-Schritt: ${assignment.step}`)
    }
    const roles = assignment.roleIds.map((id) => {
      const role = rolesById.get(id)
      if (!role) {
        throw new Error(`Unbekannte Rolle im Phasenkatalog: ${id}`)
      }
      return role
    })
    return {
      step,
      roles,
      result: assignment.result,
      humanAction: assignment.humanAction,
    }
  })
}

export const roleCatalogGroups = [
  {
    category: "specialist" as RoleCategory,
    title: "Fachliche Spezialisten",
    roleIds: [
      "anforderungsanalyst",
      "evidenzpruefer",
      "marktrecherche-assistent",
      "innovationstext-assistent",
      "budget-portalpruefer",
      "beleg-vollstaendigkeitspruefer",
      "qualitaetskoordinator",
      "export-assistent",
    ],
  },
  {
    category: "system" as RoleCategory,
    title: "System & Schutz",
    roleIds: ["workflow-koordinator", "suchanfragen-schutz"],
  },
] as const

export function getRoleCatalogGroups() {
  return roleCatalogGroups.map((group) => ({
    ...group,
    roles: group.roleIds.map((id) => {
      const role = rolesById.get(id)
      if (!role) {
        throw new Error(`Unbekannte Rolle im Spezialistenkatalog: ${id}`)
      }
      return role
    }),
  }))
}

export const kiTeamTexts = {
  title: "Rollen & Verantwortung",
  subtitle:
    "Welche Systemrolle welche Aufgabe übernimmt, welches Ergebnis sie liefert – und welche Entscheidungen bei Ihnen bleiben.",
  prototypeBadge: "Forschungsprototyp",
  intro:
    "Das System verteilt Aufgaben auf KI-gestützte Rollen, feste Prüfdienste und menschliche Freigaben.",
  neverDecides: {
    title: "Das System entscheidet nie",
    points: [
      "ob das Projekt tatsächlich gefördert wird;",
      "ob ein Partner fachlich und strategisch geeignet ist;",
      "ob Budgetangaben verbindlich freigegeben werden;",
      "ob Belege fachlich korrekt interpretiert sind;",
      "welcher finale Antragstext verwendet wird;",
      "ob und wann der Antrag eingereicht wird;",
      "eine Förderwahrscheinlichkeit.",
    ],
  },
  dataProtection: {
    title: "Daten & Schutz",
    points: [
      "Keine automatische Einreichung",
      "Keine Websuche mit der Rohidee",
      "Kritische Punkte werden menschlich geprüft",
      "Technische Details bleiben eingeklappt",
    ],
  },
} as const
