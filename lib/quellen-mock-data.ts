// Dummy-Daten für die Quellen- & Evidenzseite. Kein Backend, keine echten Daten.
import type { DataClass, HumanCheck, MachineStatus } from "./types"

// ---------------------------------------------------------------------------
// Sources
// ---------------------------------------------------------------------------

export type SourceType = "PDF" | "DOCX" | "URL" | "Text" | "Übernommen"
// Aligned with the contract SourceDocument status enum.
export type SourceStatus =
  | "uploaded"
  | "processing"
  | "processed"
  | "needs_manual_input"
  | "failed"

export interface Source {
  id: string
  name: string
  type: SourceType
  status: SourceStatus
  addedBy: string
  addedAt: string
  /** Set for failed / needs_manual_input states. */
  errorHint?: string
  /** Optional short context used in details dialogs. */
  note?: string
  /**
   * Datenklasse of the source. Missing/unknown values are always treated as
   * confidential (never silently imported across projects).
   */
  dataClass?: DataClass
}

export const dummySources: Source[] = [
  {
    id: "s1",
    name: "Innosuisse_Richtlinien_Innovationsprojekte_2025.pdf",
    type: "PDF",
    status: "processed",
    addedBy: "Anna Keller",
    addedAt: "heute, 09:15",
  },
  {
    id: "s2",
    name: "Marktanalyse_Biobasierte_Materialien_Q1.pdf",
    type: "PDF",
    status: "processed",
    addedBy: "Tobias Frei",
    addedAt: "gestern, 14:30",
  },
  {
    id: "s3",
    name: "https://www.innosuisse.admin.ch/innovation-projects",
    type: "URL",
    status: "processing",
    addedBy: "Anna Keller",
    addedAt: "heute, 10:02",
    note: "Manuell hinzugefügte öffentliche Webseite.",
  },
  {
    id: "s4",
    name: "Zusammenfassung Partnergespräch EMPA",
    type: "Text",
    status: "failed",
    addedBy: "Tobias Frei",
    addedAt: "heute, 08:45",
    errorHint:
      "Die Quelle konnte nicht verarbeitet werden. Bitte Format prüfen, erneut hochladen oder die Quelle entfernen.",
  },
]

export type UrlSourceKind = "webpage" | "pdf" | "faq" | "guideline"

export const URL_SOURCE_KIND_LABELS: Record<UrlSourceKind, string> = {
  webpage: "Webseite",
  pdf: "PDF",
  faq: "FAQ",
  guideline: "Richtlinie",
}

export interface ImportableSourceProject {
  id: string
  title: string
  sources: Source[]
}

export const importableSourceProjects: ImportableSourceProject[] = [
  {
    id: "materialentwicklung",
    title: "KI-gestützte Materialentwicklung",
    sources: [
      {
        id: "mat-src-1",
        name: "Patentrecherche Hochleistungskeramik.pdf",
        type: "PDF",
        status: "processed",
        addedBy: "Anna Keller",
        addedAt: "12.06.2026",
        dataClass: "internal",
      },
      {
        id: "mat-src-2",
        name: "Pilotbericht Industriekunde",
        type: "Text",
        status: "processed",
        addedBy: "Tobias Frei",
        addedAt: "18.06.2026",
        dataClass: "confidential",
      },
    ],
  },
  {
    id: "sensorik",
    title: "Sensorik-Plattform für Produktionsanlagen",
    sources: [
      {
        id: "sen-src-1",
        name: "Marktübersicht Predictive Maintenance.pdf",
        type: "PDF",
        status: "processed",
        addedBy: "Mara Stucki",
        addedAt: "05.06.2026",
        dataClass: "public",
      },
      {
        id: "sen-src-2",
        name: "https://www.innosuisse.admin.ch/digitalisierung",
        type: "URL",
        status: "processed",
        addedBy: "Anna Keller",
        addedAt: "09.06.2026",
        dataClass: "public",
      },
    ],
  },
  {
    id: "medtech",
    title: "Digitale Zwillinge in der Medizintechnik",
    sources: [
      {
        // Deliberately without dataClass — exercises the "unknown is treated
        // as confidential" import path.
        id: "med-src-1",
        name: "Regulatorische Hinweise MDR.pdf",
        type: "PDF",
        status: "processed",
        addedBy: "Jonas Meier",
        addedAt: "21.06.2026",
      },
      {
        id: "med-src-2",
        name: "Technologie-Roadmap Simulation",
        type: "Text",
        status: "processed",
        addedBy: "Anna Keller",
        addedAt: "22.06.2026",
      },
    ],
  },
]

