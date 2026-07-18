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
  /** Optional user-facing status line for the sidebar card (view model). */
  statusLabel?: string
}

// Workflow stepper: Katalog, Schrittstatus und Ableitung leben in
// lib/workflow.ts (6-Schritte-Modell) — hier keine Stepper-Typen mehr.

// Machine status vs human confirmation ----------------------------------

/** Machine-evaluated status — always rendered as a colored Badge. */
export type MachineStatus = "verified" | "partial" | "open" | "blocker"

// Two legitimate label domains share the MachineStatus type. Centralised here so
// each domain has a single source of truth (no per-screen duplicate maps).
//
// Default / evidence verification wording (Evidenz, Belege).
export const MACHINE_STATUS_LABELS: Record<MachineStatus, string> = {
  verified: "Verifiziert",
  partial: "Prüfen",
  open: "Offen",
  blocker: "Blockierend",
}

// Requirement-fulfilment wording (Anforderungen / Fördervoraussetzungen).
export const REQUIREMENT_STATUS_LABELS: Record<MachineStatus, string> = {
  verified: "Erfüllt",
  partial: "Teilweise erfüllt",
  open: "Offen",
  blocker: "Blockierend",
}

/** Human confirmation — always rendered as a teal check with name + time. */
export interface HumanCheck {
  name: string
  timestamp: string
}

// Confidentiality / data class ------------------------------------------

// R4.1: vier wählbare Stufen — "nda" (D3) ist NDA-/rechtlich gesperrtes Material.
// Unknown ist KEIN wählbarer Wert; fehlende Einstufung bleibt fail-closed.
export type DataClass = "public" | "internal" | "confidential" | "nda"

// Beta-Policy (zentral — UI und API nutzen dieselben Regeln):
// public -> Cloud-LLM und validierte öffentliche Webrecherche erlaubt;
// internal/confidential/nda bleiben ohne direkte externe Dienste im UI.
//
// WICHTIG (R4.1): Diese Helper sind reine UI-Gates — sie dürfen Bedienelemente
// nur DEAKTIVIEREN, nie etwas freischalten. Die finale KI-Entscheidung für
// D1/D2 trifft die Backend-ProviderPolicy (R4.3) zusammen mit data_policy /
// policy_matrix; kontrollierte KI läuft nie allein über diese Booleans.

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
  nda: "NDA / gesperrt",
}

// Restriktivität aufsteigend — Index = Rang.
const DATA_CLASS_ORDER: DataClass[] = [
  "public",
  "internal",
  "confidential",
  "nda",
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
  // "live_unavailable": Live konfiguriert, Provider nicht verfügbar — nie
  // stiller Abstieg auf den Demo-Generator (Ebene E).
  generationMode?: "unavailable" | "fake_demo" | "real_eval" | "live_unavailable"
  unavailableReason?: string | null
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

/** High-level project status surfaced as the primary card badge + summary counts. */
export type ProjectCardStatus =
  | "in_bearbeitung"
  | "review_offen"
  | "blockiert"
  | "eingereicht"

export const PROJECT_STATUS_LABELS: Record<ProjectCardStatus, string> = {
  in_bearbeitung: "In Bearbeitung",
  review_offen: "Prüfung offen",
  blockiert: "Blockiert",
  eingereicht: "Eingereicht",
}

/** A person involved in a project — rendered as an avatar in the card stack. */
export interface ProjectPerson {
  name: string
  /** 1–2 letter monogram for the avatar fallback. */
  initials: string
}

export interface DashboardProject {
  id: string
  title: string
  profileLabel: string
  deadline: string
  progressPercent: number
  /** 1-based current step number (1–6, lib/workflow.ts). */
  currentStep: number
  lastEditedLabel: string
  nextAction: NextAction
  warningBadge?: WarningBadge
  /** When true, the card shows a spinner while keeping the primary action stable. */
  analysisRunning?: boolean
  isDemo?: boolean
  /** Funding programme, e.g. "Innosuisse". Frontend fallback when absent. */
  fundingProgram?: string
  /** Application type, e.g. "Innovationsprojekt". Frontend fallback when absent. */
  applicationType?: string
  /** High-level status badge. Derived in the live mapping when absent. */
  cardStatus?: ProjectCardStatus
  /** ISO date of the submission deadline — used for the "nächste Frist" summary. */
  deadlineIso?: string | null
  /** People involved, rendered as an avatar stack. */
  people?: ProjectPerson[]
  /** Latest analysis run of the project (live mapping; feeds the canonical status). */
  latestRunId?: string | null
  /** R1.3 — canonical open-blocker count from the ReviewStatusView (lib/status.ts).
   *  null/undefined = not loaded (mock mode or no completed run yet). */
  openBlockerCount?: number | null
}


// Intake form -------------------------------------------------------
// Partner und Budget werden NICHT mehr im Intake erfasst (Schritt 2
// «Partner & Budget» ist der einzige Erfassungsort — keine Doppelerfassung).

export interface IntakeFormData {
  titel: string
  projektidee: string
  innovationsfeld: string
  /** "" = noch nicht klassifiziert (nur Legacy-Einträge; das Formular
   *  startet mit dem restriktiven Default "confidential"). */
  vertraulichkeit: DataClass | ""
}

export interface AnalyseSettings {
  ki: boolean
  web: boolean
  /** Nur vorbereitete/hochgeladene Quellen verwenden (keine Aussage über lokale LLMs). */
  localSourcesOnly: boolean
  costLimit: number
  model: "auto" | "claude" | "openai"
  /** Run-Budget: max. KI-Aufrufe pro Durchlauf (Erweiterte Einstellungen). */
  maxLlmCalls?: number
  /** Run-Budget: max. öffentliche Suchanfragen, wirkt nur bei web=true. */
  maxWebCalls?: number
  /**
   * Cloud-KI für diesen Durchlauf bewusst freigegeben (nur public/synthetic).
   * Mandatory user acknowledgement before a cloud_assisted run (Milestone 9D.2).
   */
  cloudConfirmed?: boolean
  /**
   * Expliziter Live-Lauf (processing_mode=live) mit Live-Bestätigung —
   * gesetzt nur vom Dialog-Intent «Neuen Live-Lauf erstellen».
   */
  liveRun?: boolean
}
