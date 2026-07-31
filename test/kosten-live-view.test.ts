import { describe, expect, it } from "vitest"
import { RUN_STATUS_LABELS } from "@/lib/kosten"
import type { LiveCostExecution, LiveCostRun, LiveUsageCost } from "@/lib/kosten-live"
import {
  aggregateLiveCost,
  aggregateLiveRunTotals,
  groupExecutionsByRole,
  liveRunStatusView,
  providerLabel,
  roleLabel,
  splitExecutions,
  summarizePricing,
  unpricedBadgeLabel,
} from "@/lib/kosten-live-view"

function cost(overrides: Partial<LiveUsageCost> & { status: LiveUsageCost["status"] }): LiveUsageCost {
  return { usd: null, chf_reference: null, known_usd: 0, known_chf_reference: 0, unpriced_call_count: 0, ...overrides }
}

function execution(overrides: Partial<LiveCostExecution> & { id: string }): LiveCostExecution {
  return {
    role_label: "Textvorschlag",
    provider: "openai_direct",
    model: "gpt-5.6-luna",
    status: "succeeded",
    input_tokens: 100,
    cached_input_tokens: 0,
    cache_write_input_tokens: 0,
    output_tokens: 50,
    cost: cost({ status: "priced", usd: 0.01, known_usd: 0.01, known_chf_reference: 0.008 }),
    ...overrides,
  }
}

function run(overrides: Partial<LiveCostRun> & { id: string }): LiveCostRun {
  return {
    started_at: "2026-07-24T10:00:00Z",
    ended_at: "2026-07-24T10:01:00Z",
    status: "completed",
    processing_mode: "live",
    user: "Anna Keller",
    input_tokens: 100,
    cached_input_tokens: 0,
    cache_write_input_tokens: 0,
    output_tokens: 50,
    llm_calls: 1,
    web_calls: 0,
    cost: cost({ status: "priced", usd: 0.01, known_usd: 0.01, known_chf_reference: 0.008 }),
    executions: [],
    ...overrides,
  }
}

describe("liveRunStatusView", () => {
  it("bildet abgeschlossene Statuswerte auf den vorhandenen Status-Badge ab", () => {
    expect(liveRunStatusView("completed").badge).toBe("completed")
    expect(liveRunStatusView("failed").badge).toBe("failed")
    expect(liveRunStatusView("cancelled").badge).toBe("cancelled")
    expect(liveRunStatusView("stopped", "cost_budget_exhausted").badge).toBe("stopped_cost")
  })

  it("liefert deutsche Fallback-Labels für alle übrigen Statuswerte", () => {
    expect(liveRunStatusView("stopped", "llm_budget_exhausted")).toEqual({ badge: null, label: "Gestoppt: Aufruf-Limit erreicht", tone: "orange" })
    expect(liveRunStatusView("stopped")).toEqual({ badge: null, label: "Gestoppt", tone: "orange" })
    expect(liveRunStatusView("running")).toEqual({ badge: null, label: "Läuft", tone: "gray" })
    expect(liveRunStatusView("created")).toEqual({ badge: null, label: "Noch nicht gestartet", tone: "gray" })
    expect(liveRunStatusView("paused_for_review")).toEqual({ badge: null, label: "Wartet auf Prüfung", tone: "orange" })
    expect(liveRunStatusView("something_new")).toEqual({ badge: null, label: "Status unbekannt", tone: "gray" })
  })

  it("gibt nie einen rohen Backend-Key als Label aus", () => {
    const cases: Array<[string, string | null | undefined]> = [
      ["completed", null],
      ["failed", null],
      ["cancelled", null],
      ["stopped", "cost_budget_exhausted"],
      ["stopped", "llm_budget_exhausted"],
      ["stopped", undefined],
      ["running", null],
      ["created", null],
      ["paused_for_review", null],
      ["totally_unknown_status", null],
    ]
    for (const [status, stopReason] of cases) {
      const view = liveRunStatusView(status, stopReason)
      const label = view.badge ? RUN_STATUS_LABELS[view.badge] : view.label
      expect(label).toBeTruthy()
      expect(label).not.toContain("_")
    }
  })
})

describe("providerLabel", () => {
  it("übersetzt bekannte Provider-Keys", () => {
    expect(providerLabel("openai_direct")).toBe("OpenAI (direkt)")
    expect(providerLabel("anthropic_direct")).toBe("Anthropic (direkt)")
    expect(providerLabel("openai")).toBe("OpenAI")
    expect(providerLabel("anthropic")).toBe("Anthropic")
  })

  it("fällt bei fehlendem Provider auf «Unbekannter Dienst» zurück", () => {
    expect(providerLabel(null)).toBe("Unbekannter Dienst")
    expect(providerLabel(undefined)).toBe("Unbekannter Dienst")
    expect(providerLabel("")).toBe("Unbekannter Dienst")
  })

  it("formatiert unbekannte Keys lesbar statt sie roh anzuzeigen", () => {
    expect(providerLabel("mistral_direct")).toBe("Mistral Direct")
    expect(providerLabel("some-new-provider")).toBe("Some New Provider")
  })
})

