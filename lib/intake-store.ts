// Beta-Session-Store: hält die Intake-Daten und die aktuelle Run-ID im
// sessionStorage des Browsers. Bewusst minimal — kein globaler State,
// keine Persistenz über die Browser-Session hinaus, keine Personendaten
// über das Intake hinaus.

import type { IntakeFormData } from "./types"

const INTAKE_KEY = "rf_current_intake"
const RUN_ID_KEY = "rf_current_run_id"

/**
 * Alias, den die Bridge serverseitig auf den letzten Durchlauf des Projekts
 * auflöst — Fallback, wenn keine Run-ID in der Session liegt.
 */
export const CURRENT_RUN_ID_FALLBACK = "current"

function storage(): Storage | null {
  if (typeof window === "undefined") return null
  try {
    return window.sessionStorage
  } catch {
    // Storage kann blockiert sein (z. B. Privacy-Einstellungen).
    return null
  }
}

export function saveIntake(data: IntakeFormData): void {
  storage()?.setItem(INTAKE_KEY, JSON.stringify(data))
}

export function loadIntake(): IntakeFormData | null {
  const raw = storage()?.getItem(INTAKE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as IntakeFormData
  } catch {
    return null
  }
}

export function setCurrentRunId(runId: string): void {
  storage()?.setItem(RUN_ID_KEY, runId)
}

/** Gespeicherte Run-ID oder der Bridge-Alias "current". */
export function getCurrentRunId(): string {
  return storage()?.getItem(RUN_ID_KEY) ?? CURRENT_RUN_ID_FALLBACK
}