// ---------------------------------------------------------------------------
// Analysis progress steps (used in the running-analysis banner)
// ---------------------------------------------------------------------------

export type ProgressStepState = "done" | "running" | "pending"

export interface AnalysisProgressStep {
  id: string
  label: string
  state: ProgressStepState
}

export const dummyAnalysisSteps: AnalysisProgressStep[] = [
  { id: "as1", label: "Quellen werden aufbereitet", state: "done" },
  { id: "as2", label: "Anforderungen werden erkannt", state: "done" },
  { id: "as3", label: "Belege werden verknüpft", state: "running" },
  { id: "as4", label: "Qualität wird geprüft", state: "pending" },
]

// ---------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------

export type EvidenceSection =
  | "Problemstellung"
  | "Stand der Technik"
  | "Lösungsansatz"
  | "Marktpotenzial"
  | "Umsetzbarkeit"
  | "Nachhaltigkeit"
  | "Partnerschaften"

export interface EvidenceCard {
  id: string
  sourceTitle: string
  fundstelle: string
  claimQuote: string
  section: EvidenceSection
  machineStatus: MachineStatus
  humanCheck?: HumanCheck
  /** Full passage shown only in the drawer. */
  fullPassage: string
  /** Confidence shown only in the drawer (0–100). */
  confidencePercent: number
  linkedSections: string[]
}