describe("summarizePricing", () => {
  it("zählt externe, interne und unbepreiste Aufrufe getrennt", () => {
    const runs = [
      run({
        id: "run-1",
        executions: [
          execution({ id: "u1" }),
          execution({ id: "seed", provider: null, model: null, input_tokens: 0, output_tokens: 0, cost: cost({ status: "not_applicable" }) }),
        ],
      }),
      run({
        id: "run-2",
        cost: cost({ status: "unknown_price", unpriced_call_count: 1 }),
        executions: [execution({ id: "u2", cost: cost({ status: "unknown_price", unpriced_call_count: 1 }) })],
      }),
    ]
    expect(summarizePricing(runs)).toEqual({ externalCallCount: 2, unpricedCallCount: 1, internalCallCount: 1, fullyPriced: false })
  })

  it("zeigt nie mehr unbepreiste als externe Aufrufe («n von m»-Schutz)", () => {
    const runs = [
      run({
        id: "run-1",
        cost: cost({ status: "unknown_price", unpriced_call_count: 3 }),
        executions: [execution({ id: "u1", cost: cost({ status: "unknown_price", unpriced_call_count: 1 }) })],
      }),
    ]
    const summary = summarizePricing(runs)
    expect(summary.unpricedCallCount).toBe(3)
    expect(summary.externalCallCount).toBeGreaterThanOrEqual(summary.unpricedCallCount)
  })

  it("meldet vollständig bepreiste Nutzung", () => {
    const runs = [run({ id: "run-1", executions: [execution({ id: "u1" })] })]
    expect(summarizePricing(runs).fullyPriced).toBe(true)
  })
})

describe("splitExecutions", () => {
  it("trennt externe Aufrufe von internen Buchungszeilen", () => {
    const external = execution({ id: "u1" })
    const internal = execution({ id: "seed", provider: null, cost: cost({ status: "not_applicable" }) })
    expect(splitExecutions([external, internal])).toEqual({ external: [external], internalCount: 1 })
  })
})

describe("aggregateLiveCost", () => {
  it("summiert vollständig bepreiste Durchläufe als exakte Summe", () => {
    const runs = [
      run({ id: "run-1", cost: cost({ status: "priced", usd: 0.01, chf_reference: 0.008, known_usd: 0.01, known_chf_reference: 0.008 }) }),
      run({ id: "run-2", cost: cost({ status: "priced", usd: 0.02, chf_reference: 0.016, known_usd: 0.02, known_chf_reference: 0.016 }) }),
    ]
    const total = aggregateLiveCost(runs)
    expect(total.status).toBe("priced")
    expect(total.usd).toBeCloseTo(0.03)
    expect(total.chf_reference).toBeCloseTo(0.024)
  })

  it("stuft gemischte Durchläufe als partial ein und behauptet keine exakte Summe", () => {
    const runs = [
      run({ id: "run-1", cost: cost({ status: "priced", usd: 0.01, known_usd: 0.01, known_chf_reference: 0.008 }) }),
      run({ id: "run-2", cost: cost({ status: "unknown_price", unpriced_call_count: 2 }) }),
    ]
    const total = aggregateLiveCost(runs)
    expect(total.status).toBe("partial")
    expect(total.usd).toBeNull()
    expect(total.known_usd).toBeCloseTo(0.01)
    expect(total.unpriced_call_count).toBe(2)
  })

  it("stuft rein unbepreiste Nutzung als unknown_price ein", () => {
    const runs = [run({ id: "run-1", cost: cost({ status: "unknown_price", unpriced_call_count: 1 }) })]
    expect(aggregateLiveCost(runs).status).toBe("unknown_price")
  })

  it("liefert not_applicable ohne externe Nutzung", () => {
    expect(aggregateLiveCost([]).status).toBe("not_applicable")
    expect(aggregateLiveCost([run({ id: "run-1", cost: cost({ status: "not_applicable" }) })]).status).toBe("not_applicable")
  })
})

describe("aggregateLiveRunTotals", () => {
  it("summiert Aufrufe, Tokens und Laufzeit über alle beendeten Durchläufe", () => {
    const totals = aggregateLiveRunTotals([
      run({
        id: "run-1",
        started_at: "2026-07-24T10:00:00Z",
        ended_at: "2026-07-24T10:01:30Z",
        input_tokens: 1_000,
        output_tokens: 200,
        executions: [execution({ id: "u1" })],
      }),
      run({
        id: "run-2",
        started_at: "2026-07-24T11:00:00Z",
        ended_at: "2026-07-24T11:02:00Z",
        input_tokens: 2_000,
        output_tokens: 300,
        executions: [
          execution({ id: "u2" }),
          execution({ id: "u3" }),
        ],
      }),
    ])

    expect(totals).toEqual({
      runCount: 2,
      externalCallCount: 3,
      inputTokens: 3_000,
      outputTokens: 500,
      totalTokens: 3_500,
      totalDurationMs: 210_000,
      endedRunCount: 2,
    })
  })

  it("lässt laufende und zeitlich ungültige Durchläufe nur aus der Laufzeitsumme", () => {
    const totals = aggregateLiveRunTotals([
      run({ id: "running", status: "running", ended_at: null, executions: [execution({ id: "u1" })] }),
      run({
        id: "invalid",
        started_at: "2026-07-24T11:02:00Z",
        ended_at: "2026-07-24T11:00:00Z",
        executions: [execution({ id: "u2" })],
      }),
    ])

    expect(totals.runCount).toBe(2)
    expect(totals.externalCallCount).toBe(2)
    expect(totals.totalTokens).toBe(300)
    expect(totals.totalDurationMs).toBe(0)
    expect(totals.endedRunCount).toBe(0)
  })
})

