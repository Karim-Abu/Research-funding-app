import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { LiveReview } from "@/components/review/live-review"
import { ReviewProgressCard } from "@/components/review/review-progress-card"
import { CHECK_AREA_LABELS, type CheckAreaKey } from "@/lib/check-status"

const AREAS = Object.keys(CHECK_AREA_LABELS) as CheckAreaKey[]

function pkg(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "r1",
    requirements: [],
    fields: [],
    findings: [],
    approval_status: "blocked",
    blocker_count: 0,
    warning_count: 0,
    open_issues: [],
    review_package_version: "rpv-1",
    current_approval_scope_hash: "a".repeat(64),
    recheck_required: false,
    stale_finding_count: 0,
    ...overrides,
  }
}

function checkArea(
  area: CheckAreaKey,
  overrides: Record<string, unknown> = {}
) {
  return {
    area,
    status: "not_run",
    open_blockers: 0,
    open_warnings: 0,
    reason: "not_executed",
    ...overrides,
  }
}

function checkStatus(
  areaOverrides: Partial<Record<CheckAreaKey, Record<string, unknown>>> = {},
  overrides: Record<string, unknown> = {}
) {
  return {
    run_id: "r1",
    areas: AREAS.map((a) => checkArea(a, areaOverrides[a] ?? {})),
    stale: false,
    blocking_task_count: 0,
    evidence_note_count: 0,
    review_package_version: "rpv-1",
    ...overrides,
  }
}

function group(overrides: Record<string, unknown> = {}) {
  return {
    group_key: "export_blocker|draft_placeholder|intro.app.abstract",
    title: "Abstract: Sichtbare Platzhalter im Feldtext",
    count: 1,
    severity_class: "export_blocker",
    severity: "blocker",
    affected_fields: ["INTRO.APP.ABSTRACT"],
    examples: [
      {
        finding_id: "f1",
        field_id: "INTRO.APP.ABSTRACT",
        description: "Feld enthält Platzhalter.",
        target_type: "portal_field_draft",
        target_id: "INTRO.APP.ABSTRACT",
      },
    ],
    recommended_next_action: null,
    target_field_id: "INTRO.APP.ABSTRACT",
    area: "platzhalter",
    ...overrides,
  }
}

function fixQueue(groups: ReturnType<typeof group>[] = []) {
  return {
    run_id: "r1",
    grouped_findings: groups,
    next_actions: groups,
    total_open_findings: groups.reduce((s, g) => s + (g.count as number), 0),
    blocking_task_count: groups.filter((g) => g.severity === "blocker").length,
    evidence_note_count: 0,
  }
}

function statusDto(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "r1",
    blocker_count: 0,
    warning_count: 0,
    human_review_count: 0,
    stale: false,
    approval_status: "open",
    review_package_version: "rpv-1",
    per_area_counts: {},
    last_reviewed_at: null,
    blocking_task_count: 0,
    evidence_note_count: 0,
    ...overrides,
  }
}

/** Registriert alle vier Read-Endpoints der Qualitätsprüfung. */
function useReviewHandlers({
  pkgBody = pkg(),
  checksBody = checkStatus(),
  queueBody = fixQueue(),
  statusBody = statusDto(),
}: {
  pkgBody?: ReturnType<typeof pkg>
  checksBody?: ReturnType<typeof checkStatus>
  queueBody?: ReturnType<typeof fixQueue>
  statusBody?: ReturnType<typeof statusDto>
} = {}) {
  server.use(
    http.get("/api/runs/r1/review", () => HttpResponse.json(pkgBody)),
    http.get("/api/runs/r1/review/check-status", () =>
      HttpResponse.json(checksBody)
    ),
    http.get("/api/runs/r1/review/fix-queue", () =>
      HttpResponse.json(queueBody)
    ),
    http.get("/api/runs/r1/review/status", () => HttpResponse.json(statusBody)),
    http.get("/api/capabilities", () => HttpResponse.json({ features: {} }))
  )
}

