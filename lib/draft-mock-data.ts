// Dummy data for the Entwurf (portal field editor). No backend, no real data.
// Field/section names mirror the Innolink portal structure.

import type { DraftEvidenceStatus, DraftFieldStatus } from "./draft-view"
import type { ReqBucket } from "./requirements-view"
import type { MarketDataset } from "./market-view"

export interface DraftEvidence {
  id: string
  claim: string
  source: string
  fundstelle: string
  status: DraftEvidenceStatus
}

export interface DraftRequirement {
  id: string
  title: string
  status: ReqBucket
}

export interface DraftPerson {
  name: string
  initials: string
}

export interface DraftComment {
  id: string
  author: DraftPerson
  timestamp: string
  text: string
  resolved: boolean
}

export interface DraftVersion {
  id: string
  label: string
  timestamp: string
  author: string
  current?: boolean
}

export interface DraftField {
  id: string
  name: string
  sectionId: string
  status: DraftFieldStatus
  /** Current draft text — empty string means "no draft yet". */
  text: string
  charLimit?: number | null
  guidance: string
  reviewStatus: string
  exportStatus?: string
  lastEditedLabel?: string
  openPoints: string[]
  evidence: DraftEvidence[]
  requirements: DraftRequirement[]
}

export interface DraftSection {
  id: string
  label: string
}

export const draftSections: DraftSection[] = [
  { id: "introduction", label: "Introduction" },
  { id: "org", label: "Organisations & People" },
  { id: "value", label: "Value Creation" },
  { id: "solution", label: "Solution" },
  { id: "setup", label: "Project Setup" },
  { id: "summary", label: "Summary & Submit" },
]

