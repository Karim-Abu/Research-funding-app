export type LiveCostStatus = "priced" | "partial" | "unknown_price" | "not_applicable"

export interface LiveUsageCost {
  status: LiveCostStatus
  usd?: number | null
  chf_reference?: number | null
  known_usd: number
  known_chf_reference: number
  unpriced_call_count: number
}

export interface LiveCostExecution {
  id: string
  role_label: string
  role_id?: string | null
  provider?: string | null
  model?: string | null
  status: string
  input_tokens: number
  cached_input_tokens: number
  cache_write_input_tokens: number
  output_tokens: number
  latency_ms?: number | null
  cost: LiveUsageCost
  price_version?: string | null
}

export interface LiveCostRun {
  id: string
  started_at: string
  ended_at?: string | null
  status: string
  stop_reason?: string | null
  processing_mode: string
  user: string
  max_cost_chf?: number | null
  input_tokens: number
  cached_input_tokens: number
  cache_write_input_tokens: number
  output_tokens: number
  llm_calls: number
  web_calls: number
  cost: LiveUsageCost
  executions: LiveCostExecution[]
}

export interface ProjectCostViewDto {
  project_id: string
  billing_currency: "USD"
  chf_reference_source: string
  chf_reference_rate: number
  chf_reference_as_of: string
  web_research_calls?: number
  runs: LiveCostRun[]
}

export async function getProjectCosts(projectId: string): Promise<ProjectCostViewDto> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/costs`, {
    cache: "no-store",
  })
  if (!response.ok) throw new Error("costs_load_failed")
  return response.json() as Promise<ProjectCostViewDto>
}
