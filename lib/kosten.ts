export type CostStatus =
  | "priced"
  | "estimated"
  | "partial"
  | "unavailable"

export interface CostValue {
  status: CostStatus
  amountChf?: number
}

export type KostenRunStatus =
  | "completed"
  | "stopped_cost"
  | "failed"
  | "cancelled"

export type KostenRunType =
  | "analysis"
  | "section_regenerated"
  | "web_search"

export type ModelExecutionStatus = "completed" | "failed" | "cancelled"

export interface ModelExecutionAttemptViewModel {
  id: string
  provider: string
  requestedModel?: string
  actualModel?: string
  status: ModelExecutionStatus
  retryIndex: number
  latencyMs?: number
  cost?: CostValue
  inputTokens?: number
  outputTokens?: number
}

export interface ModelExecutionViewModel {
  id: string
  roleLabel: string
  provider: string
  model: string
  status?: ModelExecutionStatus
  inputTokens?: number
  outputTokens?: number
  cost?: CostValue
  /** Gemeldete Gesamtlatenz dieser Ausfuehrungsgruppe. */
  latencyMsTotal?: number
  retryCount?: number
  /** Anzahl der in dieser Ausfuehrungsgruppe enthaltenen Aufrufe. */
  callCount?: number
  generationKinds?: string[]
  promptVersions?: string[]
  skillVersions?: string[]
  terminationReasons?: string[]
  attempts?: ModelExecutionAttemptViewModel[]
}

export interface KostenRunViewModel {
  id: string
  startedAt: string
  endedAt?: string
  type: KostenRunType
  user: string
  status: KostenRunStatus
  stopReason?: string
  kiEnabled: boolean
  webEnabled: boolean
  providerLabels: string[]
  modelLabels: string[]
  cost: CostValue
  llmCalls?: number
  webCalls?: number
  inputTokens?: number
  outputTokens?: number
  executions: ModelExecutionViewModel[]
  auditRef?: string
}

export type ServiceTestStatus = "successful" | "failed" | "not_tested"

export interface KostenServiceViewModel {
  id: string
  name: string
  subtitle?: string
  configured: boolean
  lastTestStatus: ServiceTestStatus
  lastTestAt?: string
  availabilityNote?: string
}

export interface KostenUsageLimits {
  projectLimitChf: number
  perRunLimitChf: number
  minPerRunLimitChf: number
  maxPerRunLimitChf: number
}

export type RunFilterStatus = KostenRunStatus | "all"
export type RunFilterType = KostenRunType | "all"
export type RunSort = "date_desc" | "cost_desc" | "duration_desc"

export interface RunFilters {
  query: string
  status: RunFilterStatus
  type: RunFilterType
  providerModel: string
  sort: RunSort
}

export interface KostenOverview {
  totalCost: CostValue
  averageCost: CostValue
  knownCostRuns: number
  averageDurationMs?: number
  knownDurationRuns: number
  mostExpensiveRun?: KostenRunViewModel
  hasIncompleteCosts: boolean
  usagePercent?: number
  remainingBudget: CostValue
}

export interface ProviderModelAggregate {
  id: string
  provider: string
  model: string
  usageCount?: number
  totalCost: CostValue
  averageCost: CostValue
  averageLatencyMs?: number
  latencyCallCount: number
  technicalSuccessRate?: number
  technicalStatusCount: number
}

export const RUN_TYPE_LABELS: Record<KostenRunType, string> = {
  analysis: "Analyse",
  section_regenerated: "Abschnitt neu erstellt",
  web_search: "Webrecherche",
}

export const RUN_STATUS_LABELS: Record<KostenRunStatus, string> = {
  completed: "Abgeschlossen",
  stopped_cost: "Gestoppt: Kostenlimit",
  failed: "Fehlgeschlagen",
  cancelled: "Abgebrochen",
}

export const EXECUTION_STATUS_LABELS: Record<ModelExecutionStatus, string> = {
  completed: "Technisch abgeschlossen",
  failed: "Fehlgeschlagen",
  cancelled: "Abgebrochen",
}