export const draftFields: DraftField[] = [
  {
    id: "INTRO.APP.NAME",
    name: "Application Name",
    sectionId: "introduction",
    status: "ready",
    text: "KI-gestützte Materialentwicklung für nachhaltige Verbundwerkstoffe",
    charLimit: 120,
    guidance: "Kurzer, prägnanter Projekttitel für das Innolink-Portal.",
    reviewStatus: "Geprüft",
    exportStatus: "Bereit für Export",
    lastEditedLabel: "Zuletzt bearbeitet: heute, 09:42 von Anna Keller",
    openPoints: [],
    evidence: [
      {
        id: "ev-name-1",
        claim: "Projekttitel entspricht dem Intake-Formular.",
        source: "Intake-Formular",
        fundstelle: "Feld 1",
        status: "verified",
      },
    ],
    requirements: [
      { id: "r07", title: "Projekttitel ausgefüllt", status: "fulfilled" },
    ],
  },
  {
    id: "INTRO.APP.ABSTRACT",
    name: "Abstract",
    sectionId: "introduction",
    status: "needs_review",
    text:
      "Das Vorhaben entwickelt ein neuartiges Bindersystem zur Reduktion der Prozesstemperatur. " +
      "[[Angabe ergänzen: quantifizierter Nutzen für Industriekunden]]",
    charLimit: 300,
    guidance:
      "Allgemeinverständliche Zusammenfassung des Vorhabens (max. 300 Zeichen).",
    reviewStatus: "Prüfung nötig",
    lastEditedLabel: "Zuletzt bearbeitet: heute, 08:03 von Anna Keller",
    openPoints: ["Quantifizierter Nutzen fehlt noch."],
    evidence: [
      {
        id: "ev-abs-1",
        claim: "Reduktion der Prozesstemperatur um rund 30 % realisierbar.",
        source: "Innosuisse Richtlinien 2025.pdf",
        fundstelle: "S. 12 · Abschnitt 4",
        status: "review",
      },
    ],
    requirements: [
      { id: "r01", title: "Innovationscharakter nachgewiesen", status: "partial" },
    ],
  },
  {
    id: "INTRO.APP.SUMMARY",
    name: "Executive Summary",
    sectionId: "introduction",
    status: "open",
    text: "",
    charLimit: 2000,
    guidance:
      "Management-Zusammenfassung mit Problem, Lösung, Markt und Wirkung.",
    reviewStatus: "Noch nicht geprüft",
    openPoints: ["Noch kein Entwurf vorhanden."],
    evidence: [],
    requirements: [],
  },
  {
    id: "ORG.PARTNERS",
    name: "Project Partners",
    sectionId: "org",
    status: "ready",
    text:
      "Forschungspartner: ETH Zürich. Umsetzungspartner: Müller AG, Zürich. " +
      "Beide Partner sind im Antrag mit Rolle und Beitrag beschrieben.",
    charLimit: 1500,
    guidance: "Beteiligte Organisationen mit Rolle und Beitrag.",
    reviewStatus: "Geprüft",
    lastEditedLabel: "Zuletzt bearbeitet: gestern, 14:15 von Tobias Frei",
    openPoints: [],
    evidence: [
      {
        id: "ev-part-1",
        claim: "ETH Zürich ist anerkannte Forschungsinstitution.",
        source: "Partnerliste Innosuisse 2024.pdf",
        fundstelle: "S. 3",
        status: "verified",
      },
    ],
    requirements: [
      {
        id: "r02",
        title: "Schweizer Forschungspartner eingebunden",
        status: "fulfilled",
      },
    ],
  },
  {
    id: "VC.BUSINESS",
    name: "Business Targets & Business Model",
    sectionId: "value",
    status: "no_evidence",
    text:
      "Das Business Model basiert auf der Lizenzierung der Fertigungsverfahren " +
      "sowie auf Beratungsleistungen für die Integration in bestehende Produktionslinien.",
    charLimit: 3000,
    guidance: "Markt, Geschäftsmodell und wirtschaftliche Ziele.",
    reviewStatus: "Prüfung nötig",
    lastEditedLabel: "Zuletzt bearbeitet: heute, 10:15 von Anna Keller",
    openPoints: ["Noch kein Beleg mit diesem Feld verknüpft."],
    evidence: [],
    requirements: [
      {
        id: "r05",
        title: "Wirtschaftliche Verwertung geplant",
        status: "partial",
      },
    ],
  },
  {
    id: "SOL.INNOVATION",
    name: "Innovation Solution",
    sectionId: "solution",
    status: "needs_review",
    text:
      "Neuartige Bindersysteme auf Cellulosebasis ermöglichen eine signifikante " +
      "Reduktion der Prozesstemperatur bei verbesserten mechanischen Eigenschaften.",
    charLimit: 3000,
    guidance: "Technologischer Kern und Abgrenzung zum Stand der Technik.",
    reviewStatus: "Prüfung nötig",
    lastEditedLabel: "Zuletzt bearbeitet: heute, 09:05 von Anna Keller",
    openPoints: [],
    evidence: [
      {
        id: "ev-sol-1",
        claim: "Verfahren im Labormassstab validiert (50 Zyklen).",
        source: "Marktanalyse Materialien.pdf",
        fundstelle: "S. 22 · Abschnitt 7",
        status: "verified",
      },
      {
        id: "ev-sol-2",
        claim: "Drei Patentfamilien decken das Verfahrensfeld ab.",
        source: "Marktanalyse Materialien.pdf",
        fundstelle: "S. 15",
        status: "open",
      },
    ],
    requirements: [
      {
        id: "r17",
        title: "Risikobewertung vorhanden",
        status: "fulfilled",
      },
    ],
  },
  {
    id: "PS.PLAN",
    name: "Project Plan",
    sectionId: "setup",
    status: "blocked",
    text:
      "Arbeitspaket 1: Materialcharakterisierung. Arbeitspaket 2: Prozessintegration. " +
      "TODO: Meilensteine und Abhängigkeiten ergänzen.",
    charLimit: 4000,
    guidance: "Arbeitspakete, Meilensteine und Zeitplan.",
    reviewStatus: "Blockiert",
    lastEditedLabel: "Zuletzt bearbeitet: vorgestern, 11:30 von Anna Keller",
    openPoints: [
      "Meilensteine und Abhängigkeiten fehlen.",
      "Regelung der Verwertungsrechte offen (Blocker).",
    ],
    evidence: [],
    requirements: [
      { id: "r19", title: "Verwertungsrechte geregelt", status: "blocked" },
    ],
  },
  {
    id: "PS.RISK",
    name: "Risk Management",
    sectionId: "setup",
    status: "open",
    text: "",
    charLimit: 2000,
    guidance: "Wesentliche Risiken und geplante Gegenmassnahmen.",
    reviewStatus: "Noch nicht geprüft",
    openPoints: ["Noch kein Entwurf vorhanden."],
    evidence: [],
    requirements: [],
  },
  {
    id: "SUMMARY.SUBMIT",
    name: "Summary & Submit",
    sectionId: "summary",
    status: "open",
    text: "",
    charLimit: 1000,
    guidance: "Abschliessende Zusammenfassung vor der Abgabe.",
    reviewStatus: "Noch nicht geprüft",
    openPoints: ["Wird am Ende auf Basis der übrigen Felder erstellt."],
    evidence: [],
    requirements: [],
  },
]

