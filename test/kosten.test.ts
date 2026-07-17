import { describe, expect, it } from "vitest"
import { RUNS } from "@/lib/kosten-mock-data"
import {
  aggregateCosts,
  aggregateProviderModels,
  averageCosts,
  deriveKostenOverview,
  filterAndSortRuns,
  formatCost,
  formatDuration,
  formatRemainingBudget,
  getRunDurationMs,
  providerModelKey,
  type CostValue,
  type KostenRunViewModel,
} from "@/lib/kosten"

describe("Kosten-View-Model", () => {
  it("formatiert alle Kostenstatus ohne falsche Genauigkeit", () => {
    expect(formatCost({ status: "priced", amountChf: 0.85 })).toBe("CHF 0.85")
    expect(formatCost({ status: "estimated", amountChf: 0.85 })).toBe("~ CHF 0.85")
    expect(formatCost({ status: "partial", amountChf: 0.85 })).toBe("mind. CHF 0.85")
    expect(formatCost({ status: "unavailable" })).toBe("Nicht verfügbar")
    expect(formatCost({ status: "priced" })).toBe("Nicht verfügbar")
  })

  it("leitet Summenstatus und Durchschnittsabdeckung aus vorhandenen Werten ab", () => {
    const costs: CostValue[] = [
      { status: "priced", amountChf: 1 },
      { status: "estimated", amountChf: 2 },
      { status: "unavailable" },
    ]
    expect(aggregateCosts(costs)).toEqual({ status: "partial", amountChf: 3 })
    expect(averageCosts(costs)).toEqual({
      cost: { status: "partial", amountChf: 1.5 },
      knownCount: 2,
    })
  })

  it("kennzeichnet Restbudget passend zu bepreisten, geschätzten und partiellen Summen", () => {
    expect(formatRemainingBudget({ status: "priced", amountChf: 10 })).toBe("CHF 10.00")
    expect(formatRemainingBudget({ status: "estimated", amountChf: 10 })).toBe("ca. CHF 10.00")
    expect(formatRemainingBudget({ status: "partial", amountChf: 10 })).toBe("höchstens CHF 10.00")
  })

  it("berechnet End-to-End-Laufzeit nur aus gültigem Start und Ende", () => {
    expect(getRunDurationMs(RUNS[0])).toBe(128_000)
    expect(formatDuration(getRunDurationMs(RUNS[0]))).toBe("2 min 8 s")
    expect(getRunDurationMs({ startedAt: RUNS[0].startedAt })).toBeUndefined()
    expect(
      getRunDurationMs({
        startedAt: "2026-06-10T10:00:00Z",
        endedAt: "2026-06-10T09:00:00Z",
      })
    ).toBeUndefined()
  })

  it("berechnet Provider-Latenz gewichtet nach gemeldeten Aufrufen", () => {
    const aggregates = aggregateProviderModels(RUNS)
    const openAi = aggregates.find(
      (entry) => entry.provider === "OpenAI" && entry.model === "GPT-5.4-mini"
    )
    expect(openAi?.usageCount).toBe(8)
    // 23k + 21k + 17k + 29k + 44k bei 8 gemeldeten Aufrufen.
    expect(openAi?.averageLatencyMs).toBe(16_750)
    expect(openAi?.technicalSuccessRate).toBe(100)
  })

  it("erfindet bei fehlender Latenz oder Aufrufzahl keinen Durchschnitt", () => {
    const run: KostenRunViewModel = {
      ...RUNS[0],
      id: "without-latency",
      executions: [
        {
          id: "e1",
          roleLabel: "Test",
          provider: "Provider",
          model: "Modell",
          latencyMsTotal: 1_000,
        },
      ],
    }
    const aggregate = aggregateProviderModels([run])[0]
    expect(aggregate.usageCount).toBeUndefined()
    expect(aggregate.averageLatencyMs).toBeUndefined()
  })

  it("filtert und sortiert Runs deterministisch", () => {
    expect(
      filterAndSortRuns(RUNS, {
        query: "AE-2029",
        status: "all",
        type: "all",
        providerModel: "all",
        sort: "date_desc",
      }).map((run) => run.id)
    ).toEqual(["r3"])

    const firecrawlRuns = filterAndSortRuns(RUNS, {
      query: "",
      status: "all",
      type: "all",
      providerModel: providerModelKey("Firecrawl", "Webrecherche"),
      sort: "date_desc",
    })
    expect(firecrawlRuns.map((run) => run.id)).toEqual(["r1", "r4", "r5", "r7"])

    expect(
      filterAndSortRuns(RUNS, {
        query: "",
        status: "all",
        type: "all",
        providerModel: "all",
        sort: "cost_desc",
      })[0].id
    ).toBe("r2")
  })

  it("leitet Projektverbrauch und unvollständiges Restbudget aus Runs ab", () => {
    const overview = deriveKostenOverview(RUNS, 20)
    expect(overview.totalCost).toEqual({ status: "partial", amountChf: 4.2 })
    expect(overview.knownCostRuns).toBe(8)
    expect(overview.averageDurationMs).toBe(83_000)
    expect(overview.mostExpensiveRun?.id).toBe("r2")
    expect(formatRemainingBudget(overview.remainingBudget)).toBe("höchstens CHF 15.80")
  })
})
