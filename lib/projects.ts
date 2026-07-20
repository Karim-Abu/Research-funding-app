// Projects client for the live slice (same-origin BFF /api/projects). Mock mode
// returns local stand-ins so the existing dashboard/intake keep working.

import { isLive } from "./app-mode"
import {
  dataClassificationFromFlat,
  type DataClassification,
} from "./data-classification"
import { getCsrfToken } from "./session"
import type {
  DashboardProject,
  IntakeFormData,
  NextAction,
  ProjectCardStatus,
  WarningBadge,
} from "./types"

export type ProjectStatus = "draft" | "active" | "archived"

export interface ProjectDto {
  project_id: string
  workspace_id: string
  title: string
  title_en?: string | null
  start_date?: string | null
  end_date?: string | null
  description: string
  innovation_field?: string | null
  funding_instrument_profile_id: string
  data_classification: DataClassification
  budget_framework_chf?: number | null
  // Structured budget inputs (Slice 1) — edited on Partner & Budget.
  direct_total_project_costs_excluding_overhead?: number | null
  implementation_own_contribution?: number | null
  cash_contribution?: number | null
  total_requested_funding?: number | null
  total_requested_funding_including_overhead?: number | null
  budget_exception_basis?: string | null
  duration_months?: number | null
  duration_status: "derived" | "not_derivable" | "review_required"
  duration_reason_code:
    | "duration_derived"
    | "duration_dates_missing"
    | "duration_boundary_conflict"
  primary_application_source_id?: string | null
  primary_application_status: "configured" | "not_configured" | "needs_selection"
  status: ProjectStatus
  created_at: string
  updated_at: string
  active_run_id?: string | null
  workflow_summary?: WorkflowSummaryDto | null
}

/** PATCH /projects/{id} payload — structured budget fields (additive). */
export interface ProjectBudgetPatch {
  direct_total_project_costs_excluding_overhead?: number | null
  implementation_own_contribution?: number | null
  cash_contribution?: number | null
  total_requested_funding?: number | null
  total_requested_funding_including_overhead?: number | null
  budget_exception_basis?: string | null
}

export interface ProjectMetadataPatch extends ProjectBudgetPatch {
  title?: string
  title_en?: string | null
  start_date?: string | null
  end_date?: string | null
}

interface ProjectListDto {
  items: ProjectDto[]
  next_cursor?: string | null
}

export type WorkflowNextAction = NextAction | "view_progress"

export interface WorkflowSummaryDto {
  bearbeitungsstand_percent: number
  current_step: number
  current_step_label?: string | null
  next_action: WorkflowNextAction
  warning_badge?: "run_stopped" | null
  latest_run_id?: string | null
}

const WARNING_MAP: Partial<
  Record<NonNullable<WorkflowSummaryDto["warning_badge"]>, WarningBadge>
> = {
  run_stopped: "durchlauf_gestoppt",
}

function toNextAction(action: WorkflowNextAction): NextAction {
  return action === "view_progress" ? "resume_analysis" : action
}

// Single beta funding instrument profile (resolved from the contract registry).
export const BETA_FUNDING_PROFILE_ID =
  "innosuisse_innovation_project_with_implementation_partner"

function idempotencyKey(): string {
  // 32 hex chars — satisfies the contract Idempotency-Key length (8..128).
  return crypto.randomUUID().replace(/-/g, "")
}

function intakeToCreatePayload(intake: IntakeFormData) {
  const flat = intake.vertraulichkeit
  if (!flat) throw new Error("confidentiality_missing")
  return {
    title: intake.titel,
    description: intake.projektidee,
    innovation_field: intake.innovationsfeld || null,
    funding_instrument_profile_id: BETA_FUNDING_PROFILE_ID,
    data_classification: dataClassificationFromFlat(flat),
    // Budget wird nicht mehr im Intake erfasst — Erfassungsort ist
    // ausschliesslich «Partner & Budget» (PATCH /projects).
    budget_framework_chf: null,
  }
}

export async function listProjects(): Promise<ProjectDto[]> {
  if (!isLive("projects")) return []
  const res = await fetch("/api/projects", { method: "GET" })
  if (!res.ok) throw new Error("projects_load_failed")
  const data = (await res.json()) as ProjectListDto
  return data.items
}

export async function createProjectFromIntake(
  intake: IntakeFormData
): Promise<ProjectDto> {
  const payload = intakeToCreatePayload(intake)
  if (!isLive("projects")) {
    const now = new Date().toISOString()
    return {
      project_id: `mock-${Date.now()}`,
      workspace_id: "mock-workspace",
      status: "draft",
      created_at: now,
      updated_at: now,
      active_run_id: null,
      duration_status: "not_derivable",
      duration_reason_code: "duration_dates_missing",
      primary_application_status: "not_configured",
      ...payload,
    }
  }
  const csrf = getCsrfToken()
  const res = await fetch("/api/projects", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey(),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error("project_create_failed")
  return (await res.json()) as ProjectDto
}

export async function getProject(projectId: string): Promise<ProjectDto> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`)
  if (!res.ok) throw new Error("project_load_failed")
  return (await res.json()) as ProjectDto
}

export async function patchProject(
  projectId: string,
  patch: ProjectMetadataPatch
): Promise<ProjectDto> {
  const csrf = getCsrfToken()
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error("project_update_failed")
  return (await res.json()) as ProjectDto
}

export async function selectPrimaryApplication(
  projectId: string,
  sourceId: string,
  expectedPrimarySourceId: string | null
): Promise<ProjectDto> {
  const csrf = getCsrfToken()
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/primary-application`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      },
      body: JSON.stringify({
        source_id: sourceId,
        expected_primary_source_id: expectedPrimarySourceId,
      }),
    }
  )
  if (!res.ok) throw new Error("primary_application_update_failed")
  return (await res.json()) as ProjectDto
}

