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
  WarningBadge,
} from "./types"

export type ProjectStatus = "draft" | "active" | "archived"

export interface ProjectDto {
  project_id: string
  workspace_id: string
  title: string
  description: string
  innovation_field?: string | null
  funding_instrument_profile_id: string
  data_classification: DataClassification
  budget_framework_chf?: number | null
  status: ProjectStatus
  created_at: string
  updated_at: string
  active_run_id?: string | null
  workflow_summary?: WorkflowSummaryDto | null
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
  const flat = intake.vertraulichkeit || "public"
  const budget = intake.budgetrahmen.trim()
  return {
    title: intake.titel,
    description: intake.projektidee,
    innovation_field: intake.innovationsfeld || null,
    funding_instrument_profile_id: BETA_FUNDING_PROFILE_ID,
    data_classification: dataClassificationFromFlat(flat),
    budget_framework_chf: budget ? Number(budget.replace(",", ".")) : null,
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

/** Map a contract project onto the existing dashboard card shape (no redesign). */
export function toDashboardCard(project: ProjectDto): DashboardProject {
  const summary = project.workflow_summary
  return {
    id: project.project_id,
    title: project.title,
    profileLabel: "Innosuisse Beta-Profil",
    deadline: "—",
    progressPercent: summary?.bearbeitungsstand_percent ?? 0,
    currentStep: summary?.current_step ?? 1,
    lastEditedLabel: `Angelegt: ${new Date(
      project.created_at
    ).toLocaleDateString("de-CH")}`,
    nextAction: toNextAction(summary?.next_action ?? "upload_sources"),
    warningBadge: summary?.warning_badge
      ? WARNING_MAP[summary.warning_badge]
      : undefined,
    analysisRunning: summary?.next_action === "view_progress",
    isDemo: project.title.trim().endsWith("(Demo)"),
  }
}
