import type { HumanCheck, MachineStatus } from "@/lib/types"

export type FieldStatus = "fulfilled" | "open"

export interface PortalSection {
  id: string
  /** Display field name. */
  name: string
  guidance: string
  mandatory: boolean
  status: FieldStatus
  charCount: number
  charLimit: number
}

export interface EvidenceChip {
  label: string
}

export interface AISuggestion {
  id: string
  text: string[]
  evidence: EvidenceChip[]
}

export interface EvidenceAnchor {
  id: string
  sourceTitle: string
  location: string
  status: MachineStatus
  humanCheck?: HumanCheck
}

export const portalSections: PortalSection[] = [
  {
    id: "value-creation",
    name: "Value Creation & Market Logic (Dummy)",
    guidance:
      "Erläutern Sie den Nutzen, den Markt und das Business Model des Vorhabens.",
    mandatory: true,
    status: "fulfilled",
    charCount: 2450,
    charLimit: 3000,
  },
  {
    id: "innovation",
    name: "Innovation & Technologie (Dummy)",
    guidance: "Was ist neu? Worin liegt der technologische Fortschritt?",
    mandatory: true,
    status: "open",
    charCount: 0,
    charLimit: 3000,
  },
  {
    id: "feasibility",
    name: "Machbarkeit & Arbeitsplan (Dummy)",
    guidance: "Beschreiben Sie Vorgehen, Meilensteine und Risiken.",
    mandatory: true,
    status: "open",
    charCount: 820,
    charLimit: 4000,
  },
  {
    id: "team",
    name: "Team & Kompetenzen (Dummy)",
    guidance: "Wer setzt das Vorhaben um? Welche Erfahrung liegt vor?",
    mandatory: true,
    status: "fulfilled",
    charCount: 1500,
    charLimit: 2000,
  },
  {
    id: "partners",
    name: "Umsetzungspartner (Dummy)",
    guidance: "Rolle und Beitrag der beteiligten Partner.",
    mandatory: false,
    status: "open",
    charCount: 300,
    charLimit: 1500,
  },
  {
    id: "budget",
    name: "Budget & Finanzierung (Dummy)",
    guidance: "Erläutern Sie die Mittelverwendung und Eigenleistung.",
    mandatory: true,
    status: "open",
    charCount: 0,
    charLimit: 2500,
  },
  {
    id: "impact",
    name: "Wirkung & Nachhaltigkeit (Dummy)",
    guidance: "Welche wirtschaftliche und gesellschaftliche Wirkung entsteht?",
    mandatory: false,
    status: "open",
    charCount: 640,
    charLimit: 2000,
  },
]

export const draftText =
  "Das Vorhaben adressiert einen wachsenden Markt für nachhaltige Verbundwerkstoffe (Dummy). " +
  "Der Nutzen für Industriekunden liegt in einer Reduktion der Materialkosten um rund 18 %, " +
  "bei gleichzeitig verbesserter Recyclingfähigkeit.\n\n" +
  "Das Business Model basiert auf Lizenzierung der Fertigungsverfahren sowie auf Beratungsleistungen " +
  "für die Integration in bestehende Produktionslinien (Dummy-Text)."

export const aiSuggestions: AISuggestion[] = [
  {
    id: "s1",
    text: [
      "Der adressierbare Markt für nachhaltige Verbundwerkstoffe wächst laut Branchenschätzungen jährlich im zweistelligen Bereich (Dummy).",
      "Eine differenzierte Positionierung gegenüber etablierten Anbietern entsteht durch die Kombination aus geringeren Materialkosten und höherer Recyclingfähigkeit.",
    ],
    evidence: [{ label: "McKinsey 2023 · S. 12" }, { label: "Marktstudie (Dummy) · S. 4" }],
  },
  {
    id: "s2",
    text: [
      "Das Business Model verbindet Lizenzeinnahmen mit wiederkehrenden Beratungsleistungen und schafft so eine stabile Erlösbasis (Dummy).",
    ],
    evidence: [{ label: "Interne Analyse (Dummy) · S. 8" }],
  },
  {
    id: "s3",
    text: [
      "Frühe Pilotkunden bestätigen die Zahlungsbereitschaft für recyclingfähige Materialien im Premiumsegment (Dummy).",
    ],
    evidence: [{ label: "Pilotbericht (Dummy)" }],
  },
  {
    id: "s4",
    text: [
      "Eine frühere Fassung betonte stärker die regulatorischen Treiber im europäischen Markt (Dummy).",
    ],
    evidence: [{ label: "EU-Bericht (Dummy) · S. 21" }],
  },
  {
    id: "s5",
    text: [
      "Alternative Formulierung mit Fokus auf Skalierungspotenzial der Fertigung (Dummy).",
    ],
    evidence: [{ label: "Interne Notiz (Dummy)" }],
  },
]

export const evidenceAnchors: EvidenceAnchor[] = [
  {
    id: "e1",
    sourceTitle: "McKinsey Materials Report 2023 (Dummy)",
    location: "S. 12, Abb. 4",
    status: "verified",
    humanCheck: { name: "Anna Keller", timestamp: "09:42" },
  },
  {
    id: "e2",
    sourceTitle: "Marktstudie Verbundwerkstoffe (Dummy)",
    location: "S. 4",
    status: "partial",
  },
  {
    id: "e3",
    sourceTitle: "Interne Wirtschaftlichkeitsrechnung (Dummy)",
    location: "S. 8, Tab. 2",
    status: "verified",
  },
  {
    id: "e4",
    sourceTitle: "Pilotbericht Industriekunde (Dummy)",
    location: "Abschnitt 3",
    status: "open",
  },
  {
    id: "e5",
    sourceTitle: "Patentrecherche (Dummy)",
    location: "Treffer 7",
    status: "partial",
  },
]

// Candidates offered in the "Beleg verknüpfen" sheet of the evidence panel:
// two anchors already linked to the section plus two not yet linked.
export const linkableEvidence: EvidenceAnchor[] = [
  evidenceAnchors[1],
  evidenceAnchors[3],
  {
    id: "e6",
    sourceTitle: "Technologie-Roadmap Leichtbau (Dummy)",
    location: "S. 17",
    status: "verified",
  },
  {
    id: "e7",
    sourceTitle: "EU-Bericht Kreislaufwirtschaft (Dummy)",
    location: "S. 21, Kap. 3",
    status: "partial",
  },
]