// ---------------------------------------------------------------------------
// Collaboration (mock): responsible/reviewer, comments and version history per
// field. Looked up by field id; fields without an entry fall back in the UI.
// ---------------------------------------------------------------------------
const ANNA: DraftPerson = { name: "Anna Keller", initials: "AK" }
const TOBIAS: DraftPerson = { name: "Tobias Frei", initials: "TF" }
const MARA: DraftPerson = { name: "Mara Stucki", initials: "MS" }

export const mockResponsibleByField: Record<string, DraftPerson> = {
  "INTRO.APP.ABSTRACT": ANNA,
  "VC.BUSINESS": ANNA,
  "SOL.INNOVATION": TOBIAS,
}

export const mockReviewerByField: Record<string, DraftPerson> = {
  "VC.BUSINESS": MARA,
  "SOL.INNOVATION": ANNA,
}

export const mockCommentsByField: Record<string, DraftComment[]> = {
  "INTRO.APP.ABSTRACT": [
    {
      id: "c-abs-1",
      author: ANNA,
      timestamp: "heute, 08:03",
      text: "Quantifizierten Nutzen für Industriekunden noch ergänzen.",
      resolved: false,
    },
  ],
  "VC.BUSINESS": [
    {
      id: "c-vc-1",
      author: MARA,
      timestamp: "gestern, 14:15",
      text: "Bitte Marktgrösse mit einer Quelle belegen.",
      resolved: false,
    },
    {
      id: "c-vc-2",
      author: ANNA,
      timestamp: "heute, 09:42",
      text: "Differenzierung gegenüber CeramTech ergänzt.",
      resolved: true,
    },
  ],
}

export const mockVersionsByField: Record<string, DraftVersion[]> = {
  "VC.BUSINESS": [
    { id: "v-vc-3", label: "Aktuelle Version", timestamp: "heute, 10:15", author: "Anna Keller", current: true },
    { id: "v-vc-2", label: "Marktargument ergänzt", timestamp: "gestern, 16:40", author: "Tobias Frei" },
    { id: "v-vc-1", label: "Erstentwurf (Vorlage)", timestamp: "12.06.2026", author: "Vorlage" },
  ],
  "INTRO.APP.ABSTRACT": [
    { id: "v-abs-1", label: "Aktuelle Version", timestamp: "heute, 08:03", author: "Anna Keller", current: true },
  ],
}

