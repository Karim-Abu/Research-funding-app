// R2.5 — Client für die Fix Queue (GET /api/runs/{id}/review/fix-queue, R2.4).
// Gruppierte Findings + priorisierte «Nächste Aufgaben»; read-only.

import * as React from "react"

import { fieldLabel } from "./review-view"

export type SeverityClass =
  | "export_blocker"
  | "eligibility_blocker"
  | "budget_blocker"
  | "reviewer_risk"
  | "evidence_risk"
  | "style_risk"

export interface GroupedFindingExampleDto {
  finding_id: string
  field_id: string | null
  description: string
  target_type: string | null
  target_id: string | null
}

export interface GroupedFindingDto {
  group_key: string
  title: string
  count: number
  severity_class: SeverityClass
  severity: "blocker" | "warning" | "info"
  affected_fields: string[]
  examples: GroupedFindingExampleDto[]
  recommended_next_action: string | null
  target_field_id: string | null
  /** Prüfbereich der Gruppe (Teil A); null = keinem Bereich zuordenbar. */
  area: string | null
}

export interface FixQueueDto {
  run_id: string
  grouped_findings: GroupedFindingDto[]
  next_actions: GroupedFindingDto[]
  total_open_findings: number
  /** B7 — gruppierte handlungsrelevante Aufgaben mit Blocker-Severity. */
  blocking_task_count: number
  /** B7 — technische Zahl der offenen claimgebundenen Findings. */
  evidence_note_count: number
}

/** Anzeigetitel einer Gruppe: bei genau einem Zielfeld mit dem zentralen
 *  Feld-Label davor («Solution → Innovation Solution: Nicht belegte Aussage»).
 *  Nutzt fieldLabel — nie rohe Registry-Labels oder IDs. */
export function groupDisplayTitle(group: GroupedFindingDto): string {
  if (group.target_field_id) {
    return `${fieldLabel(group.target_field_id)}: ${group.title}`
  }
  return group.title
}

/** Nutzerlesbare Labels der sechs severity-Klassen (UI-Anzeige). */
export const SEVERITY_CLASS_LABELS: Record<SeverityClass, string> = {
  export_blocker: "Export-Blocker",
  eligibility_blocker: "Fördervoraussetzung",
  budget_blocker: "Budget",
  reviewer_risk: "Gutachter-Risiko",
  evidence_risk: "Beleg-Risiko",
  style_risk: "Hinweis",
}

export async function getFixQueue(runId: string): Promise<FixQueueDto> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/review/fix-queue`
  )
  if (!res.ok) {
    throw new Error("Die Aufgabenliste konnte nicht geladen werden.")
  }
  return (await res.json()) as FixQueueDto
}

/** Lädt die Fix Queue eines Runs; `refreshKey` erzwingt Neuladen (z. B. neue
 *  review_package_version). Die Fix Queue ist die Standard-Aufgabenliste der
 *  Qualitätsprüfung (kein Feature-Flag mehr). */
export function useFixQueue(
  runId: string | null | undefined,
  refreshKey?: string
): { queue: FixQueueDto | null; failed: boolean } {
  const [queue, setQueue] = React.useState<FixQueueDto | null>(null)
  const [failed, setFailed] = React.useState(false)

  React.useEffect(() => {
    if (!runId) {
      setQueue(null)
      return
    }
    let active = true
    getFixQueue(runId)
      .then((q) => {
        if (!active) return
        setQueue(q)
        setFailed(false)
      })
      .catch(() => {
        if (!active) return
        setQueue(null)
        setFailed(true)
      })
    return () => {
      active = false
    }
  }, [runId, refreshKey])

  return { queue, failed }
}
