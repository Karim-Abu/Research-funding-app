import { describe, it, expect } from "vitest"

import { checkpointGroups, findingFamily } from "@/lib/reliability-view"
import type { ReliabilityFindingDto } from "@/lib/reliability"

function f(
  finding_code: string,
  severity: "blocker" | "warning" = "warning"
): ReliabilityFindingDto {
  return {
    finding_id: `${finding_code}-id`,
    field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
    severity,
    description: "technische Meldung",
    status: "open",
    finding_code,
    target_type: "draft_claim",
    target_id: "clm-1",
  }
}

describe("reliability view model", () => {
  it("liest die Familie aus dem Finding-Code", () => {
    expect(findingFamily("reliability:market:clm-7")).toBe("reliability:market")
    expect(findingFamily("reliability:drift:code:FIELD")).toBe("reliability:drift")
  })

  it("bündelt unbekannte Familien, statt Meldungen zu verlieren", () => {
    const groups = checkpointGroups([
      f("reliability:brandneu:clm-1"),
      f("reliability:nochneuer:clm-2"),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0]).toMatchObject({
      family: "other",
      count: 2,
      text: "2 weitere Stellen brauchen eine Prüfung.",
      critical: false,
    })
  })

  it("«veraltet» ist kein inhaltlicher Prüfpunkt", () => {
    expect(checkpointGroups([f("reliability:stale:run-1", "blocker")])).toEqual([])
  })

  it("markiert nur blockierende Gruppen als kritisch und sortiert sie nach vorn", () => {
    const groups = checkpointGroups([
      ...Array.from({ length: 4 }, (_, i) => f(`reliability:unsupported:clm-${i}`)),
      f("reliability:conflict:clm-9", "blocker"),
    ])
    expect(groups.map((g) => [g.family, g.critical])).toEqual([
      ["reliability:conflict", true],
      ["reliability:unsupported", false],
    ])
  })

  it("formuliert Einzahl und Mehrzahl korrekt", () => {
    expect(checkpointGroups([f("reliability:market:clm-1")])[0].text).toBe(
      "1 Markt- oder Wettbewerbsangabe braucht einen Beleg."
    )
    expect(
      checkpointGroups([
        f("reliability:market:clm-1"),
        f("reliability:market:clm-2"),
      ])[0].text
    ).toBe("2 Markt- und Wettbewerbsangaben brauchen einen Beleg.")
  })
})
