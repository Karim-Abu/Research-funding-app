// Beta-Session-Store: hält die Intake-Daten und die aktuelle Run-ID im
// sessionStorage des Browsers. Bewusst minimal — kein globaler State,
// keine Persistenz über die Browser-Session hinaus, keine Personendaten
// über das Intake hinaus.
//
// Quelle der Wahrheit: Nach der Projektanlage ist der SERVER die Wahrheit
// (POST /projects, status "draft"). Dieser Store hält für nicht-public
// klassifizierte Projekte NUR die Vertraulichkeitsstufe (R4.4) — nie die
// Projektidee, nie Titel, nie Budgetwerte. Keine neuen Inhalts-Keys anlegen.

import type { IntakeFormData } from "./types"

const INTAKE_KEY = "rf_current_intake"
const RUN_ID_KEY = "rf_current_run_id"
const ACTIVE_PROJECT_KEY = "rf_active_project_id"
const SELECTED_RUN_KEY = "rf_selected_run_id"

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

// R4.4 (Security-P0 S1, Owner-Tabelle §6): nur D0/public darf Inhalte in der
// Browser-Session halten. Für internal/confidential/nda und unklassifiziert
// wird nur die Stufe selbst persistiert — keine Projektidee, kein Titel,
// keine Budgetwerte, keine Partnernamen.
function redactIntake(data: IntakeFormData): IntakeFormData {
  return {
    titel: "",
    projektidee: "",
    innovationsfeld: "",
    vertraulichkeit: data.vertraulichkeit,
  }
}

function hasIntakeContent(data: IntakeFormData): boolean {
  // budgetrahmen/partner sind keine Formularfelder mehr, können aber in
  // Alt-Einträgen im Storage liegen — weiterhin als Inhalt werten (Scrub).
  const legacy = data as unknown as Record<string, unknown>
  return Boolean(
    data.titel ||
      data.projektidee ||
      data.innovationsfeld ||
      legacy.budgetrahmen ||
      (Array.isArray(legacy.partner) && legacy.partner.length > 0)
  )
}

export function saveIntake(data: IntakeFormData): void {
  const value = data.vertraulichkeit === "public" ? data : redactIntake(data)
  storage()?.setItem(INTAKE_KEY, JSON.stringify(value))
}

function normalizeLegacyConfidentiality(value: unknown): IntakeFormData["vertraulichkeit"] {
  if (value === "public_synthetic" || value === "public_external") return "public"
  // R4.1: "nda" ist jetzt eine eigene Stufe (D3) — der frühere Kollaps auf
  // "confidential" war ein stiller Marker-Verlust (Owner-Tabelle §4.1).
  if (
    value === "public" ||
    value === "internal" ||
    value === "confidential" ||
    value === "nda"
  ) {
    return value
  }
  return ""
}

export function loadIntake(): IntakeFormData | null {
  const raw = storage()?.getItem(INTAKE_KEY)
  if (!raw) return null
  try {
    const data = JSON.parse(raw) as IntakeFormData
    const normalized = {
      ...data,
      vertraulichkeit: normalizeLegacyConfidentiality(data.vertraulichkeit),
    }
    // R4.4: Alt-Einträge (vor dem Fix gespeichert) mit Roh-Content für
    // nicht-public sofort bereinigen — Rückgabe UND Storage.
    if (normalized.vertraulichkeit !== "public" && hasIntakeContent(normalized)) {
      const redacted = redactIntake(normalized)
      storage()?.setItem(INTAKE_KEY, JSON.stringify(redacted))
      return redacted
    }
    return normalized
  } catch {
    return null
  }
}

/** R4.4: Logout — entfernt den Intake-Eintrag (Inhalts-Key) vollständig. */
export function clearIntakeSession(): void {
  storage()?.removeItem(INTAKE_KEY)
}

/** R4.4: Projektwechsel — Inhalte leeren, Stufe behalten (das Intake gehört
 *  zum vorherigen Projekt; die Klasse bleibt als restriktives Signal). */
export function redactIntakeInSession(): void {
  const data = loadIntake()
  if (data) storage()?.setItem(INTAKE_KEY, JSON.stringify(redactIntake(data)))
}

/** Mock-only: Run-ID der Mock-Bridge. Live-Screens nutzen die zentrale
 *  Run-Auswahl (lib/active-run.ts) — hier nichts Neues anschliessen. */
export function setCurrentRunId(runId: string): void {
  storage()?.setItem(RUN_ID_KEY, runId)
}

/** Mock-only: gespeicherte Run-ID oder der Bridge-Alias "current". */
export function getCurrentRunId(): string {
  return storage()?.getItem(RUN_ID_KEY) ?? CURRENT_RUN_ID_FALLBACK
}

/** Explizit vom Nutzer gewählter Analyse-Lauf — Stufe 2 der Run-Auswahl-
 *  Ladder (lib/active-run.ts). Nur die ID, keine Inhalte (R4.4). */
export function setSelectedRunId(runId: string): void {
  storage()?.setItem(SELECTED_RUN_KEY, runId)
}

export function getSelectedRunId(): string | null {
  return storage()?.getItem(SELECTED_RUN_KEY) ?? null
}

/** Aktives Projekt (real angelegtes Projekt aus dem Intake). */
export function setActiveProjectId(projectId: string): void {
  storage()?.setItem(ACTIVE_PROJECT_KEY, projectId)
}

export function getActiveProjectId(): string | null {
  return storage()?.getItem(ACTIVE_PROJECT_KEY) ?? null
}
