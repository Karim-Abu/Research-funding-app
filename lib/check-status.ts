// Teil A — Check-Status-Client. EINZIGE Statusquelle der Qualitätsprüfung für
// die neun Prüfbereiche (GET /api/runs/{id}/review/check-status). «Bestanden»
// kommt ausschliesslich aus dem Backend (Check lief nachweislich und war
// erfolgreich); die frühere automatische Pass-Logik im Frontend ist entfernt.

import * as React from "react"

export type CheckAreaKey =
  | "pflichtfelder"
  | "zeichenlimits"
  | "platzhalter"
  | "voraussetzungen"
  | "budget"
  | "evidenz_coverage"
  | "evidenz_suffizienz"
  | "konsistenz"
  | "export"

export type CheckAreaState = "not_run" | "passed" | "warning" | "failed"

export interface CheckAreaStatusDto {
  area: CheckAreaKey
  status: CheckAreaState
  open_blockers: number
  open_warnings: number
  reason: string | null
}

export interface ReviewCheckStatusDto {
  run_id: string
  areas: CheckAreaStatusDto[]
  stale: boolean
  blocking_task_count: number
  evidence_note_count: number
  review_package_version: string
}

export const CHECK_AREA_LABELS: Record<CheckAreaKey, string> = {
  pflichtfelder: "Pflichtfelder",
  zeichenlimits: "Zeichenlimits",
  platzhalter: "Platzhalter",
  voraussetzungen: "Fördervoraussetzungen",
  budget: "Budget & Beiträge",
  evidenz_coverage: "Evidenz-Abdeckung",
  evidenz_suffizienz: "Evidenz-Stützung",
  konsistenz: "Inhaltliche Konsistenz",
  export: "Export-/Kopierbereitschaft",
}

export const CHECK_AREA_DESCRIPTIONS: Record<CheckAreaKey, string> = {
  pflichtfelder: "Sind alle Pflichtfelder ausgefüllt?",
  zeichenlimits: "Halten die Texte die Innolink-Zeichenlimits ein?",
  platzhalter: "Enthalten Felder noch offene Platzhalter?",
  voraussetzungen: "Sind die Fördervoraussetzungen erfüllt?",
  budget: "Sind Budget und Beiträge plausibel?",
  evidenz_coverage: "Sind belegpflichtige Aussagen mit Quellen verknüpft?",
  evidenz_suffizienz: "Stützen die verknüpften Quellen die Aussagen inhaltlich?",
  konsistenz: "Sind die Angaben in sich stimmig?",
  export: "Ist der Antrag bereit zum Kopieren nach Innolink?",
}

// Statussprache (CLAUDEX §6): Grün=Bestanden, Orange=Teilweise/Prüfung nötig,
// Rot=Nicht bestanden, Grau=Offen/Nicht geprüft.
export const CHECK_STATE_LABELS: Record<CheckAreaState, string> = {
  not_run: "Nicht geprüft",
  passed: "Bestanden",
  warning: "Teilweise bestanden",
  failed: "Nicht bestanden",
}

export const CHECK_STATE_STYLE: Record<CheckAreaState, string> = {
  not_run: "bg-muted text-muted-foreground",
  passed: "bg-status-fulfilled/12 text-status-fulfilled",
  warning: "bg-status-partial/12 text-status-partial",
  failed: "bg-destructive/10 text-destructive",
}

/** Sonderwortlaut A6: Warnungen blockieren das Kopieren nicht, aber der
 *  Export ist nie grün «fachlich freigegeben», solange Risiken offen sind. */
export function checkStateLabel(area: CheckAreaStatusDto): string {
  if (area.area === "export" && area.status === "warning") {
    return "Mit Warnungen kopierbar"
  }
  return CHECK_STATE_LABELS[area.status]
}

/** Nutzerlesbarer Grund für «Nicht geprüft» (Maschinen-Schlüssel nie roh zeigen). */
export function notRunReasonLabel(area: CheckAreaStatusDto): string {
  if (area.reason === "stale") {
    return "Prüfung veraltet — bitte erneut ausführen."
  }
  return "Diese Prüfung wurde noch nicht ausgeführt."
}

// Ring-Zählwerte über die Prüfbereiche. Ehrlicher Nenner: alle neun Bereiche,
// «Nicht geprüft» ist ein eigenes (graues) Segment — nie stillschweigend grün.
export interface AreaProgress {
  total: number
  bestanden: number
  teilweise: number
  nichtBestanden: number
  nichtGeprueft: number
}

export function areaProgress(areas: CheckAreaStatusDto[]): AreaProgress {
  return {
    total: areas.length,
    bestanden: areas.filter((a) => a.status === "passed").length,
    teilweise: areas.filter((a) => a.status === "warning").length,
    nichtBestanden: areas.filter((a) => a.status === "failed").length,
    nichtGeprueft: areas.filter((a) => a.status === "not_run").length,
  }
}

export async function getCheckStatus(
  runId: string
): Promise<ReviewCheckStatusDto> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/review/check-status`
  )
  if (!res.ok) {
    throw new Error("Der Prüfbereichsstatus konnte nicht geladen werden.")
  }
  return (await res.json()) as ReviewCheckStatusDto
}

/** Lädt die Check-Status-Übersicht; `refreshKey` erzwingt Neuladen (z. B.
 *  neue review_package_version nach Recheck/Freigabe). */
export function useCheckStatus(
  runId: string | null | undefined,
  refreshKey?: string
): { checks: ReviewCheckStatusDto | null; error: string | null } {
  const [checks, setChecks] = React.useState<ReviewCheckStatusDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!runId) {
      setChecks(null)
      return
    }
    let active = true
    getCheckStatus(runId)
      .then((c) => {
        if (!active) return
        setChecks(c)
        setError(null)
      })
      .catch((e) => {
        if (!active) return
        setError(
          e instanceof Error ? e.message : "Prüfbereichsstatus nicht ladbar."
        )
      })
    return () => {
      active = false
    }
  }, [runId, refreshKey])

  return { checks, error }
}
