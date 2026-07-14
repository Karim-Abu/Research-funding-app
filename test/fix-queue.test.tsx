// R2.5 — Fix Queue UI: «Nächste Aufgaben» + gruppierte Findings («4 × …»).
import { describe, it, expect } from "vitest"
import { render, screen, within, fireEvent } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"

import {
  GroupedFindingsSection,
  NextActionsCard,
} from "@/components/review/fix-queue"
import type { GroupedFindingDto } from "@/lib/fix-queue"

function group(overrides: Partial<GroupedFindingDto> = {}): GroupedFindingDto {
  return {
    group_key: "evidence_risk|reliability:quantified",
    title: "Quantifizierte Aussage ohne passenden Zahlenbeleg",
    count: 4,
    severity_class: "evidence_risk",
    severity: "warning",
    affected_fields: ["VC.BUSINESS_TARGETS_MODEL.EDITOR"],
    examples: [0, 1, 2, 3].map((i) => ({
      finding_id: `f-${i}`,
      field_id: "VC.BUSINESS_TARGETS_MODEL.EDITOR",
      description: `Beispiel-Claim ${i} ohne Zahlenbeleg.`,
      target_type: "draft_claim",
      target_id: `claim-${i}`,
    })),
    recommended_next_action: null,
    target_field_id: "VC.BUSINESS_TARGETS_MODEL.EDITOR",
    area: "evidenz_suffizienz",
    ...overrides,
  }
}

const FIXTURE: GroupedFindingDto[] = [
  group({
    group_key: "export_blocker|draft_placeholder",
    title: "Sichtbare Platzhalter im Feldtext",
    count: 3,
    severity_class: "export_blocker",
    severity: "blocker",
    affected_fields: ["INTRO.APP.ABSTRACT", "SOL.INNOVATION_SOLUTION.EDITOR"],
    target_field_id: null,
    examples: [
      {
        finding_id: "p-1",
        field_id: "INTRO.APP.ABSTRACT",
        description: "Das Feld „Abstract“ enthält noch sichtbare Platzhalter.",
        target_type: "portal_field_draft",
        target_id: "d-1",
      },
    ],
    recommended_next_action: "Platzhalter durch konkrete Angaben ersetzen.",
  }),
  group(),
  group({
    group_key: "eligibility_blocker|open_issue_blocker",
    title: "Blockierende Anforderung",
    count: 1,
    severity_class: "eligibility_blocker",
    severity: "blocker",
    affected_fields: [],
    target_field_id: null,
    examples: [
      {
        finding_id: "b-1",
        field_id: null,
        description: "Kein beitragsberechtigter Forschungspartner erfasst.",
        target_type: "requirement_assessment",
        target_id: "req-1",
      },
    ],
  }),
]

describe("NextActionsCard", () => {
  it("zeigt die Top-Aufgaben in Prioritätsreihenfolge mit Zählprefix", () => {
    render(<NextActionsCard groups={FIXTURE} limit={5} />)
    const items = screen.getAllByTestId("fix-queue-next-item")
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent("3 × Sichtbare Platzhalter im Feldtext")
    expect(items[0]).toHaveTextContent("Export-Blocker")
    expect(items[2]).toHaveTextContent("Blockierende Anforderung")
  })

  it("begrenzt auf Top-5", () => {
    const many = Array.from({ length: 8 }, (_, i) =>
      group({ group_key: `style_risk|fam-${i}`, title: `Gruppe ${i}` })
    )
    render(<NextActionsCard groups={many} limit={5} />)
    expect(screen.getAllByTestId("fix-queue-next-item")).toHaveLength(5)
  })

  it("verlinkt Feldgruppen auf den Entwurf (Deep-Link ?field=…)", () => {
    render(<NextActionsCard groups={[group()]} limit={5} />)
    // Base-UI-Button rendert den Anchor mit role="button" (vgl. live-review.test).
    const link = screen.getByRole("button", { name: "Im Entwurf öffnen" })
    expect(link).toHaveAttribute(
      "href",
      "/editor?field=VC.BUSINESS_TARGETS_MODEL.EDITOR"
    )
  })

  it("verlinkt Anforderungs-Blocker auf die Anforderungen", () => {
    render(<NextActionsCard groups={[FIXTURE[2]]} limit={5} />)
    const link = screen.getByRole("button", { name: "Zu den Anforderungen" })
    expect(link).toHaveAttribute("href", "/anforderungen")
  })
})