// ---------------------------------------------------------------------------
// Market & competition (mock): datasets per section. Only Value Creation and
// Solution are market-relevant. Everything carries an evidence status.
// ---------------------------------------------------------------------------
export const mockMarketBySection: Record<string, MarketDataset> = {
  value: {
    status: "teilweise_belegt",
    overview: {
      targetMarket: "Hersteller von Hochleistungskeramik in der DACH-Region",
      customerSegment: "Industrielle Zulieferer und OEMs der Materialbranche",
      marketProblem: "Hohe Energiekosten und Ausschuss im Sinterprozess",
      customerBenefit: "Reduktion der Material- und Energiekosten um rund 18 %",
      status: "teilweise_belegt",
    },
    competitors: [
      {
        id: "comp-vc-1",
        name: "CeramTech AG",
        focus: "Etablierte Sinterverfahren",
        strength: "Grosse Produktionskapazität, etablierte Kundenbasis",
        gap: "Hoher Energieverbrauch, kein cellulosebasiertes Bindersystem",
        differentiation: "Niedrigere Prozesstemperatur senkt Energiekosten deutlich",
        source: { label: "Marktanalyse Materialien.pdf", fundstelle: "S. 7" },
        status: "belegt",
      },
      {
        id: "comp-vc-2",
        name: "BioBinder Labs",
        focus: "Biobasierte Bindersysteme",
        strength: "Frühe Patente im Verfahrensfeld",
        gap: "Noch nicht industriell skaliert",
        differentiation: "Im Labormassstab über 50 Zyklen validiertes Verfahren",
        source: { label: "Patentrecherche.pdf", fundstelle: "S. 3" },
        status: "teilweise_belegt",
      },
      {
        id: "comp-vc-3",
        name: "Inhouse-Verfahren grosser OEMs",
        focus: "Eigene, nicht veröffentlichte Prozesse",
        strength: "Vertikale Integration",
        gap: "Geringe Transparenz, vermutlich konventionelle Prozesse",
        differentiation: "Offen belegbare Energie- und Recyclingvorteile",
        source: null,
        status: "quelle_fehlt",
      },
    ],
    differentiation: [
      {
        id: "diff-vc-1",
        whatIsDifferent: "Cellulosebasiertes Bindersystem senkt die Prozesstemperatur um rund 30 %",
        whyRelevant: "Direkter Kostenvorteil für energieintensive Fertigung",
        source: { label: "Innosuisse Richtlinien 2025.pdf", fundstelle: "S. 12" },
        targetField: "Value Creation › Business Targets & Business Model",
        status: "belegt",
      },
      {
        id: "diff-vc-2",
        whatIsDifferent: "Höhere Recyclingfähigkeit der Komposite",
        whyRelevant: "Adressiert regulatorische Treiber der Kreislaufwirtschaft",
        source: null,
        targetField: "Solution › Innovation Solution",
        status: "quelle_fehlt",
      },
      {
        id: "diff-vc-3",
        whatIsDifferent: "Skalierbarkeit im Labormassstab bereits gezeigt",
        whyRelevant: "Reduziert das Umsetzungsrisiko gegenüber reinen Konzepten",
        source: { label: "Marktanalyse Materialien.pdf", fundstelle: "S. 22" },
        targetField: "Value Creation › Business Targets & Business Model",
        status: "teilweise_belegt",
      },
    ],
    openQuestions: [
      "Aktuelle Marktgrösse für biobasierte Komposite quantifizieren.",
      "Zahlungsbereitschaft der Pilotkunden mit einer Quelle belegen.",
    ],
    risk: {
      title: "Risiko: Lösung existiert bereits teilweise im Markt",
      text: "Die Analyse deutet darauf hin, dass ähnliche Lösungen existieren. Der Antrag sollte daher nicht absolute Neuheit behaupten, sondern die konkrete Differenzierung belegen.",
    },
  },
  solution: {
    status: "pruefung_noetig",
    overview: {
      targetMarket: "Industrielle Anwendungen mit hohen Materialanforderungen",
      customerSegment: "Forschungs- und Entwicklungsabteilungen der Zulieferer",
      marketProblem: "Etablierte Verfahren erreichen die Energie- und Recyclingziele nicht",
      customerBenefit: "Technologischer Vorsprung bei Effizienz und Nachhaltigkeit",
      status: "pruefung_noetig",
    },
    competitors: [
      {
        id: "comp-sol-1",
        name: "Etablierte Sinter-Patentfamilien",
        focus: "Konventionelle Hochtemperaturprozesse",
        strength: "Breite Schutzrechte im Verfahrensfeld",
        gap: "Keine Reduktion der Prozesstemperatur adressiert",
        differentiation: "Umgehungsstrategie über neuartige Bindersysteme",
        source: { label: "Marktanalyse Materialien.pdf", fundstelle: "S. 15" },
        status: "teilweise_belegt",
      },
      {
        id: "comp-sol-2",
        name: "Alternative Materialansätze",
        focus: "Kunststoff-/Metall-Hybride",
        strength: "Etablierte Lieferketten",
        gap: "Geringere Hitzebeständigkeit",
        differentiation: "Höhere thermische Belastbarkeit der Keramik",
        source: null,
        status: "quelle_fehlt",
      },
    ],
    differentiation: [
      {
        id: "diff-sol-1",
        whatIsDifferent: "Neuartiges Bindersystem statt konventioneller Hochtemperaturprozess",
        whyRelevant: "Grenzt klar von bestehenden Patentfamilien ab",
        source: { label: "Marktanalyse Materialien.pdf", fundstelle: "S. 15" },
        targetField: "Solution › Innovation Solution",
        status: "teilweise_belegt",
      },
      {
        id: "diff-sol-2",
        whatIsDifferent: "Reproduzierbarkeit von 97 % im Labormassstab",
        whyRelevant: "Belegt die technische Machbarkeit",
        source: { label: "Marktanalyse Materialien.pdf", fundstelle: "S. 22" },
        targetField: "Solution › Innovation Solution",
        status: "belegt",
      },
    ],
    openQuestions: [
      "Abgrenzung gegenüber den drei Patentfamilien belegen.",
    ],
    risk: {
      title: "Risiko: Lösung existiert bereits teilweise im Markt",
      text: "Ähnliche Verfahren sind durch Patente abgedeckt. Der Antrag sollte die konkrete Differenzierung statt absoluter Neuheit belegen.",
    },
  },
}
