// Workflow-Katalog (6 Schritte) und Schrittstatus-Ableitung (lib/workflow.ts).
// Schrittstatus entsteht nur aus Backend-Artefakten — nie aus «Screen besucht».

import { describe, expect, it } from "vitest"
import { selectActiveRun } from "@/lib/active-run"
import type { PartnerDto } from "@/lib/partners"
import type { ProjectDto } from "@/lib/projects"
import type { AnalysisRunDto, RunStatus } from "@/lib/runs"
import type { ReviewStatusDto } from "@/lib/status"
import {
  deriveStepStatuses,
  stepForPathname,
  WORKFLOW_STEPS,
} from "@/lib/workflow"

function makeProject(overrides: Partial<ProjectDto> = {}): ProjectDto {
  return {
    project_id: "p-1",
    workspace_id: "ws-1",
    title: "Testprojekt",
    description: "",
    funding_instrument_profile_id: "beta",
    data_classification: {
      sensitivity: "public",
      origin: "synthetic",
      processing_mode: "cloud_assisted",
      web_research_mode: "generic_only",
      nda_applies: false,
    } as ProjectDto["data_classification"],
    status: "active",
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
    active_run_id: null,
    direct_total_project_costs_excluding_overhead: 100000,
    total_requested_funding: 50000,
    workflow_summary: {
      bearbeitungsstand_percent: 50,
      current_step: 3,
      next_action: "review_analysis",
      latest_run_id: "run-1",
    },
    ...overrides,
  }
}

function makeRun(
  runId: string,
  status: RunStatus,
  createdAt = "2026-07-05T10:00:00Z"
): AnalysisRunDto {
  return {
    run_id: runId,
    project_id: "p-1",
    status,
    current_stage: "finalize_run",
    progress_percent: 100,
    processing_mode: "deterministic_only",
    created_at: createdAt,
    recheck_required: false,
    semantic_findings_stale: false,
  }
}

function makeReviewStatus(
  overrides: Partial<ReviewStatusDto> = {}
): ReviewStatusDto {
  return {
    run_id: "run-1",
    blocker_count: 0,
    warning_count: 0,
    human_review_count: 0,
    stale: false,
    approval_status: "open",
    review_package_version: "v1",
    per_area_counts: {},
    last_reviewed_at: null,
    ...overrides,
  }
}

const PARTNER: PartnerDto = {
  partner_id: "pa-1",
  project_id: "p-1",
  name: "Umsetzungspartner AG",
  partner_type: "implementation_partner",
}

function derive(opts: {
  project?: ProjectDto | null
  runs?: AnalysisRunDto[]
  reviewStatus?: ReviewStatusDto | null
  partners?: PartnerDto[] | null
}) {
  const runs = opts.runs ?? []
  return deriveStepStatuses({
    project: opts.project === undefined ? makeProject() : opts.project,
    runs,
    activeRun: selectActiveRun({
      projectActiveRunId:
        opts.project === undefined ? null : opts.project?.active_run_id,
      runs,
    }),
    reviewStatus: opts.reviewStatus ?? null,
    partners: opts.partners === undefined ? [PARTNER] : opts.partners,
  })
}

describe("WORKFLOW_STEPS Katalog", () => {
  it("hat genau 6 Schritte mit eindeutigen Labels und Nummern 1–6", () => {
    expect(WORKFLOW_STEPS).toHaveLength(6)
    const labels = new Set(WORKFLOW_STEPS.map((s) => s.label))
    expect(labels.size).toBe(6)
    expect(WORKFLOW_STEPS.map((s) => s.step)).toEqual([1, 2, 3, 4, 5, 6])
  })

  it("ordnet alle Workflow-Routen genau einem Schritt zu", () => {
    const expected: Record<string, number> = {
      "/intake": 1,
      "/import": 1,
      "/quellen": 1,
      "/partner": 2,
      "/anforderungen": 3,
      "/editor": 4,
      "/review": 5,
      "/export": 6,
      "/portal-transfer": 6,
    }
    for (const [route, step] of Object.entries(expected)) {
      expect(stepForPathname(route)?.step, route).toBe(step)
    }
    expect(stepForPathname("/")).toBeNull()
    expect(stepForPathname("/ki-team")).toBeNull()
  })
})