export const COST_STATUS_LABELS: Record<CostStatus, string> = {
  priced: "Bepreist",
  estimated: "Geschätzt",
  partial: "Teilweise bepreist",
  unavailable: "Nicht verfügbar",
}

export const EMPTY_COST: CostValue = { status: "unavailable" }

function validAmount(cost: CostValue | undefined): number | undefined {
  if (
    !cost ||
    cost.status === "unavailable" ||
    cost.amountChf === undefined ||
    !Number.isFinite(cost.amountChf) ||
    cost.amountChf < 0
  ) {
    return undefined
  }
  return cost.amountChf
}

function formatChf(amountChf: number): string {
  return `CHF ${amountChf.toFixed(2)}`
}

export function formatCost(cost: CostValue | undefined): string {
  const amount = validAmount(cost)
  if (amount === undefined || !cost) return "Nicht verfügbar"
  if (cost.status === "estimated") return `~ ${formatChf(amount)}`
  if (cost.status === "partial") return `mind. ${formatChf(amount)}`
  return formatChf(amount)
}

export function formatRemainingBudget(cost: CostValue): string {
  const amount = validAmount(cost)
  if (amount === undefined) return "Nicht verfügbar"
  if (cost.status === "estimated") return `ca. ${formatChf(amount)}`
  if (cost.status === "partial") return `höchstens ${formatChf(amount)}`
  return formatChf(amount)
}

export function aggregateCosts(costs: readonly CostValue[]): CostValue {
  const amounts = costs
    .map((cost) => validAmount(cost))
    .filter((amount): amount is number => amount !== undefined)

  if (amounts.length === 0) return EMPTY_COST

  const amountChf = amounts.reduce((sum, amount) => sum + amount, 0)
  const incomplete =
    amounts.length !== costs.length ||
    costs.some(
      (cost) => cost.status === "partial" || cost.status === "unavailable"
    )

  if (incomplete) return { status: "partial", amountChf }
  if (costs.some((cost) => cost.status === "estimated")) {
    return { status: "estimated", amountChf }
  }
  return { status: "priced", amountChf }
}

export function averageCosts(costs: readonly CostValue[]): {
  cost: CostValue
  knownCount: number
} {
  const known = costs.filter((cost) => validAmount(cost) !== undefined)
  if (known.length === 0) return { cost: EMPTY_COST, knownCount: 0 }

  const aggregate = aggregateCosts(costs)
  const knownTotal = known.reduce(
    (sum, cost) => sum + (validAmount(cost) ?? 0),
    0
  )
  return {
    cost: { status: aggregate.status, amountChf: knownTotal / known.length },
    knownCount: known.length,
  }
}

export function getRunDurationMs(
  run: Pick<KostenRunViewModel, "startedAt" | "endedAt">
): number | undefined {
  if (!run.endedAt) return undefined
  const started = Date.parse(run.startedAt)
  const ended = Date.parse(run.endedAt)
  if (!Number.isFinite(started) || !Number.isFinite(ended) || ended < started) {
    return undefined
  }
  return ended - started
}

export function formatDuration(durationMs: number | undefined): string {
  if (
    durationMs === undefined ||
    !Number.isFinite(durationMs) ||
    durationMs < 0
  ) {
    return "Nicht verfügbar"
  }
  const seconds = Math.round(durationMs / 1000)
  if (seconds < 60) return `${seconds} s`

  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes < 60) {
    return remainingSeconds > 0
      ? `${minutes} min ${remainingSeconds} s`
      : `${minutes} min`
  }

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return remainingMinutes > 0
    ? `${hours} h ${remainingMinutes} min`
    : `${hours} h`
}

export function formatDateTime(value: string | undefined): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "Nicht verfügbar"
  return new Intl.DateTimeFormat("de-CH", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Zurich",
  }).format(new Date(value))
}

export function formatTokens(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value) || value < 0) {
    return "Nicht verfügbar"
  }
  return new Intl.NumberFormat("de-CH").format(value)
}

