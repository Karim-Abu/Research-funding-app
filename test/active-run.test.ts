// Run-Auswahl-Ladder (lib/active-run.ts): active_run_id → Nutzer-Auswahl →
// neuester abgeschlossener Run nach created_at. Nie «erster completed aus
// unsortierter Liste».

import { describe, expect, it } from "vitest"
import { selectActiveRun } from "@/lib/active-run"
import type { AnalysisRunDto, RunStatus } from "@/lib/runs"

function run(
  runId: string,
  status: RunStatus,
  createdAt: string
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

const OLD_COMPLETED = run("run-old", "completed", "2026-07-01T10:00:00Z")
const NEW_COMPLETED = run("run-new", "completed", "2026-07-05T10:00:00Z")
const NEWEST_FAILED = run("run-failed", "failed", "2026-07-08T10:00:00Z")
const RUNNING = run("run-running", "running", "2026-07-09T10:00:00Z")

describe("selectActiveRun", () => {
  it("Stufe 1: active_run_id gewinnt — auch gegen einen neueren completed Run", () => {
    const result = selectActiveRun({
      projectActiveRunId: "run-old",
      runs: [NEW_COMPLETED, OLD_COMPLETED],
    })
    expect(result.runId).toBe("run-old")
    expect(result.source).toBe("project_active")
  })

  it("hängende active_run_id (nicht in der Liste) fällt auf die nächste Stufe durch", () => {
    const result = selectActiveRun({
      projectActiveRunId: "run-deleted",
      runs: [OLD_COMPLETED, NEW_COMPLETED],
    })
    expect(result.runId).toBe("run-new")
    expect(result.source).toBe("latest_completed")
  })

  it("active_run_id, die auf einen nicht abgeschlossenen Run zeigt, wird ignoriert", () => {
    const result = selectActiveRun({
      projectActiveRunId: "run-failed",
      runs: [NEWEST_FAILED, OLD_COMPLETED],
    })
    expect(result.runId).toBe("run-old")
    expect(result.source).toBe("latest_completed")
  })

  it("Stufe 2: Nutzer-Auswahl gewinnt vor dem Neuesten, wenn kein Projekt-Pointer existiert", () => {
    const result = selectActiveRun({
      projectActiveRunId: null,
      userSelectedRunId: "run-old",
      runs: [NEW_COMPLETED, OLD_COMPLETED],
    })
    expect(result.runId).toBe("run-old")
    expect(result.source).toBe("user_selected")
  })

  it("Stufe 2: ungültige Nutzer-Auswahl fällt kontrolliert auf Stufe 3 durch", () => {
    const result = selectActiveRun({
      userSelectedRunId: "run-running",
      runs: [RUNNING, OLD_COMPLETED, NEW_COMPLETED],
    })
    expect(result.runId).toBe("run-new")
    expect(result.source).toBe("latest_completed")
  })

  it("Stufe 3: neuester completed nach created_at — unabhängig von der Listenreihenfolge", () => {
    // Bewusst «falsch» sortierte Liste (alt zuerst): ein naives
    // runs.find(completed) würde run-old liefern.
    const shuffled = [OLD_COMPLETED, NEWEST_FAILED, NEW_COMPLETED, RUNNING]
    const result = selectActiveRun({ runs: shuffled })
    expect(result.runId).toBe("run-new")
    expect(result.source).toBe("latest_completed")
  })

  it("ohne abgeschlossenen Run gibt es keine Auswahl (kein geratener Run)", () => {
    const result = selectActiveRun({ runs: [RUNNING, NEWEST_FAILED] })
    expect(result.runId).toBeNull()
    expect(result.run).toBeNull()
    expect(result.source).toBeNull()
  })

  it("leere Liste ⇒ keine Auswahl", () => {
    const result = selectActiveRun({ runs: [] })
    expect(result.runId).toBeNull()
  })
})
