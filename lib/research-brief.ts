import { getCsrfToken } from "./session"

export type ResearchModule =
  | "market_growth"
  | "competition_alternatives"
  | "customer_problem"
  | "state_of_the_art"
  | "swiss_research_partners"

export const RESEARCH_MODULE_LABELS: Record<ResearchModule, string> = {
  market_growth: "Markt & Wachstum",
  competition_alternatives: "Wettbewerb & Alternativen",
  customer_problem: "Kundenproblem & Bedarf",
  state_of_the_art: "State of the Art",
  swiss_research_partners: "Mögliche Schweizer Forschungspartner",
}

export interface ResearchBriefInput {
  application_domain: string
  technology_class: string
  target_customer_segments: string[]
  region: string
  competence_needs: string[]
  modules: ResearchModule[]
}

export interface ResearchBriefDto extends ResearchBriefInput {
  research_brief_id: string
  version: number
  status: "draft" | "approved" | "superseded"
  approved_at?: string | null
}

export interface ResearchQueryDto {
  approval_id: string
  research_brief_id: string
  module: ResearchModule
  planner_purpose: string
  query_text: string
  firewall_decision: string
  risk_label: "low" | "medium" | "high"
  redaction_summary: Array<{ category?: string; label?: string; count?: number }>
  status: "pending" | "approved" | "rejected" | "expired" | "used"
  task_id?: string | null
  task_status?: string | null
  execution_mode?: "fake_demo" | "live" | null
}

export interface ResearchResultDto {
  result_id: string
  task_id: string
  module?: ResearchModule | null
  planner_purpose?: string | null
  title: string
  source_url: string
  final_url?: string | null
  domain: string
  snippet?: string | null
  retrieved_at: string
  relevance_reason: string
  status: "candidate" | "imported" | "rejected" | "failed"
  execution_mode?: "fake_demo" | "live" | null
  source_document_id?: string | null
  source_locations: Array<{
    source_id: string
    source_version_id: string
    page?: number | null
    section?: string | null
    excerpt: string
  }>
  partner_candidate?: {
    organization_or_group: string
    location?: string | null
    location_status: "verified" | "unverified"
    expertise_keywords: string[]
    possible_project_role: string
    why_potentially_relevant: string
    evidence_url: string
    status: "candidate_not_eligibility_confirmed"
  } | null
}

export interface ResearchWorkspaceDto {
  brief: { latest?: ResearchBriefDto | null; active_approved?: ResearchBriefDto | null }
  queries: ResearchQueryDto[]
  results: ResearchResultDto[]
  provider_mode: "fake_demo" | "live" | "unavailable"
}

function headers(): Record<string, string> {
  const csrf = getCsrfToken()
  return { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) }
}

async function checked<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = "Die Rechercheaktion konnte nicht gespeichert werden."
    try {
      const problem = await response.json()
      message = problem.detail ?? message
    } catch {}
    throw new Error(message)
  }
  return (await response.json()) as T
}

export function getResearchWorkspace(projectId: string): Promise<ResearchWorkspaceDto> {
  return fetch(`/api/projects/${encodeURIComponent(projectId)}/research-workspace`).then(
    (response) => checked<ResearchWorkspaceDto>(response)
  )
}

export function suggestResearchBrief(projectId: string): Promise<ResearchBriefDto> {
  return fetch(`/api/projects/${encodeURIComponent(projectId)}/research-brief/suggest`, {
    method: "POST", headers: headers(),
  }).then((response) => checked<ResearchBriefDto>(response))
}

export function saveResearchBrief(
  projectId: string, brief: ResearchBriefInput
): Promise<ResearchBriefDto> {
  return fetch(`/api/projects/${encodeURIComponent(projectId)}/research-brief`, {
    method: "PUT", headers: headers(), body: JSON.stringify(brief),
  }).then((response) => checked<ResearchBriefDto>(response))
}

export function approveResearchBrief(briefId: string): Promise<ResearchBriefDto> {
  return fetch(`/api/research-briefs/${encodeURIComponent(briefId)}/approve`, {
    method: "POST", headers: headers(),
  }).then((response) => checked<ResearchBriefDto>(response))
}

export function planResearchQueries(briefId: string): Promise<{
  brief: ResearchBriefDto
  queries: ResearchQueryDto[]
  provider_mode: ResearchWorkspaceDto["provider_mode"]
}> {
  return fetch(`/api/research-briefs/${encodeURIComponent(briefId)}/queries/plan`, {
    method: "POST", headers: headers(),
  }).then((response) => checked<{
    brief: ResearchBriefDto
    queries: ResearchQueryDto[]
    provider_mode: ResearchWorkspaceDto["provider_mode"]
  }>(response))
}

export function previewBriefQuery(
  briefId: string,
  query: Pick<ResearchQueryDto, "module" | "planner_purpose" | "query_text" | "approval_id">
): Promise<ResearchQueryDto> {
  return fetch(`/api/research-briefs/${encodeURIComponent(briefId)}/queries/preview`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      module: query.module,
      planner_purpose: query.planner_purpose,
      query_text: query.query_text,
      supersedes_approval_id: query.approval_id,
    }),
  }).then((response) => checked<ResearchQueryDto>(response))
}

export function runResearchBrief(
  briefId: string, approvalIds: string[]
): Promise<{ task_ids: string[]; result_count: number; execution_mode: string }> {
  return fetch(`/api/research-briefs/${encodeURIComponent(briefId)}/run`, {
    method: "POST", headers: headers(), body: JSON.stringify({ approval_ids: approvalIds }),
  }).then((response) => checked<{
    task_ids: string[]
    result_count: number
    execution_mode: string
  }>(response))
}