export function runProviderModelLabel(run: KostenRunViewModel): string {
  if (run.providerLabels.length === 0 && run.modelLabels.length === 0) {
    return run.webEnabled && !run.kiEnabled ? "Nur Webrecherche" : "Nicht verfügbar"
  }
  if (run.providerLabels.length === 1 && run.modelLabels.length === 1) {
    return `${run.providerLabels[0]} / ${run.modelLabels[0]}`
  }
  if (run.providerLabels.length > 1) {
    return `${run.providerLabels.join(" + ")} / Mehrere Modelle`
  }
  return `${run.providerLabels[0] ?? "Mehrere Dienste"} / ${
    run.modelLabels.length > 1 ? "Mehrere Modelle" : run.modelLabels[0]
  }`
}

export function runProviderModelKeys(run: KostenRunViewModel): string[] {
  const executionKeys = run.executions.map((execution) =>
    providerModelKey(execution.provider, execution.model)
  )
  if (executionKeys.length > 0) return [...new Set(executionKeys)]

  const keys: string[] = []
  for (const provider of run.providerLabels) {
    for (const model of run.modelLabels) {
      keys.push(providerModelKey(provider, model))
    }
  }
  return [...new Set(keys)]
}

export function providerModelKey(provider: string, model: string): string {
  return `${provider}::${model}`
}

export function parseProviderModelKey(key: string): {
  provider: string
  model: string
} {
  const separator = key.indexOf("::")
  if (separator === -1) return { provider: key, model: "" }
  return {
    provider: key.slice(0, separator),
    model: key.slice(separator + 2),
  }
}

function comparableCost(run: KostenRunViewModel): number | undefined {
  return validAmount(run.cost)
}

function comparableDate(run: KostenRunViewModel): number {
  const value = Date.parse(run.startedAt)
  return Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY
}

function compareOptionalDescending(
  left: number | undefined,
  right: number | undefined
): number {
  if (left === undefined && right === undefined) return 0
  if (left === undefined) return 1
  if (right === undefined) return -1
  return right - left
}

export function filterAndSortRuns(
  runs: readonly KostenRunViewModel[],
  filters: RunFilters
): KostenRunViewModel[] {
  const query = filters.query.trim().toLocaleLowerCase("de-CH")
  const filtered = runs.filter((run) => {
    if (filters.status !== "all" && run.status !== filters.status) return false
    if (filters.type !== "all" && run.type !== filters.type) return false
    if (
      filters.providerModel !== "all" &&
      !runProviderModelKeys(run).includes(filters.providerModel)
    ) {
      return false
    }
    if (!query) return true
    return `${run.user} ${run.auditRef ?? ""}`
      .toLocaleLowerCase("de-CH")
      .includes(query)
  })

  return [...filtered].sort((left, right) => {
    let result = 0
    if (filters.sort === "cost_desc") {
      result = compareOptionalDescending(comparableCost(left), comparableCost(right))
    } else if (filters.sort === "duration_desc") {
      result = compareOptionalDescending(
        getRunDurationMs(left),
        getRunDurationMs(right)
      )
    } else {
      result = comparableDate(right) - comparableDate(left)
    }
    return result || comparableDate(right) - comparableDate(left)
  })
}

export function deriveKostenOverview(
  runs: readonly KostenRunViewModel[],
  projectLimitChf: number
): KostenOverview {
  const totalCost = aggregateCosts(runs.map((run) => run.cost))
  const average = averageCosts(runs.map((run) => run.cost))
  const durations = runs
    .map((run) => getRunDurationMs(run))
    .filter((duration): duration is number => duration !== undefined)
  const averageDurationMs =
    durations.length > 0
      ? durations.reduce((sum, duration) => sum + duration, 0) / durations.length
      : undefined
  const mostExpensiveRun = runs.reduce<KostenRunViewModel | undefined>(
    (current, run) => {
      const amount = comparableCost(run)
      if (amount === undefined) return current
      if (!current || amount > (comparableCost(current) ?? Number.NEGATIVE_INFINITY)) {
        return run
      }
      return current
    },
    undefined
  )
  const totalAmount = validAmount(totalCost)
  const remainingAmount =
    totalAmount === undefined || !Number.isFinite(projectLimitChf)
      ? undefined
      : Math.max(0, projectLimitChf - totalAmount)

  return {
    totalCost,
    averageCost: average.cost,
    knownCostRuns: average.knownCount,
    averageDurationMs,
    knownDurationRuns: durations.length,
    mostExpensiveRun,
    hasIncompleteCosts:
      totalCost.status === "partial" || totalCost.status === "unavailable",
    usagePercent:
      totalAmount === undefined || projectLimitChf <= 0
        ? undefined
        : (totalAmount / projectLimitChf) * 100,
    remainingBudget:
      remainingAmount === undefined
        ? EMPTY_COST
        : { status: totalCost.status, amountChf: remainingAmount },
  }
}