describe("unpricedBadgeLabel", () => {
  it("dekliniert Singular und Plural korrekt", () => {
    expect(unpricedBadgeLabel(1)).toBe("1 Aufruf unbepreist")
    expect(unpricedBadgeLabel(4)).toBe("4 Aufrufe unbepreist")
  })
})

describe("roleLabel", () => {
  it("übersetzt bekannte System-Rollen ins Deutsche", () => {
    expect(roleLabel("A1_FACT_EVIDENCE_ANALYST")).toBe("Anforderungsanalyst")
    expect(roleLabel("A2_INNOSUISSE_PROPOSAL_WRITER")).toBe("Innovationstext-Assistent")
    expect(roleLabel("A3_INNOSUISSE_CRITICAL_REVIEWER")).toBe("Qualitätskoordinator")
    expect(roleLabel("RESEARCH_EVIDENCE_SYNTHESIZER")).toBe("Marktrecherche-Assistent")
  })

  it("fällt bei null oder unbekannter Rolle auf «KI-Aufruf» zurück", () => {
    expect(roleLabel(null)).toBe("KI-Aufruf")
    expect(roleLabel(undefined)).toBe("KI-Aufruf")
    expect(roleLabel("SOME_FUTURE_ROLE")).toBe("KI-Aufruf")
  })
})

describe("groupExecutionsByRole", () => {
  it("fasst mehrere Aufrufe derselben Rolle zu einer Zeile zusammen", () => {
    const groups = groupExecutionsByRole([
      execution({ id: "a", role_id: "A2_INNOSUISSE_PROPOSAL_WRITER", model: "gpt-5.6-terra", input_tokens: 7000, output_tokens: 3000, cost: cost({ status: "priced", usd: 0.02, known_usd: 0.02, known_chf_reference: 0.016 }) }),
      execution({ id: "b", role_id: "A2_INNOSUISSE_PROPOSAL_WRITER", model: "gpt-5.6-terra", input_tokens: 8000, output_tokens: 2000, cost: cost({ status: "priced", usd: 0.03, known_usd: 0.03, known_chf_reference: 0.024 }) }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].roleLabel).toBe("Innovationstext-Assistent")
    expect(groups[0].models).toEqual(["gpt-5.6-terra"])
    expect(groups[0].callCount).toBe(2)
    expect(groups[0].inputTokens).toBe(15000)
    expect(groups[0].outputTokens).toBe(5000)
    expect(groups[0].cost.status).toBe("priced")
    expect(groups[0].cost.usd).toBeCloseTo(0.05)
  })

  it("trennt verschiedene Rollen und schliesst interne Aufrufe aus", () => {
    const groups = groupExecutionsByRole([
      execution({ id: "a", role_id: "A1_FACT_EVIDENCE_ANALYST", model: "gpt-5.6-luna" }),
      execution({ id: "b", role_id: "A3_INNOSUISSE_CRITICAL_REVIEWER", model: "claude-sonnet-5" }),
      execution({ id: "seed", role_id: null, provider: null, model: null, cost: cost({ status: "not_applicable" }) }),
    ])
    expect(groups.map((group) => group.roleLabel)).toEqual(["Anforderungsanalyst", "Qualitätskoordinator"])
  })

  it("stuft eine Gruppe mit unbepreisten Aufrufen als partial/unknown ein", () => {
    const partial = groupExecutionsByRole([
      execution({ id: "a", role_id: "A2_INNOSUISSE_PROPOSAL_WRITER", cost: cost({ status: "priced", usd: 0.02, known_usd: 0.02, known_chf_reference: 0.016 }) }),
      execution({ id: "b", role_id: "A2_INNOSUISSE_PROPOSAL_WRITER", cost: cost({ status: "unknown_price", unpriced_call_count: 1 }) }),
    ])
    expect(partial[0].cost.status).toBe("partial")
    expect(partial[0].cost.usd).toBeNull()

    const unknown = groupExecutionsByRole([
      execution({ id: "a", role_id: "A2_INNOSUISSE_PROPOSAL_WRITER", cost: cost({ status: "unknown_price", unpriced_call_count: 1 }) }),
    ])
    expect(unknown[0].cost.status).toBe("unknown_price")
  })
})
