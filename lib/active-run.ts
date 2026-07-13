// Zentrale Run-Auswahl (eine Run-Wahrheit für alle Screens). Reine Funktion,
// keine Fetches — der React-Teil lebt in
// components/providers/workflow-run-provider.tsx.
//
// Ladder (Reihenfolge ist Vertrag):
//   1. project.active_run_id — vom Backend beim erfolgreichen Run-Abschluss
//      gesetzt (backend/app/runs/graph.py, node_finalize_run);
//   2. explizit vom Nutzer gewählter Run (sessionStorage, lib/intake-store.ts);
//   3. kontrollierter Fallback: neuester abgeschlossener Run nach created_at —
//      expliziter Sort, nie Listenreihenfolge, nie «irgendein erster completed».

import type { AnalysisRunDto } from "./runs"

export type ActiveRunSource =
  | "project_active"
  | "user_selected"
  | "latest_completed"

export interface ActiveRunSelection {
  runId: string | null
  run: AnalysisRunDto | null
  source: ActiveRunSource | null
}

export const NO_ACTIVE_RUN: ActiveRunSelection = {
  runId: null,
  run: null,
  source: null,
}

/** Deutsche Beschreibung der Auswahlquelle für «Technische Details». */
export const ACTIVE_RUN_SOURCE_LABELS: Record<ActiveRunSource, string> = {
  project_active: "aktiver Lauf des Projekts",
  user_selected: "vom Nutzer gewählt",
  latest_completed: "neuester abgeschlossener Lauf",
}

export function selectActiveRun(opts: {
  projectActiveRunId?: string | null
  userSelectedRunId?: string | null
  runs: readonly AnalysisRunDto[]
}): ActiveRunSelection {
  // Nur abgeschlossene Läufe tragen Artefakte (Anforderungen, Felder, Review).
  const completed = opts.runs.filter((r) => r.status === "completed")
  const byId = (id: string): AnalysisRunDto | null =>
    completed.find((r) => r.run_id === id) ?? null

  // Stufe 1: Projekt-Pointer — nur wenn er auf einen real vorhandenen,
  // abgeschlossenen Run zeigt (schützt vor hängenden IDs).
  if (opts.projectActiveRunId) {
    const run = byId(opts.projectActiveRunId)
    if (run) return { runId: run.run_id, run, source: "project_active" }
  }

  // Stufe 2: explizite Nutzer-Auswahl, gleiche Gültigkeitsprüfung.
  if (opts.userSelectedRunId) {
    const run = byId(opts.userSelectedRunId)
    if (run) return { runId: run.run_id, run, source: "user_selected" }
  }

  // Stufe 3: neuester abgeschlossener Run — explizit sortiert.
  const newest =
    [...completed].sort(
      (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)
    )[0] ?? null
  if (newest) {
    return { runId: newest.run_id, run: newest, source: "latest_completed" }
  }
  return NO_ACTIVE_RUN
}
