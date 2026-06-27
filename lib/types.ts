// Shared domain types for the Proposal-Unterstützung prototype.
// All user-facing strings live in mock-data / components (German); types are English.

export type Role = "lead_admin" | "member"

export interface User {
  name: string
  displayRole: string
  role: Role
}

export interface Project {
  id: string
  title: string
}

// Workflow stepper -------------------------------------------------------

export type StepStatus = "done" | "current" | "upcoming"

export interface WorkflowStep {
  /** 1-based step number */
  step: number
  label: string
  /** Shorter version used in the full stepper strip when the label would truncate. */
  shortLabel?: string
  subLabel: string
  /** Route the step links to (8 steps map onto 6 screens). */
  href: string
}

// Machine status vs human confirmation ----------------------------------

/** Machine-evaluated status — always rendered as a colored Badge. */
export type MachineStatus = "verified" | "partial" | "open" | "blocker"

/** Human confirmation — always rendered as a teal check with name + time. */
export interface HumanCheck {
  name: string
  timestamp: string
}

// Confidentiality / data class ------------------------------------------

export type DataClass = "public" | "internal" | "confidential"

// Beta-Policy (zentral — UI und API nutzen dieselben Regeln):
// public -> Cloud-LLM und validierte öffentliche Webrecherche erlaubt;
// internal/confidential bleiben ohne direkte externe Dienste im UI.

export function isCloudAllowed(dataClass: DataClass): boolean {
  return dataClass === "public"
}

export function isWebAllowed(dataClass: DataClass): boolean {
  return dataClass === "public"
}

export const DATA_CLASS_LABELS: Record<DataClass, string> = {
  public: "Öffentlich",
  internal: "Intern",
  confidential: "Vertraulich",
}

// Restriktivität aufsteigend — Index = Rang.
const DATA_CLASS_ORDER: DataClass[] = [
  "public",
  "internal",
  "confidential",
]

/**
 * Effektive Datenklasse eines Laufs = restriktivste aus Projekt + Quellen.
 * Eine weniger restriktive Kombination darf nie Cloud-Aufrufe freischalten.
 */
export function mostRestrictiveDataClass(classes: DataClass[]): DataClass {
  let result: DataClass = "public"
  for (const dc of classes) {
    if (DATA_CLASS_ORDER.indexOf(dc) > DATA_CLASS_ORDER.indexOf(result)) {
      result = dc
    }
  }
  return result
}

// Service availability (booleans only — never expose provider info) ------

export interface ServiceAvailability {
  ki: boolean
  web: boolean
}

// Dashboard project cards -----------------------------------------------

/** Typed next-action union — maps to German button labels in the card. */
export type NextAction =
  | "upload_sources"
  | "start_analysis"
  | "review_analysis"
  | "continue_draft"
  | "approve_review"
  | "create_export"
  | "resume_analysis"

/** Optional warning badge — at most one per card. */
export type WarningBadge = "durchlauf_gestoppt" | "freigabe_offen"

export interface DashboardProject {
  id: string
  title: string
  profileLabel: string
  deadline: string
  progressPercent: number
  /** 1-based current step number (1–8). */
  currentStep: number
  lastEditedLabel: string
  nextAction: NextAction
  warningBadge?: WarningBadge
  /** When true, the card shows a spinner + "Analyse läuft…" and the next-action button becomes "Fortschritt ansehen". */
  analysisRunning?: boolean
  isDemo?: boolean
}


// Intake form -------------------------------------------------------

export interface IntakePartner {
  id: string
  name: string
  type: "Forschungspartner" | "Umsetzungspartner"
}

export interface IntakeFormData {
  titel: string
  projektidee: string
  innovationsfeld: string
  budgetrahmen: string
  vertraulichkeit: DataClass | ""
  partner: IntakePartner[]
}

export interface AnalyseSettings {
  ki: boolean
  web: boolean
  /** Nur vorbereitete/hochgeladene Quellen verwenden (keine Aussage über lokale LLMs). */
  localSourcesOnly: boolean
  costLimit: number
  model: "auto" | "claude" | "openai"
  maxTextLength?: number
  maxSources?: number
  maxWebPages?: number
}