describe("GroupedFindingsSection", () => {
  it("zeigt «4 × Feld-Label: Titel» und beim Aufklappen die Einzel-Claims", () => {
    render(<GroupedFindingsSection groups={[group()]} />)
    const row = screen.getByTestId("grouped-finding")
    // Feldbewusster Titel über den zentralen fieldLabel-Helfer — nie rohe
    // Registry-Labels («Open Editor …») oder IDs.
    expect(row).toHaveTextContent(
      "4 × Value Creation → Business Targets Model: Quantifizierte Aussage ohne passenden Zahlenbeleg"
    )
    expect(row).not.toHaveTextContent(/Open Editor|VC\.BUSINESS/)
    fireEvent.click(within(row).getByRole("button", { expanded: false }))
    expect(row).toHaveTextContent("Beispiel-Claim 0 ohne Zahlenbeleg.")
    expect(row).toHaveTextContent("Beispiel-Claim 3 ohne Zahlenbeleg.")
  })

  it("weist auf weitere gleichartige Meldungen hin, wenn Beispiele gekappt sind", () => {
    const capped = group({ count: 31, examples: group().examples.slice(0, 3) })
    render(<GroupedFindingsSection groups={[capped]} />)
    const row = screen.getByTestId("grouped-finding")
    fireEvent.click(within(row).getByRole("button", { expanded: false }))
    expect(row).toHaveTextContent("… und 28 weitere gleichartige Meldungen.")
  })

  it("keine identischen Meldungen direkt untereinander (gruppierte Titel sind eindeutig)", () => {
    render(<GroupedFindingsSection groups={FIXTURE} />)
    const titles = screen
      .getAllByTestId("grouped-finding")
      .map((el) => el.textContent ?? "")
    for (let i = 1; i < titles.length; i++) {
      expect(titles[i]).not.toEqual(titles[i - 1])
    }
    expect(new Set(titles).size).toBe(titles.length)
  })
})

describe("ClaimDetailsDrawer (Technische Details, B4)", () => {
  it("öffnet aus einer Claim-Gruppe und zeigt claimgenaue Details ohne Provider-Wording", async () => {
    server.use(
      http.get("/api/runs/r1/reliability", () =>
        HttpResponse.json({
          run_id: "r1",
          available: true,
          reliability_stale: false,
          summary: null,
          claims: [
            {
              claim_id: "c1",
              field_id: "VC.BUSINESS_TARGETS_MODEL.EDITOR",
              claim_type: "market",
              strength: "strong",
              requires_evidence: true,
              claim_text: "Der Markt wächst um 40 Prozent pro Jahr.",
              lineage_status: "no_evidence",
              sufficiency_status: "insufficient_evidence",
              reason: "Keine verknüpfte Quelle gefunden.",
            },
          ],
          findings: [],
        })
      )
    )
    render(<GroupedFindingsSection groups={[group()]} runId="r1" />)
    const row = screen.getByTestId("grouped-finding")
    fireEvent.click(within(row).getByRole("button", { expanded: false }))
    fireEvent.click(
      within(row).getByRole("button", { name: /Technische Details/ })
    )
    const drawer = await screen.findByTestId("claim-details-drawer")
    expect(drawer).toHaveTextContent("Der Markt wächst um 40 Prozent pro Jahr.")
    expect(drawer).toHaveTextContent("Marktaussage")
    expect(drawer).toHaveTextContent(/stark formuliert/)
    expect(drawer).toHaveTextContent("Kein Beleg verknüpft")
    // Kein Modell-/Provider-Wording, keine Konfidenz-Prozente.
    expect(drawer.textContent ?? "").not.toMatch(
      /anthropic|openai|gpt|claude|sonnet|Konfidenz/i
    )
  })

  it("ohne runId bleibt die Gruppe ohne Drawer-Trigger (reine Anzeige)", () => {
    render(<GroupedFindingsSection groups={[group()]} />)
    const row = screen.getByTestId("grouped-finding")
    fireEvent.click(within(row).getByRole("button", { expanded: false }))
    expect(
      within(row).queryByRole("button", { name: /Technische Details/ })
    ).toBeNull()
  })
})