/** Archiviert ein Projekt (status="archived"). Das Projekt wird danach aus der
 *  Übersicht ausgeblendet, bleibt aber in der Datenbank (umkehrbar). Nutzt den
 *  bestehenden PATCH-Endpunkt; kein Idempotency-Key (wie andere Mutationen ohne
 *  Erzeugung). Im Mock-Modus ein No-Op — die Übersicht entfernt die Karte lokal. */
export async function archiveProject(projectId: string): Promise<void> {
  if (!isLive("projects")) return
  const csrf = getCsrfToken()
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: JSON.stringify({ status: "archived" }),
  })
  if (!res.ok) throw new Error("project_archive_failed")
}

// --- Budget-Vorprüfung (read-only, run-unabhängig) ---------------------------
// Rechnung und Schwellen kommen ausschliesslich aus dem Backend-Rule-Kern;
// das Frontend zeigt nur an. Status-Vokabular ist EIGENSTÄNDIG (kein
// Requirement-Status): fulfilled | review | blocker | missing.
export type BudgetPrecheckStatus = "fulfilled" | "review" | "blocker" | "missing"

export interface BudgetPrecheckFiguresDto {
  direct_costs_chf: number | null
  own_contribution_chf: number | null
  cash_contribution_chf: number | null
  requested_funding_chf: number | null
  implementation_contribution_chf: number | null
  implementation_share_percent: number | null
  cash_share_percent: number | null
  funding_share_percent: number | null
  exception_claimed: boolean
}

export interface BudgetPrecheckCheckDto {
  rule_id: string
  requirement_id: string | null
  /** Deutscher Anzeigetitel — die UI zeigt nie rohe Regel-IDs. */
  title: string
  status: BudgetPrecheckStatus
  reason: string
  observed: Record<string, unknown>
  condition: Record<string, unknown>
  severity: string
  source_ref: string | null
  source_version: string | null
  last_checked: string | null
  rule_version: string
}

export interface BudgetPrecheckDto {
  figures: BudgetPrecheckFiguresDto
  checks: BudgetPrecheckCheckDto[]
}

export async function getBudgetPrecheck(
  projectId: string
): Promise<BudgetPrecheckDto> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/budget/precheck`
  )
  if (!res.ok) throw new Error("budget_precheck_failed")
  return (await res.json()) as BudgetPrecheckDto
}

// The backend workflow_summary keeps its own 8-step numbering (1 Intake,
// 2 Quellen, 3 Anforderungen, 4 Evidenz, 5 Entwurf, 6 Review, 7 Abschluss,
// 8 Export). The UI uses the 6-step catalog from lib/workflow.ts
// (1 Projekt & Unterlagen, 2 Partner & Budget, 3 Analyse & Recherche,
// 4 Antragsentwurf, 5 Qualitätsprüfung, 6 Innolink-Übernahme) — backend steps
// translate explicitly here, never silently. Anforderungen (3) und Evidenz (4)
// sind beide Teil von «Analyse & Recherche»; «Abschluss» (7) gehört zur
// Qualitätsprüfung. Der Partner-Schritt hat kein Backend-Pendant.
const BACKEND_STEP_TO_UI_STEP: Record<number, number> = {
  1: 1,
  2: 1,
  3: 3,
  4: 3,
  5: 4,
  6: 5,
  7: 5,
  8: 6,
}

function toUiStep(backendStep: number): number {
  return BACKEND_STEP_TO_UI_STEP[backendStep] ?? backendStep
}

/** Derive the high-level card status from the available workflow signals. */
function toCardStatus(summary?: WorkflowSummaryDto | null): ProjectCardStatus {
  if (summary?.warning_badge === "run_stopped") return "blockiert"
  if (summary?.next_action === "approve_review") return "review_offen"
  return "in_bearbeitung"
}

/** Map a contract project onto the dashboard card shape (frontend-only, no API change). */
export function toDashboardCard(project: ProjectDto): DashboardProject {
  const summary = project.workflow_summary
  return {
    id: project.project_id,
    title: project.title,
    profileLabel: "Innosuisse Beta-Profil",
    fundingProgram: "Innosuisse",
    applicationType: "Innovationsprojekt",
    deadline: "Frist: offen",
    deadlineIso: null,
    progressPercent: summary?.bearbeitungsstand_percent ?? 0,
    currentStep: summary ? toUiStep(summary.current_step) : 1,
    cardStatus: toCardStatus(summary),
    lastEditedLabel: `Angelegt: ${new Date(
      project.created_at
    ).toLocaleDateString("de-CH")}`,
    nextAction: toNextAction(summary?.next_action ?? "upload_sources"),
    warningBadge: summary?.warning_badge
      ? WARNING_MAP[summary.warning_badge]
      : undefined,
    analysisRunning: summary?.next_action === "view_progress",
    isDemo: project.title.trim().endsWith("(Demo)"),
    people: [],
    latestRunId: summary?.latest_run_id ?? null,
  }
}

/** R1.3 — merge the canonical blocker count into a card. Cards with open
 *  blockers surface as «Blockiert» so the dashboard no longer hides
 *  content blockers behind «In Bearbeitung». */
export function withCanonicalStatus(
  card: DashboardProject,
  blockerCount: number
): DashboardProject {
  return {
    ...card,
    openBlockerCount: blockerCount,
    cardStatus: blockerCount > 0 ? "blockiert" : card.cardStatus,
  }
}
