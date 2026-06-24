// Dummy-Daten für die Quellen- & Evidenzseite. Kein Backend, keine echten Daten.
import type { DataClass, HumanCheck, MachineStatus } from "./types"

// ---------------------------------------------------------------------------
// Sources
// ---------------------------------------------------------------------------

export type SourceType = "PDF" | "DOCX" | "URL" | "Text"
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
}

export const dummySources: Source[] = [
  {
    id: "s1",
    name: "Innosuisse_Richtlinien_2025.pdf (Dummy)",
    type: "PDF",
    status: "processed",
    addedBy: "Anna Keller",
    addedAt: "heute, 09:15",
  },
  {
    id: "s2",
    name: "Marktanalyse_Materialien_Q1.pdf (Dummy)",
    type: "PDF",
    status: "processed",
    addedBy: "Tobias Frei",
    addedAt: "gestern, 14:30",
  },
  {
    id: "s3",
    name: "https://example.ch/foerderung (Dummy)",
    type: "URL",
    status: "processing",
    addedBy: "Anna Keller",
    addedAt: "heute, 10:02",
  },
  {
    id: "s4",
    name: "Zusammenfassung_Partnergespräch.txt (Dummy)",
    type: "Text",
    status: "failed",
    addedBy: "Tobias Frei",
    addedAt: "heute, 08:45",
    errorHint:
      "Datei konnte nicht verarbeitet werden — Format prüfen oder erneut hochladen.",
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
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf (Dummy)",
    fundstelle: "S. 3, Abs. 2",
    claimQuote:
      "Innovative Materialien mit verbesserter Ressourceneffizienz sind ein strategisches Förderziel.",
    section: "Problemstellung",
    machineStatus: "verified",
    humanCheck: { name: "Bruno Steiner", timestamp: "gestern, 16:10" },
    fullPassage:
      "Innovative Materialien mit verbesserter Ressourceneffizienz sind ein strategisches Förderziel der Innosuisse für die Periode 2025–2028. Antragsteller sollen den gesellschaftlichen und wirtschaftlichen Nutzen klar darlegen. (Dummy-Text)",
    confidencePercent: 94,
    linkedSections: ["Problemstellung", "Lösungsansatz"],
  },
  {
    id: "e2",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf (Dummy)",
    fundstelle: "S. 7, Tab. 1",
    claimQuote:
      "Der Markt für biobasierte Komposite wächst laut Studie jährlich um 12 %.",
    section: "Problemstellung",
    machineStatus: "partial",
    fullPassage:
      "Der Markt für biobasierte Komposite wächst laut Studie jährlich um 12 % und soll bis 2030 ein Volumen von mehreren Milliarden Franken erreichen. (Dummy-Text, keine echten Zahlen)",
    confidencePercent: 71,
    linkedSections: ["Problemstellung", "Marktpotenzial"],
  },
  // --- Stand der Technik ---
  {
    id: "e3",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf (Dummy)",
    fundstelle: "S. 12, Abb. 4",
    claimQuote:
      "Aktuelle Herstellungsverfahren weisen hohe Energieverluste im Sinterprozess auf.",
    section: "Stand der Technik",
    machineStatus: "verified",
    humanCheck: { name: "Anna Keller", timestamp: "heute, 09:42" },
    fullPassage:
      "Aktuelle Herstellungsverfahren für Hochleistungskeramiken weisen hohe Energieverluste im Sinterprozess auf. Eine Reduktion um 30 % gilt als realisierbar. (Dummy-Text)",
    confidencePercent: 88,
    linkedSections: ["Stand der Technik", "Lösungsansatz"],
  },
  {
    id: "e4",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf (Dummy)",
    fundstelle: "S. 15, Abs. 1",
    claimQuote:
      "Drei Patentfamilien decken das relevante Verfahrensfeld nahezu vollständig ab.",
    section: "Stand der Technik",
    machineStatus: "open",
    fullPassage:
      "Drei Patentfamilien aus Deutschland und Japan decken das relevante Verfahrensfeld nahezu vollständig ab. Eine Umgehungsstrategie ist im Projektplan darzulegen. (Dummy-Text)",
    confidencePercent: 62,
    linkedSections: ["Stand der Technik"],
  },
  // --- Lösungsansatz ---
  {
    id: "e5",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf (Dummy)",
    fundstelle: "S. 9, Abs. 4",
    claimQuote:
      "Neuartige Bindersysteme ermöglichen eine signifikante Reduktion der Prozesstemperatur.",
    section: "Lösungsansatz",
    machineStatus: "partial",
    fullPassage:
      "Neuartige Bindersysteme auf Cellulosebasis ermöglichen eine signifikante Reduktion der Prozesstemperatur und verbessern gleichzeitig die mechanischen Eigenschaften. (Dummy-Text)",
    confidencePercent: 78,
    linkedSections: ["Lösungsansatz", "Umsetzbarkeit"],
  },
  {
    id: "e6",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf (Dummy)",
    fundstelle: "S. 22, Abb. 7",
    claimQuote:
      "Das Verfahren ist skalierbar und wurde im Labormassstab bereits validiert.",
    section: "Lösungsansatz",
    machineStatus: "verified",
    fullPassage:
      "Das Verfahren ist skalierbar und wurde im Labormassstab mit einer Chargenfolge von 50 Zyklen bereits validiert. Die Reproduzierbarkeit liegt bei 97 %. (Dummy-Text)",
    confidencePercent: 91,
    linkedSections: ["Lösungsansatz"],
  },
  // --- Marktpotenzial ---
  {
    id: "e7",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf (Dummy)",
    fundstelle: "S. 28, Tab. 3",
    claimQuote:
      "Drei Pilotkunden haben unverbindliches Interesse an einer Abnahme bekundet.",
    section: "Marktpotenzial",
    machineStatus: "open",
    fullPassage:
      "Drei Pilotkunden aus der Automobil- und Bauindustrie haben unverbindliches Interesse an einer Abnahme bekundet. Vertragliche Zusagen liegen noch nicht vor. (Dummy-Text)",
    confidencePercent: 55,
    linkedSections: ["Marktpotenzial", "Partnerschaften"],
  },
  {
    id: "e8",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf (Dummy)",
    fundstelle: "S. 5, Abs. 3",
    claimQuote:
      "Anträge müssen den Schweizer Mehrwert und die geplante Wertschöpfung im Inland darlegen.",
    section: "Marktpotenzial",
    machineStatus: "partial",
    fullPassage:
      "Anträge müssen den Schweizer Mehrwert und die geplante Wertschöpfung im Inland darlegen. Fehlende Angaben führen zur Ablehnung des Antrags. (Dummy-Text)",
    confidencePercent: 83,
    linkedSections: ["Marktpotenzial"],
  },
  // --- Umsetzbarkeit ---
  {
    id: "e9",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf (Dummy)",
    fundstelle: "S. 31, Abs. 2",
    claimQuote:
      "Das Projektteam verfügt über ausgewiesene Expertise in der Materialcharakterisierung.",
    section: "Umsetzbarkeit",
    machineStatus: "verified",
    fullPassage:
      "Das Projektteam verfügt über ausgewiesene Expertise in der Materialcharakterisierung und hat in den letzten fünf Jahren 12 einschlägige Publikationen veröffentlicht. (Dummy-Text)",
    confidencePercent: 96,
    linkedSections: ["Umsetzbarkeit"],
  },
  // --- Nachhaltigkeit ---
  {
    id: "e10",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf (Dummy)",
    fundstelle: "S. 18, Abs. 1",
    claimQuote:
      "Nachhaltigkeitsziele müssen quantifiziert und messbar im Antrag verankert sein.",
    section: "Nachhaltigkeit",
    machineStatus: "open",
    fullPassage:
      "Nachhaltigkeitsziele müssen quantifiziert und messbar im Antrag verankert sein. Qualitative Aussagen allein genügen nicht den Förderkriterien. (Dummy-Text)",
    confidencePercent: 67,
    linkedSections: ["Nachhaltigkeit"],
  },
  // --- Partnerschaften ---
  {
    id: "e11",
    sourceTitle: "Marktanalyse_Materialien_Q1.pdf (Dummy)",
    fundstelle: "S. 40, Tab. 5",
    claimQuote:
      "Die Forschungspartnerin EMPA bringt einschlägige Infrastruktur in das Projekt ein.",
    section: "Partnerschaften",
    machineStatus: "verified",
    fullPassage:
      "Die Forschungspartnerin EMPA bringt einschlägige Infrastruktur und Messtechnik in das Projekt ein, die anderweitig nicht zugänglich wäre. (Dummy-Text)",
    confidencePercent: 89,
    linkedSections: ["Partnerschaften", "Umsetzbarkeit"],
  },
  {
    id: "e12",
    sourceTitle: "Innosuisse_Richtlinien_2025.pdf (Dummy)",
    fundstelle: "S. 6, Abs. 2",
    claimQuote:
      "Mindestens eine Forschungsinstitution muss als gleichberechtigte Partnerin beteiligt sein.",
    section: "Partnerschaften",
    machineStatus: "partial",
    fullPassage:
      "Mindestens eine anerkannte Forschungsinstitution muss als gleichberechtigte Partnerin beteiligt sein und aktiv Forschungsleistungen erbringen. (Dummy-Text)",
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