describe("deriveStepStatuses", () => {
  it("ohne Projekt sind alle Schritte «Nicht begonnen»", () => {
    const statuses = derive({ project: null })
    for (const step of WORKFLOW_STEPS) {
      expect(statuses[step.id]).toBe("nicht_begonnen")
    }
  })

  it("keine Runs ⇒ Analyse «Nicht begonnen», Prüfung «Nicht begonnen» (nie eine 0)", () => {
    const statuses = derive({ runs: [] })
    expect(statuses.analyse).toBe("nicht_begonnen")
    expect(statuses.pruefung).toBe("nicht_begonnen")
    expect(statuses.uebernahme).toBe("nicht_begonnen")
  })

  it("fehlgeschlagener neuester Run ohne completed ⇒ Analyse «Fehlgeschlagen», kein Haken", () => {
    const statuses = derive({ runs: [makeRun("run-1", "failed")] })
    expect(statuses.analyse).toBe("fehlgeschlagen")
    expect(statuses.entwurf).toBe("nicht_begonnen")
  })

  it("gestoppter neuester Run ohne completed ⇒ Analyse «Blockiert»", () => {
    const statuses = derive({ runs: [makeRun("run-1", "stopped")] })
    expect(statuses.analyse).toBe("blockiert")
  })

  it("laufender Run ⇒ Analyse «In Bearbeitung» — auch wenn ein alter completed existiert", () => {
    const statuses = derive({
      runs: [
        makeRun("run-old", "completed", "2026-07-01T10:00:00Z"),
        makeRun("run-live", "running", "2026-07-09T10:00:00Z"),
      ],
      reviewStatus: makeReviewStatus(),
    })
    expect(statuses.analyse).toBe("in_bearbeitung")
  })

  it("Blocker im kanonischen Status ⇒ Analyse/Prüfung/Übernahme «Blockiert»", () => {
    const statuses = derive({
      runs: [makeRun("run-1", "completed")],
      reviewStatus: makeReviewStatus({ blocker_count: 3 }),
    })
    expect(statuses.analyse).toBe("blockiert")
    expect(statuses.pruefung).toBe("blockiert")
    expect(statuses.uebernahme).toBe("blockiert")
  })

  it("Freigabe (approved, nicht stale) ⇒ Prüfung «Abgeschlossen», Übernahme «In Bearbeitung»", () => {
    const statuses = derive({
      runs: [makeRun("run-1", "completed")],
      reviewStatus: makeReviewStatus({ approval_status: "approved" }),
    })
    expect(statuses.pruefung).toBe("abgeschlossen")
    expect(statuses.entwurf).toBe("abgeschlossen")
    // Nie «Abgeschlossen»: die manuelle Übernahme ist nicht verifizierbar.
    expect(statuses.uebernahme).toBe("in_bearbeitung")
  })

  it("completed Run ohne ladbaren Review-Status ⇒ Prüfung «Nicht begonnen» (Noch nicht geprüft)", () => {
    const statuses = derive({
      runs: [makeRun("run-1", "completed")],
      reviewStatus: null,
    })
    expect(statuses.pruefung).toBe("nicht_begonnen")
  })

  it("stale ⇒ Prüfung «In Bearbeitung», offene Prüfung ohne Blocker ⇒ «Bereit zur Prüfung»", () => {
    const runs = [makeRun("run-1", "completed")]
    expect(
      derive({ runs, reviewStatus: makeReviewStatus({ stale: true }) }).pruefung
    ).toBe("in_bearbeitung")
    expect(derive({ runs, reviewStatus: makeReviewStatus() }).pruefung).toBe(
      "bereit_zur_pruefung"
    )
  })

  it("changes_required ⇒ Prüfung «Eingaben fehlen»", () => {
    const statuses = derive({
      runs: [makeRun("run-1", "completed")],
      reviewStatus: makeReviewStatus({ approval_status: "changes_required" }),
    })
    expect(statuses.pruefung).toBe("eingaben_fehlen")
  })

  it("keine Partner oder fehlende Budget-Kernfelder ⇒ Partner & Budget «Eingaben fehlen»", () => {
    expect(derive({ partners: [] }).partner).toBe("eingaben_fehlen")
    expect(
      derive({
        project: makeProject({ total_requested_funding: null }),
        partners: [PARTNER],
      }).partner
    ).toBe("eingaben_fehlen")
    expect(derive({ partners: [PARTNER] }).partner).toBe("abgeschlossen")
  })

  it("fehlende Quellen (upload_sources) ⇒ Projekt & Unterlagen «Eingaben fehlen»", () => {
    const project = makeProject({
      workflow_summary: {
        bearbeitungsstand_percent: 12,
        current_step: 2,
        next_action: "upload_sources",
      },
    })
    expect(derive({ project }).projekt).toBe("eingaben_fehlen")
    expect(derive({}).projekt).toBe("abgeschlossen")
  })
})