interface MutableProviderAggregate {
  provider: string
  model: string
  usageCount: number
  hasUsageCount: boolean
  costs: CostValue[]
  costCallCount: number
  knownCostTotal: number
  latencyMsTotal: number
  latencyCallCount: number
  successfulCalls: number
  technicalStatusCount: number
}

export function aggregateProviderModels(
  runs: readonly KostenRunViewModel[]
): ProviderModelAggregate[] {
  const grouped = new Map<string, MutableProviderAggregate>()

  for (const run of runs) {
    for (const execution of run.executions) {
      const key = providerModelKey(execution.provider, execution.model)
      const group = grouped.get(key) ?? {
        provider: execution.provider,
        model: execution.model,
        usageCount: 0,
        hasUsageCount: false,
        costs: [],
        costCallCount: 0,
        knownCostTotal: 0,
        latencyMsTotal: 0,
        latencyCallCount: 0,
        successfulCalls: 0,
        technicalStatusCount: 0,
      }
      const callCount =
        execution.callCount !== undefined &&
        Number.isFinite(execution.callCount) &&
        execution.callCount > 0
          ? execution.callCount
          : undefined

      if (callCount !== undefined) {
        group.usageCount += callCount
        group.hasUsageCount = true
      }
      if (execution.cost) {
        group.costs.push(execution.cost)
        const amount = validAmount(execution.cost)
        if (amount !== undefined && callCount !== undefined) {
          group.knownCostTotal += amount
          group.costCallCount += callCount
        }
      }
      if (
        execution.latencyMsTotal !== undefined &&
        Number.isFinite(execution.latencyMsTotal) &&
        execution.latencyMsTotal >= 0 &&
        callCount !== undefined
      ) {
        group.latencyMsTotal += execution.latencyMsTotal
        group.latencyCallCount += callCount
      }
      if (execution.status && callCount !== undefined) {
        group.technicalStatusCount += callCount
        if (execution.status === "completed") {
          group.successfulCalls += callCount
        }
      }
      grouped.set(key, group)
    }
  }

  return [...grouped.entries()]
    .map(([id, group]): ProviderModelAggregate => {
      const totalCost =
        group.costs.length > 0 ? aggregateCosts(group.costs) : EMPTY_COST
      const averageCost =
        group.costCallCount > 0
          ? {
              status: totalCost.status,
              amountChf: group.knownCostTotal / group.costCallCount,
            }
          : EMPTY_COST
      return {
        id,
        provider: group.provider,
        model: group.model,
        usageCount: group.hasUsageCount ? group.usageCount : undefined,
        totalCost,
        averageCost,
        averageLatencyMs:
          group.latencyCallCount > 0
            ? group.latencyMsTotal / group.latencyCallCount
            : undefined,
        latencyCallCount: group.latencyCallCount,
        technicalSuccessRate:
          group.technicalStatusCount > 0
            ? (group.successfulCalls / group.technicalStatusCount) * 100
            : undefined,
        technicalStatusCount: group.technicalStatusCount,
      }
    })
    .sort(
      (left, right) =>
        left.provider.localeCompare(right.provider, "de-CH") ||
        left.model.localeCompare(right.model, "de-CH")
    )
}

export function executionLatencyTotal(
  executions: readonly ModelExecutionViewModel[]
): number | undefined {
  const latencies = executions
    .map((execution) => execution.latencyMsTotal)
    .filter((latency): latency is number => latency !== undefined)
  if (latencies.length === 0) return undefined
  return latencies.reduce((sum, latency) => sum + latency, 0)
}
