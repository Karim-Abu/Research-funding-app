// Dummy-Daten für Anforderungen & Fördervoraussetzungen (Schritt 3).
// Keine echten Daten, keine Backend-Aufrufe.

import type { MachineStatus, HumanCheck } from "@/lib/types"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RequirementGroup =
  | "Fördervoraussetzungen"
  | "Pflichtfelder des Beta-Profils"
  | "Budget-Prüfung"
  | "Passung & Lücken"

export interface EvidenceChip {
  label: string
  /** ID of the EvidenceCard in quellen-mock-data to open in the drawer. */
  evidenceCardId: string
}

export interface OverrideRecord {
  byName: string
  newStatus: MachineStatus
  comment: string
  timestamp: string
}

export interface Requirement {
  id: string
  group: RequirementGroup
  title: string
  /** One-sentence reason shown in the row summary. */
  reason: string
  /** Expanded detail text. */
  detail: string
  machineStatus: MachineStatus
  /** When null, row shows "Kein Beleg gefunden — bitte prüfen." and status is forced open. */
  evidence: EvidenceChip | null
  humanCheck?: HumanCheck
  override?: OverrideRecord
}

export interface RunState {
  isStopped: boolean
  /** ISO-like label shown in the stopped stamp. */
  stoppedAt: string
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

export const runState: RunState = {
  isStopped: false,
  stoppedAt: "heute, 08:17",
}

export const GROUPS: RequirementGroup[] = [
  "Fördervoraussetzungen",
  "Pflichtfelder des Beta-Profils",
  "Budget-Prüfung",
  "Passung & Lücken",
]

export const requirements: Requirement[] = [
  // ── Fördervoraussetzungen (6 rows) ─────────────────────────────────────
  {
    id: "r01",
    group: "Fördervoraussetzungen",
    title: "Innovationscharakter nachgewiesen",
    reason: "Das Vorhaben zeigt nachweisbar technologische Neuheit gegenüber dem Stand der Technik.",
    detail:
      "Innosuisse verlangt, dass das Vorhaben gegenüber dem internationalen Stand der Technik eine klare Neuheit aufweist. Die eingereichten Unterlagen belegen dies durch Verweise auf zwei Patentanalysen und einen Marktvergleich.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Innosuisse Leitfaden 2024, S. 8",
      evidenceCardId: "e1",
    },
  },
  {
    id: "r02",
    group: "Fördervoraussetzungen",
    title: "Schweizer Forschungspartner eingebunden",
    reason: "Ein anerkannter Schweizer Forschungspartner ist im Antrag korrekt benannt.",
    detail:
      "Als Forschungspartner ist die ETH Zürich aufgeführt. Das System hat geprüft, dass die Institution auf der offiziellen Liste anerkannter Schweizer Forschungsinstitutionen steht.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Partnerliste Innosuisse 2024, S. 3",
      evidenceCardId: "e2",
    },
    humanCheck: {
      name: "Anna Keller",
      timestamp: "heute, 10:15",
    },
  },
  {
    id: "r03",
    group: "Fördervoraussetzungen",
    title: "Umsetzungspartner mit CH-Domizil",
    reason: "Der Umsetzungspartner hat seinen rechtlichen Sitz in der Schweiz.",
    detail:
      "Laut den hochgeladenen Unterlagen ist das Unternehmen im Handelsregister des Kantons Zürich eingetragen. Adresse und UID-Nummer wurden verifiziert.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Handelsregisterauszug, S. 1",
      evidenceCardId: "e3",
    },
  },
  {
    id: "r04",
    group: "Fördervoraussetzungen",
    title: "Keine laufende Doppelförderung",
    reason: "Es wurde kein Hinweis auf eine parallele Förderung desselben Vorhabens gefunden.",
    detail:
      "Die Analyse hat die beschriebenen Projektziele mit bekannten laufenden Projekten verglichen. Es wurde keine inhaltliche Überschneidung gefunden, die auf Doppelförderung hinweisen würde.",
    machineStatus: "partial",
    evidence: {
      label: "Beleg: Eigendeklaration, S. 2",
      evidenceCardId: "e4",
    },
    override: {
      byName: "Tobias Frei",
      newStatus: "partial",
      comment: "Ähnliches Projekt läuft bei SNF — kein direktes Overlap, aber zu erwähnen.",
      timestamp: "gestern, 14:32",
    },
  },
  {
    id: "r05",
    group: "Fördervoraussetzungen",
    title: "Wirtschaftliche Verwertung geplant",
    reason: "Ein konkreter Verwertungsplan mit Markt- und Produktionsschritten liegt vor.",
    detail:
      "Der Antrag enthält eine Roadmap zur wirtschaftlichen Verwertung mit drei Phasen. Der erste Markttest ist für Q4 2026 geplant.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Verwertungsplan, S. 5",
      evidenceCardId: "e5",
    },
  },
  {
    id: "r06",
    group: "Fördervoraussetzungen",
    title: "Datenschutz-Folgenabschätzung dokumentiert",
    reason: "Eine DSFA ist erforderlich, da personenbezogene Daten verarbeitet werden.",
    detail:
      "Die hochgeladenen Unterlagen enthalten keine Datenschutz-Folgenabschätzung. Da das System personenbezogene Trainingsdaten verarbeitet, ist eine DSFA nach Art. 35 DSGVO obligatorisch.",
    machineStatus: "open",
    evidence: null,
  },

  // ── Pflichtfelder des Beta-Profils (5 rows) ────────────────────────────
  {
    id: "r07",
    group: "Pflichtfelder des Beta-Profils",
    title: "Projekttitel ausgefüllt",
    reason: "Ein beschreibender Projekttitel ist vorhanden.",
    detail:
      "Das Feld «Projekttitel» ist ausgefüllt und enthält eine beschreibende Bezeichnung mit weniger als 120 Zeichen.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Intake-Formular, Feld 1",
      evidenceCardId: "e6",
    },
  },
  {
    id: "r08",
    group: "Pflichtfelder des Beta-Profils",
    title: "Projektbeschreibung (mind. 300 Zeichen)",
    reason: "Die Beschreibung ist vollständig und überschreitet das Mindestzeichenlimit.",
    detail:
      "Die Projektidee umfasst 847 Zeichen und beschreibt Hintergrund, Ziel und Methodik in verständlicher Weise.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Intake-Formular, Feld 2",
      evidenceCardId: "e7",
    },
    humanCheck: {
      name: "Anna Keller",
      timestamp: "heute, 09:42",
    },
  },
  {
    id: "r09",
    group: "Pflichtfelder des Beta-Profils",
    title: "Vertraulichkeitsstufe gesetzt",
    reason: "Die Vertraulichkeitsstufe wurde im Intake-Formular gewählt.",
    detail:
      "Die Stufe «Intern» wurde gewählt. Damit sind externe KI-Dienste nur mit manueller Bestätigung erlaubt.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Intake-Formular, Feld 5",
      evidenceCardId: "e8",
    },
  },
  {
    id: "r10",
    group: "Pflichtfelder des Beta-Profils",
    title: "Mindestens ein Partner erfasst",
    reason: "Es ist mindestens ein Forschungs- oder Umsetzungspartner angegeben.",
    detail:
      "Zwei Partner wurden erfasst: ETH Zürich (Forschungspartner) und Müller AG (Umsetzungspartner).",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Intake-Formular, Abschnitt Partner",
      evidenceCardId: "e9",
    },
  },
  {
    id: "r11",
    group: "Pflichtfelder des Beta-Profils",
    title: "Innovationsfeld angegeben",
    reason: "Das Innovationsfeld wurde im Intake-Formular benannt.",
    detail:
      "Als Innovationsfeld wurde «Nachhaltige Materialien» angegeben. Das Feld ist ein Pflichtfeld im Beta-Profil.",
    machineStatus: "partial",
    evidence: {
      label: "Beleg: Intake-Formular, Feld 3",
      evidenceCardId: "e10",
    },
  },

  // ── Budget-Prüfung (4 rows) ────────────────────────────────────────────
  {
    id: "r12",
    group: "Budget-Prüfung",
    title: "Gesamtbudget im zulässigen Rahmen",
    reason: "Das beantragte Budget liegt innerhalb der maximalen Fördersumme.",
    detail:
      "Das beantragte Gesamtbudget liegt im für dieses Profil zulässigen Bereich. Eine genaue Budgetüberprüfung erfolgt durch Innosuisse im formalen Verfahren.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Budgetübersicht, S. 1",
      evidenceCardId: "e11",
    },
  },
  {
    id: "r13",
    group: "Budget-Prüfung",
    title: "Eigenanteil des Umsetzungspartners ausgewiesen",
    reason: "Der geforderte Eigenanteil ist dokumentiert und entspricht dem Mindestsatz.",
    detail:
      "Der Eigenanteil des Umsetzungspartners ist im Finanzplan ausgewiesen und entspricht mindestens dem geforderten Mindestsatz gemäss Innosuisse-Richtlinien.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Finanzplan, S. 2",
      evidenceCardId: "e12",
    },
  },
  {
    id: "r14",
    group: "Budget-Prüfung",
    title: "Reisekosten plausibel",
    reason: "Die angegebenen Reisekosten erscheinen im Verhältnis zum Projektumfang plausibel.",
    detail:
      "Die Reisekosten betragen weniger als 5 % des Gesamtbudgets. Die geplanten Reiseziele sind im Projektplan beschrieben.",
    machineStatus: "partial",
    evidence: null,
  },
  {
    id: "r15",
    group: "Budget-Prüfung",
    title: "Keine doppelt erfassten Kostenpositionen",
    reason: "Es wurden keine Positionen gefunden, die in mehreren Kategorien doppelt budgetiert sind.",
    detail:
      "Eine automatische Prüfung der Budgetzeilen hat keine offensichtlichen Doppelzählungen gefunden.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Budgetübersicht, S. 3",
      evidenceCardId: "e1",
    },
  },

  // ── Passung & Lücken (4 rows) ──────────────────────────────────────────
  {
    id: "r16",
    group: "Passung & Lücken",
    title: "Passung zum Förderschwerpunkt",
    reason: "Das Vorhaben passt zum aktuellen Förderschwerpunkt «Digitalisierung & KI».",
    detail:
      "Die Analyse hat das Vorhaben mit den aktuell ausgeschriebenen Innosuisse-Schwerpunktthemen abgeglichen. Das Thema KI-gestützte Materialentwicklung fällt in den Bereich «Digitalisierung & KI».",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Ausschreibung Innosuisse 2024, S. 4",
      evidenceCardId: "e2",
    },
  },
  {
    id: "r17",
    group: "Passung & Lücken",
    title: "Risikobewertung vorhanden",
    reason: "Eine Risikoanalyse ist Bestandteil der eingereichten Unterlagen.",
    detail:
      "Der Antrag enthält ein Kapitel zur Risikoanalyse mit vier identifizierten Risiken und entsprechenden Massnahmen.",
    machineStatus: "verified",
    evidence: {
      label: "Beleg: Risikokapitel, S. 9",
      evidenceCardId: "e3",
    },
  },
  {
    id: "r18",
    group: "Passung & Lücken",
    title: "Nachhaltigkeitsaspekte adressiert",
    reason: "Ökologische und soziale Aspekte werden im Antrag explizit erwähnt.",
    detail:
      "Der Antrag enthält einen Abschnitt zu ökologischen Auswirkungen. Soziale Aspekte werden nur am Rande erwähnt — eine Vertiefung wird empfohlen.",
    machineStatus: "partial",
    evidence: {
      label: "Beleg: Nachhaltigkeitsabschnitt, S. 11",
      evidenceCardId: "e4",
    },
  },
  {
    id: "r19",
    group: "Passung & Lücken",
    title: "Verwertungsrechte geregelt",
    reason: "Keine Regelung zu IP-Rechten zwischen den Partnern gefunden.",
    detail:
      "In den hochgeladenen Unterlagen fehlt ein Abschnitt zur Regelung der Verwertungsrechte zwischen Forschungs- und Umsetzungspartner. Innosuisse empfiehlt eine schriftliche Vereinbarung.",
    machineStatus: "open",
    evidence: null,
  },
]
