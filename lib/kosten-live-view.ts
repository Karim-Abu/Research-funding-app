import type { KostenRunStatus } from "@/lib/kosten"
import type { LiveCostExecution, LiveCostRun, LiveUsageCost } from "@/lib/kosten-live"

// Presentation mapping for live cost data. Pure functions only: the API
// contract in lib/kosten-live.ts stays untouched, raw backend keys never
// reach the UI, and honest pricing semantics are preserved (incomplete sums
// are never presented as exact).

export interface LiveRunStatusView {
  /** When set, render the shared RunStatusBadge with this status. */
  badge: KostenRunStatus | null
  /** Fallback label for statuses outside the badge's map. */
  label: string | null
  tone: "gray" | "orange"
}

export function liveRunStatusView(status: string, stopReason?: string | null): LiveRunStatusView {
  switch (status) {
    case "completed":
      return { badge: "completed", label: null, tone: "gray" }
    case "failed":
      return { badge: "failed", label: null, tone: "gray" }
    case "cancelled":
      return { badge: "cancelled", label: null, tone: "gray" }
    case "stopped":
      if (stopReason === "cost_budget_exhausted") return { badge: "stopped_cost", label: null, tone: "orange" }
      if (stopReason === "llm_budget_exhausted") return { badge: null, label: "Gestoppt: Aufruf-Limit erreicht", tone: "orange" }
      return { badge: null, label: "Gestoppt", tone: "orange" }
    case "running":
      return { badge: null, label: "Läuft", tone: "gray" }
    case "created":
      return { badge: null, label: "Noch nicht gestartet", tone: "gray" }
    case "paused_for_review":
      return { badge: null, label: "Wartet auf Prüfung", tone: "orange" }
    default:
      return { badge: null, label: "Status unbekannt", tone: "gray" }
  }
}

const PROVIDER_LABELS: Record<string, string> = {
  openai_direct: "OpenAI (direkt)",
  anthropic_direct: "Anthropic (direkt)",
  openai: "OpenAI",
  anthropic: "Anthropic",
}

export function providerLabel(provider?: string | null): string {
  if (!provider) return "Unbekannter Dienst"
  const known = PROVIDER_LABELS[provider]
  if (known) return known
  return provider
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

export interface PricingSummary {
  /** External calls (executions with billable cost semantics). */
  externalCallCount: number
  /** Backend-authoritative count of calls without a price rule. */
  unpricedCallCount: number
  /** Internal bookkeeping calls without external costs. */
  internalCallCount: number
  fullyPriced: boolean
}

export function summarizePricing(runs: readonly LiveCostRun[]): PricingSummary {
  const executions = runs.flatMap((run) => run.executions)
  const externalRaw = executions.filter((execution) => execution.cost.status !== "not_applicable").length
  const internalCallCount = executions.length - externalRaw
  const unpricedCallCount = runs.reduce((sum, run) => sum + run.cost.unpriced_call_count, 0)
  // The backend count and the execution list could drift; never show "n von m" with n > m.
  const externalCallCount = Math.max(externalRaw, unpricedCallCount)
  return { externalCallCount, unpricedCallCount, internalCallCount, fullyPriced: unpricedCallCount === 0 }
}

export function aggregateLiveCost(runs: readonly LiveCostRun[]): LiveUsageCost {
  const unpriced = runs.reduce((sum, run) => sum + run.cost.unpriced_call_count, 0)
  const knownUsd = runs.reduce((sum, run) => sum + run.cost.known_usd, 0)
  const knownChf = runs.reduce((sum, run) => sum + run.cost.known_chf_reference, 0)
  const externalRuns = runs.filter((run) => run.cost.status !== "not_applicable")
  const allPriced = externalRuns.length > 0 && unpriced === 0 && externalRuns.every((run) => run.cost.status === "priced")
  return {
    status: allPriced ? "priced" : unpriced > 0 && knownUsd > 0 ? "partial" : unpriced > 0 ? "unknown_price" : "not_applicable",
    usd: allPriced ? knownUsd : null,
    chf_reference: allPriced ? knownChf : null,
    known_usd: knownUsd,
    known_chf_reference: knownChf,
    unpriced_call_count: unpriced,
  }
}

export function splitExecutions(executions: readonly LiveCostExecution[]): { external: LiveCostExecution[]; internalCount: number } {
  const external = executions.filter((execution) => execution.cost.status !== "not_applicable")
  return { external, internalCount: executions.length - external.length }
}

export function unpricedBadgeLabel(count: number): string {
  return `${count} Aufruf${count === 1 ? "" : "e"} unbepreist`
}

const ROLE_LABELS: Record<string, string> = {
  A1_FACT_EVIDENCE_ANALYST: "Anforderungsanalyst",
  A2_INNOSUISSE_PROPOSAL_WRITER: "Innovationstext-Assistent",
  A3_INNOSUISSE_CRITICAL_REVIEWER: "Qualitätskoordinator",
  RESEARCH_QUERY_PLANNER: "Marktrecherche-Planer",
  RESEARCH_EVIDENCE_SYNTHESIZER: "Marktrecherche-Assistent",
  EVIDENCE_SUPPORT_VERIFIER: "Evidenzprüfer",
}

export function roleLabel(roleId?: string | null): string {
  if (!roleId) return "KI-Aufruf"
  return ROLE_LABELS[roleId] ?? "KI-Aufruf"
}

export interface RoleGroup {
  key: string
  roleLabel: string
  models: string[]
  callCount: number
  inputTokens: number
  outputTokens: number
  cost: LiveUsageCost
}

// Aggregate the external calls of one run by their system role, so a role that
// ran many times shows once (label + models + summed tokens/cost) instead of
// repeating the model name per call. Internal (not_applicable) rows are handled
// separately via splitExecutions and are excluded here.
export function groupExecutionsByRole(executions: readonly LiveCostExecution[]): RoleGroup[] {
  const { external } = splitExecutions(executions)
  const order: string[] = []
  const buckets = new Map<string, LiveCostExecution[]>()
  for (const execution of external) {
    const key = execution.role_id ?? "__none__"
    if (!buckets.has(key)) {
      buckets.set(key, [])
      order.push(key)
    }
    buckets.get(key)!.push(execution)
  }
  return order.map((key) => {
    const group = buckets.get(key)!
    const models = [...new Set(group.map((execution) => execution.model).filter((model): model is string => !!model))]
    return {
      key,
      roleLabel: roleLabel(group[0].role_id),
      models,
      callCount: group.length,
      inputTokens: group.reduce((sum, execution) => sum + execution.input_tokens, 0),
      outputTokens: group.reduce((sum, execution) => sum + execution.output_tokens, 0),
      cost: aggregateExecutionCost(group),
    }
  })
}

// Same priced/partial/unknown logic as aggregateLiveCost, but over executions
// (each execution's own cost already carries known_usd / unpriced_call_count).
function aggregateExecutionCost(executions: readonly LiveCostExecution[]): LiveUsageCost {
  const knownUsd = executions.reduce((sum, execution) => sum + execution.cost.known_usd, 0)
  const knownChf = executions.reduce((sum, execution) => sum + execution.cost.known_chf_reference, 0)
  const unpriced = executions.filter((execution) => execution.cost.status !== "priced").length
  const allPriced = executions.length > 0 && unpriced === 0
  return {
    status: allPriced ? "priced" : knownUsd > 0 ? "partial" : "unknown_price",
    usd: allPriced ? knownUsd : null,
    chf_reference: allPriced ? knownChf : null,
    known_usd: knownUsd,
    known_chf_reference: knownChf,
    unpriced_call_count: unpriced,
  }
}