describe("LiveReview", () => {
  it("zeigt Bereiche ohne ausgeführten Check als «Nicht geprüft», nie als bestanden", async () => {
    useReviewHandlers()
    render(<LiveReview runId="r1" />)
    const card = await screen.findByTestId("review-progress-card")
    // Kein Check lief ⇒ 0 von 9 bestanden, alles grau.
    expect(card).toHaveTextContent("0 / 9")
    expect(card).toHaveTextContent("Prüfbereiche bestanden")
    const rows = await screen.findAllByTestId("check-area")
    expect(rows).toHaveLength(AREAS.length)
    for (const row of rows) {
      expect(row).toHaveTextContent("Nicht geprüft")
      expect(row).not.toHaveTextContent(/^Bestanden$/)
    }
    // RUN 4A: Ring-Legende + die vier primären Kennzahlen.
    for (const label of [
      "Bestanden",
      "Teilweise bestanden",
      "Nicht bestanden",
      "Nicht geprüft",
      "Formale Blocker",
      "Fehlende Pflichtangaben",
      "Wichtige Qualitätsrisiken",
      "Offene menschliche Prüfungen",
    ]) {
      expect(card).toHaveTextContent(label)
    }
    // Die technische Claim-Zahl ist verlagert, nicht gelöscht (collapsed).
    expect(card).toHaveTextContent("Unterliegende Evidenzhinweise")
    expect(card).toHaveTextContent(/keine Aussage zur Förderwahrscheinlichkeit/)
  })

  it("RUN 4A: nicht ausgeführte Prüfungen erscheinen als «Nicht geprüft», nie als 0", () => {
    render(
      <ReviewProgressCard
        progress={{
          total: 9,
          bestanden: 0,
          teilweise: 0,
          nichtBestanden: 0,
          nichtGeprueft: 9,
        }}
        blockingTasks={0}
        evidenceNotes={0}
        pruefungNoetig={0}
        missingMandatory={null}
        qualityRisks={null}
      />
    )
    const card = screen.getByTestId("review-progress-card")
    // Zwei Kennzahlen ohne ausgeführte Prüfung → Text statt Null; zusammen mit
    // der Ring-Legende steht «Nicht geprüft» dreimal in der Karte.
    expect(within(card).getAllByText("Nicht geprüft")).toHaveLength(3)
  })

  it("zeigt Blocker als gruppierte Aufgabe, Bereich rot, Freigabe gesperrt", async () => {
    useReviewHandlers({
      pkgBody: pkg({ blocker_count: 1 }),
      checksBody: checkStatus(
        {
          platzhalter: { status: "failed", open_blockers: 1, reason: null },
          export: { status: "failed", reason: null },
        },
        { blocking_task_count: 1 }
      ),
      queueBody: fixQueue([group()]),
      statusBody: statusDto({ blocker_count: 1, blocking_task_count: 1 }),
    })
    render(<LiveReview runId="r1" />)
    await waitFor(() =>
      expect(
        screen.getAllByText(/Sichtbare Platzhalter im Feldtext/).length
      ).toBeGreaterThan(0)
    )
    const approve = screen.getByRole("button", { name: /Prüfung abschliessen/ })
    expect(approve).toBeDisabled()
    expect(screen.getByText(/1 Blocker offen/)).toBeInTheDocument()
    // Headline-Zahl: EINE blockierende Aufgabe (gruppiert), nicht N Findings.
    expect(
      screen.getByText(/1 blockierende Aufgabe zu klären/)
    ).toBeInTheDocument()
    // Die Aufgabe deep-linkt in das betroffene Feld.
    const editorLinks = screen.getAllByRole("button", { name: "Im Entwurf öffnen" })
    expect(
      editorLinks.some(
        (el) => el.getAttribute("href") === "/editor?field=INTRO.APP.ABSTRACT"
      )
    ).toBe(true)
    // Nur der ganze Lauf kann erneut geprüft werden.
    expect(
      screen.getByRole("button", { name: "Gesamte Prüfung erneut ausführen" })
    ).toBeInTheDocument()
  })

  it("100 gleichartige Claim-Probleme erscheinen als EINE Aufgabe mit Beispielen", async () => {
    const bigGroup = group({
      group_key: "evidence_risk|reliability:quantified|vc.business_targets_model.editor",
      title: "Business Targets: Quantifizierte Aussage ohne passenden Zahlenbeleg",
      count: 100,
      severity_class: "evidence_risk",
      severity: "warning",
      affected_fields: ["VC.BUSINESS_TARGETS_MODEL.EDITOR"],
      examples: [0, 1, 2, 3, 4].map((i) => ({
        finding_id: `f${i}`,
        field_id: "VC.BUSINESS_TARGETS_MODEL.EDITOR",
        description: `Quantifizierte Aussage ${i} ohne Zahl im Beleg.`,
        target_type: "draft_claim",
        target_id: `claim-${i}`,
      })),
      target_field_id: "VC.BUSINESS_TARGETS_MODEL.EDITOR",
      area: "evidenz_suffizienz",
    })
    useReviewHandlers({
      checksBody: checkStatus(
        {
          evidenz_suffizienz: {
            status: "warning",
            open_warnings: 100,
            reason: null,
          },
        },
        { evidence_note_count: 100 }
      ),
      queueBody: fixQueue([bigGroup]),
      statusBody: statusDto({ evidence_note_count: 100 }),
    })
    render(<LiveReview runId="r1" />)
    // Genau EIN gruppierter Eintrag «100 × …» in den Nächsten Aufgaben.
    const next = await screen.findByTestId("fix-queue-next")
    expect(next).toHaveTextContent("100 ×")
    expect(next).toHaveTextContent(
      "Business Targets: Quantifizierte Aussage ohne passenden Zahlenbeleg"
    )
    // Technische Claim-Zahl bleibt getrennt sichtbar (keine 100 Blocker).
    const card = screen.getByTestId("review-progress-card")
    expect(card).toHaveTextContent("Unterliegende Evidenzhinweise")
    expect(card).toHaveTextContent("100")
    expect(screen.queryByText(/100 blockierende/)).toBeNull()
  })

  it("Warnungen sperren die Arbeitskopie nicht, verhindern aber «fachlich freigegeben»", async () => {
    useReviewHandlers({
      pkgBody: pkg({ approval_status: "open" }),
      checksBody: checkStatus({
        pflichtfelder: { status: "passed", reason: null },
        zeichenlimits: { status: "passed", reason: null },
        platzhalter: { status: "passed", reason: null },
        evidenz_suffizienz: { status: "warning", open_warnings: 3, reason: null },
        export: { status: "warning", reason: null },
      }),
    })
    render(<LiveReview runId="r1" />)
    // Erscheint im Freigabe-Panel UND als Status des Export-Prüfbereichs.
    await waitFor(() =>
      expect(
        screen.getAllByText("Mit Warnungen kopierbar").length
      ).toBeGreaterThan(0)
    )
    // Kein grünes «Bereit für Export», aber der Kopierweg bleibt offen.
    expect(screen.queryByText("Bereit für Export")).toBeNull()
    expect(
      screen.getAllByRole("button", { name: /Weiter zum Export/ }).length
    ).toBeGreaterThan(0)
  })

  it("approves successfully when no blockers remain", async () => {
    useReviewHandlers({ pkgBody: pkg({ approval_status: "open" }) })
    server.use(
      http.post("/api/runs/r1/approvals", () =>
        HttpResponse.json(
          {
            approval_id: "ap1",
            run_id: "r1",
            scope: "run",
            status: "approved",
            approval_scope_hash: "a".repeat(64),
            approved_by: "u",
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      )
    )
    render(<LiveReview runId="r1" />)
    const approve = await screen.findByRole("button", { name: /Prüfung abschliessen/ })
    expect(approve).toBeEnabled()
    fireEvent.click(approve)
    await waitFor(() =>
      expect(screen.getByText("Prüfung abgeschlossen.")).toBeInTheDocument()
    )
  })

  it("enables approval when clean and shows recheck notice when required", async () => {
    useReviewHandlers({
      pkgBody: pkg({ recheck_required: true, approval_status: "blocked" }),
      checksBody: checkStatus({}, { stale: true }),
    })
    render(<LiveReview runId="r1" />)
    await waitFor(() =>
      expect(screen.getByText(/ungeprüfte Änderungen/)).toBeInTheDocument()
    )
    expect(screen.getByRole("button", { name: /Prüfung abschliessen/ })).toBeDisabled()
    expect(screen.getByText(/Erneute Prüfung erforderlich/)).toBeInTheDocument()
  })

  it("shows the stale-reliability banner and blocks approval (M10.1, F3)", async () => {
    useReviewHandlers({
      pkgBody: pkg({
        blocker_count: 1,
        findings: [
          {
            finding_id: "rel-stale", profile_id: "M9K.reliability_assurance",
            field_id: null, requirement_id: null,
            severity: "blocker",
            description:
              "Qualitätsprüfung veraltet: der Entwurf wurde nach dem letzten " +
              "Reliability-Lauf geändert.",
            suggested_improvement: null, status: "open", advisory: false,
          },
        ],
      }),
      checksBody: checkStatus({}, { stale: true }),
    })
    render(<LiveReview runId="r1" />)
    const banner = await screen.findByTestId("reliability-stale-banner")
    expect(banner).toHaveTextContent(
      "Qualitätsprüfung veraltet — bitte erneut ausführen."
    )
    expect(screen.getByRole("button", { name: /Prüfung abschliessen/ })).toBeDisabled()
  })

  it("shows no stale-reliability banner for claim-bound reliability findings", async () => {
    useReviewHandlers({
      pkgBody: pkg({
        blocker_count: 1,
        findings: [
          {
            finding_id: "rel-claim", profile_id: "M9K.reliability_assurance",
            field_id: "SOL.INNOVATION_SOLUTION.EDITOR", requirement_id: null,
            severity: "blocker",
            description: "Nicht belegte Aussage: bitte belegen oder abschwächen.",
            suggested_improvement: null, status: "open", advisory: false,
          },
        ],
      }),
    })
    render(<LiveReview runId="r1" />)
    await waitFor(() =>
      expect(screen.getByTestId("review-progress-card")).toBeInTheDocument()
    )
    expect(screen.queryByTestId("reliability-stale-banner")).toBeNull()
  })

  it("groups A3 findings under neutral review hints, blocks approval, hides provider", async () => {
    useReviewHandlers({
      pkgBody: pkg({
        blocker_count: 1,
        findings: [
          {
            finding_id: "det1", profile_id: "deterministic-review-1",
            field_id: "INTRO.APP.ABSTRACT", requirement_id: null,
            severity: "warning", description: "Deterministischer Hinweis.",
            suggested_improvement: null, status: "open", advisory: true,
          },
          {
            finding_id: "ai1", profile_id: "A3.evidence_consistency",
            field_id: "SOL.INNOVATION_SOLUTION.EDITOR", requirement_id: null,
            severity: "blocker",
            description: "Aussage ohne verifizierten Beleg.",
            suggested_improvement: "Beleg verknüpfen oder offen markieren.",
            status: "open", advisory: false,
          },
        ],
      }),
    })
    render(<LiveReview runId="r1" />)
    const aiSection = await screen.findByTestId("ai-findings")
    expect(aiSection).toHaveTextContent("Fachliche Prüfhinweise")
    expect(aiSection).toHaveTextContent("Aussage ohne verifizierten Beleg.")
    // Deterministic finding stays out of the KI section.
    expect(aiSection).not.toHaveTextContent("Deterministischer Hinweis.")
    // A3 blocker disables approval.
    expect(screen.getByRole("button", { name: /Prüfung abschliessen/ })).toBeDisabled()
    // No model/provider/confidence leaks anywhere.
    expect(screen.queryByText(/anthropic|openai|gpt|claude|sonnet|confidence|Konfidenz/i)).toBeNull()
  })
})