export const dummyEvidence: EvidenceCard[] = [
  // --- Problemstellung ---
  {
    id: "e1",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf",
    fundstelle: "S. 3, Abs. 2",
    claimQuote:
      "Innovative Materialien mit verbesserter Ressourceneffizienz sind ein strategisches Förderziel.",
    section: "Problemstellung",
    machineStatus: "verified",
    humanCheck: { name: "Bruno Steiner", timestamp: "gestern, 16:10" },
    fullPassage:
      "Innovative Materialien mit verbesserter Ressourceneffizienz sind ein strategisches Förderziel der Innosuisse für die Periode 2025–2028. Antragsteller sollen den gesellschaftlichen und wirtschaftlichen Nutzen klar darlegen.",
    confidencePercent: 94,
    linkedSections: ["Problemstellung", "Lösungsansatz"],
  },
  {
    id: "e2",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf",
    fundstelle: "S. 7, Tab. 1",
    claimQuote:
      "Der Markt für biobasierte Komposite wächst laut Studie jährlich um 12 %.",
    section: "Problemstellung",
    machineStatus: "partial",
    fullPassage:
      "Der Markt für biobasierte Komposite wächst laut Studie jährlich um 12 % und soll bis 2030 ein Volumen von mehreren Milliarden Franken erreichen.",
    confidencePercent: 71,
    linkedSections: ["Problemstellung", "Marktpotenzial"],
  },
  // --- Stand der Technik ---
  {
    id: "e3",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf",
    fundstelle: "S. 12, Abb. 4",
    claimQuote:
      "Aktuelle Herstellungsverfahren weisen hohe Energieverluste im Sinterprozess auf.",
    section: "Stand der Technik",
    machineStatus: "verified",
    humanCheck: { name: "Anna Keller", timestamp: "heute, 09:42" },
    fullPassage:
      "Aktuelle Herstellungsverfahren für Hochleistungskeramiken weisen hohe Energieverluste im Sinterprozess auf. Eine Reduktion um 30 % gilt als realisierbar.",
    confidencePercent: 88,
    linkedSections: ["Stand der Technik", "Lösungsansatz"],
  },
  {
    id: "e4",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf",
    fundstelle: "S. 15, Abs. 1",
    claimQuote:
      "Drei Patentfamilien decken das relevante Verfahrensfeld nahezu vollständig ab.",
    section: "Stand der Technik",
    machineStatus: "open",
    fullPassage:
      "Drei Patentfamilien aus Deutschland und Japan decken das relevante Verfahrensfeld nahezu vollständig ab. Eine Umgehungsstrategie ist im Projektplan darzulegen.",
    confidencePercent: 62,
    linkedSections: ["Stand der Technik"],
  },
  // --- Lösungsansatz ---
  {
    id: "e5",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf",
    fundstelle: "S. 9, Abs. 4",
    claimQuote:
      "Neuartige Bindersysteme ermöglichen eine signifikante Reduktion der Prozesstemperatur.",
    section: "Lösungsansatz",
    machineStatus: "partial",
    fullPassage:
      "Neuartige Bindersysteme auf Cellulosebasis ermöglichen eine signifikante Reduktion der Prozesstemperatur und verbessern gleichzeitig die mechanischen Eigenschaften.",
    confidencePercent: 78,
    linkedSections: ["Lösungsansatz", "Umsetzbarkeit"],
  },
  {
    id: "e6",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf",
    fundstelle: "S. 22, Abb. 7",
    claimQuote:
      "Das Verfahren ist skalierbar und wurde im Labormassstab bereits validiert.",
    section: "Lösungsansatz",
    machineStatus: "verified",
    fullPassage:
      "Das Verfahren ist skalierbar und wurde im Labormassstab mit einer Chargenfolge von 50 Zyklen bereits validiert. Die Reproduzierbarkeit liegt bei 97 %.",
    confidencePercent: 91,
    linkedSections: ["Lösungsansatz"],
  },
  // --- Marktpotenzial ---
  {
    id: "e7",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf",
    fundstelle: "S. 28, Tab. 3",
    claimQuote:
      "Drei Pilotkunden haben unverbindliches Interesse an einer Abnahme bekundet.",
    section: "Marktpotenzial",
    machineStatus: "open",
    fullPassage:
      "Drei Pilotkunden aus der Automobil- und Bauindustrie haben unverbindliches Interesse an einer Abnahme bekundet. Vertragliche Zusagen liegen noch nicht vor.",
    confidencePercent: 55,
    linkedSections: ["Marktpotenzial", "Partnerschaften"],
  },
  {
    id: "e8",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf",
    fundstelle: "S. 5, Abs. 3",
    claimQuote:
      "Anträge müssen den Schweizer Mehrwert und die geplante Wertschöpfung im Inland darlegen.",
    section: "Marktpotenzial",
    machineStatus: "partial",
    fullPassage:
      "Anträge müssen den Schweizer Mehrwert und die geplante Wertschöpfung im Inland darlegen. Fehlende Angaben führen zur Ablehnung des Antrags.",
    confidencePercent: 83,
    linkedSections: ["Marktpotenzial"],
  },
  // --- Umsetzbarkeit ---
  {
    id: "e9",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf",
    fundstelle: "S. 31, Abs. 2",
    claimQuote:
      "Das Projektteam verfügt über ausgewiesene Expertise in der Materialcharakterisierung.",
    section: "Umsetzbarkeit",
    machineStatus: "verified",
    fullPassage:
      "Das Projektteam verfügt über ausgewiesene Expertise in der Materialcharakterisierung und hat in den letzten fünf Jahren 12 einschlägige Publikationen veröffentlicht.",
    confidencePercent: 96,
    linkedSections: ["Umsetzbarkeit"],
  },
  // --- Nachhaltigkeit ---
  {
    id: "e10",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf",
    fundstelle: "S. 18, Abs. 1",
    claimQuote:
      "Nachhaltigkeitsziele müssen quantifiziert und messbar im Antrag verankert sein.",
    section: "Nachhaltigkeit",
    machineStatus: "open",
    fullPassage:
      "Nachhaltigkeitsziele müssen quantifiziert und messbar im Antrag verankert sein. Qualitative Aussagen allein genügen nicht den Förderkriterien.",
    confidencePercent: 67,
    linkedSections: ["Nachhaltigkeit"],
  },
  // --- Partnerschaften ---
  {
    id: "e11",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf",
    fundstelle: "S. 40, Tab. 5",
    claimQuote:
      "Die Forschungspartnerin EMPA bringt einschlägige Infrastruktur in das Projekt ein.",
    section: "Partnerschaften",
    machineStatus: "verified",
    fullPassage:
      "Die Forschungspartnerin EMPA bringt einschlägige Infrastruktur und Messtechnik in das Projekt ein, die anderweitig nicht zugänglich wäre.",
    confidencePercent: 89,
    linkedSections: ["Partnerschaften", "Umsetzbarkeit"],
  },
  {
    id: "e12",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf",
    fundstelle: "S. 6, Abs. 2",
    claimQuote:
      "Mindestens eine Forschungsinstitution muss als gleichberechtigte Partnerin beteiligt sein.",
    section: "Partnerschaften",
    machineStatus: "partial",
    fullPassage:
      "Mindestens eine anerkannte Forschungsinstitution muss als gleichberechtigte Partnerin beteiligt sein und aktiv Forschungsleistungen erbringen.",
    confidencePercent: 80,
    linkedSections: ["Partnerschaften"],
  },
]

export const EVIDENCE_SECTIONS: EvidenceSection[] = [
  "Problemstellung",
  "Stand der Technik",
  "Lösungsansatz",
  "Marktpotenzial",
  "Umsetzbarkeit",
  "Nachhaltigkeit",
  "Partnerschaften",
]

// Page-level state used by the demo toggles
export type PageAnalysisState = "idle" | "running" | "stopped" | "completed"
export const defaultDataClass: DataClass = "public"
