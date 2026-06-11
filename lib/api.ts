// Zentraler API-Layer der UI. Alle Datenzugriffe laufen über diese
// Funktionen; USE_MOCKS schaltet pro Funktion zwischen Mock-Adapter
// (bestehende Dummy-Daten, simulierte Latenz) und fetch gegen /api/*.
//
// Sicherheitsregeln: keine Secrets/Env-Werte im Client. Die Bridge-URL kennt
// nur der Server (app/api/* liest FASTAPI_BRIDGE_URL); der Client spricht
// ausschließlich relative /api-Pfade an.

import type { Source, AnalysisProgressStep } from "./quellen-mock-data"
import {
  requirements as mockRequirements,
  type Requirement,
} from "./anforderungen-mock-data"
import { RUN_STEP_TEMPLATE } from "./run-steps"
import type { AnalyseSettings } from "./types"

/**
 * Einziger Schalter: true = App läuft vollständig auf Mock-Daten (Demo-Modus).
 * Bewusst eine Code-Konstante, kein Env-Handling im Client.
 */
export const USE_MOCKS = true

// ---------------------------------------------------------------------------
// Fehler-Envelope { error: { code, message } } — message ist deutscher UI-Text.
// ---------------------------------------------------------------------------

export interface ApiErrorEnvelope {
  error: { code: string; message: string }
}

export class ApiError extends Error {
  readonly code: string
  constructor(code: string, message: string) {
    super(message)
    this.name = "ApiError"
    this.code = code
  }
}

export const BRIDGE_UNREACHABLE_MESSAGE =
  "Der Analysedienst ist derzeit nicht erreichbar. Bitte versuchen Sie es später erneut."

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError("network_error", BRIDGE_UNREACHABLE_MESSAGE)
  }
  if (!res.ok) {
    let envelope: ApiErrorEnvelope | null = null
    try {
      envelope = (await res.json()) as ApiErrorEnvelope
    } catch {
      // non-JSON error body -> generic German message below
    }
    throw new ApiError(
      envelope?.error?.code ?? "unknown_error",
      envelope?.error?.message ?? BRIDGE_UNREACHABLE_MESSAGE
    )
  }
  return (await res.json()) as T
}

// ---------------------------------------------------------------------------
// DTOs (UI-seitig; Steps tragen bereits deutsche Labels)
// ---------------------------------------------------------------------------

export type RunStatus = "running" | "completed" | "stopped" | "failed"

export interface RunStatusDto {
  runId: string
  status: RunStatus
  steps: AnalysisProgressStep[]
}

export interface ProjectStateDto {
  projectId: string
  requirements: Requirement[]
}

export interface ExportDto {
  exportId: string
  status: "generating" | "ready" | "error"
  filename?: string
}

// ---------------------------------------------------------------------------
// Mock-Run-Engine: dieselbe sichtbare Progression wie die Demo (~1,2 s pro
// Schritt), aber poll-getrieben und pausierbar — damit die Page identisch
// gegen Mock und echtes Backend funktioniert.
// ---------------------------------------------------------------------------

const MOCK_STEP_MS = 1200

interface MockRun {
  /** Anzahl abgeschlossener Schritte (0..4). */
  completed: number
  paused: boolean
  /** Zeitpunkt, ab dem der nächste Schritt-Fortschritt gerechnet wird. */
  lastAdvance: number
}

const mockRuns = new Map<string, MockRun>()
let mockRunCounter = 0

function advanceMockRun(run: MockRun) {
  if (run.paused) return
  const now = Date.now()
  while (
    run.completed < RUN_STEP_TEMPLATE.length &&
    now - run.lastAdvance >= MOCK_STEP_MS
  ) {
    run.completed += 1
    run.lastAdvance += MOCK_STEP_MS
  }
}

function mockRunDto(runId: string, run: MockRun): RunStatusDto {
  const finished = run.completed >= RUN_STEP_TEMPLATE.length
  return {
    runId,
    status: finished ? "completed" : run.paused ? "stopped" : "running",
    steps: RUN_STEP_TEMPLATE.map((step, i) => ({
      id: step.id,
      label: step.label,
      state:
        i < run.completed
          ? "done"
          : i === run.completed && !finished
            ? "running"
            : "pending",
    })),
  }
}

const mockDelay = (ms = 150) => new Promise((r) => setTimeout(r, ms))

// ---------------------------------------------------------------------------
// Runs (Slice 1: voll verdrahtet)
// ---------------------------------------------------------------------------

export async function startRun(
  settings: AnalyseSettings
): Promise<{ runId: string }> {
  if (USE_MOCKS) {
    await mockDelay()
    mockRunCounter += 1
    const runId = `mock-run-${mockRunCounter}`
    mockRuns.set(runId, { completed: 0, paused: false, lastAdvance: Date.now() })
    return { runId }
  }
  return request<{ runId: string }>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  })
}

export async function getRun(runId: string): Promise<RunStatusDto> {
  if (USE_MOCKS) {
    const run = mockRuns.get(runId)
    if (!run) {
      throw new ApiError("run_not_found", BRIDGE_UNREACHABLE_MESSAGE)
    }
    advanceMockRun(run)
    return mockRunDto(runId, run)
  }
  return request<RunStatusDto>(`/api/runs/${encodeURIComponent(runId)}`)
}

/**
 * Stop/Resume sind im Bridge-Contract noch nicht definiert (kein Endpoint);
 * im Mock-Modus pausiert/weckt das die lokale Run-Engine. Beim Umstieg auf
 * USE_MOCKS=false braucht der Contract einen Stop-Endpoint (offenes Risiko).
 */
export async function stopRun(runId: string): Promise<void> {
  if (USE_MOCKS) {
    const run = mockRuns.get(runId)
    if (run) run.paused = true
    return
  }
  throw new ApiError("not_implemented", BRIDGE_UNREACHABLE_MESSAGE)
}

export async function resumeRun(runId: string): Promise<void> {
  if (USE_MOCKS) {
    const run = mockRuns.get(runId)
    if (run) {
      run.paused = false
      run.lastAdvance = Date.now()
    }
    return
  }
  throw new ApiError("not_implemented", BRIDGE_UNREACHABLE_MESSAGE)
}

// ---------------------------------------------------------------------------
// Projekt-State (Slice 1: voll verdrahtet)
// ---------------------------------------------------------------------------

export async function getProjectState(
  projectId: string
): Promise<ProjectStateDto> {
  if (USE_MOCKS) {
    await mockDelay()
    return { projectId, requirements: mockRequirements }
  }
  return request<ProjectStateDto>(
    `/api/projects/${encodeURIComponent(projectId)}/state`
  )
}

// ---------------------------------------------------------------------------
// Spätere Slices: Signaturen + Mock-Verhalten, Route-Handler sind 501-Stubs.
// ---------------------------------------------------------------------------

export async function uploadSource(file: File): Promise<Source> {
  if (USE_MOCKS) {
    await mockDelay(400)
    return {
      id: `upload-${Date.now()}`,
      name: `${file.name} (Dummy)`,
      type: "PDF",
      status: "processing",
      addedBy: "Anna Keller",
      addedAt: "soeben",
    }
  }
  const body = new FormData()
  body.append("file", file)
  return request<Source>("/api/sources", { method: "POST", body })
}

export async function patchSection(
  fieldId: string,
  text: string
): Promise<{ fieldId: string; charCount: number }> {
  if (USE_MOCKS) {
    await mockDelay()
    return { fieldId, charCount: text.trimEnd().length }
  }
  return request(`/api/sections/${encodeURIComponent(fieldId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  })
}

export async function acceptSuggestion(
  suggestionId: string
): Promise<{ suggestionId: string }> {
  if (USE_MOCKS) {
    await mockDelay()
    return { suggestionId }
  }
  return request(`/api/suggestions/${encodeURIComponent(suggestionId)}/accept`, {
    method: "POST",
  })
}

export async function createExport(
  kind: "word" | "markdown" | "json_audit"
): Promise<ExportDto> {
  if (USE_MOCKS) {
    await mockDelay(300)
    return { exportId: `mock-export-${kind}`, status: "generating" }
  }
  return request<ExportDto>("/api/exports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind }),
  })
}

export async function getExport(exportId: string): Promise<ExportDto> {
  if (USE_MOCKS) {
    await mockDelay()
    return { exportId, status: "ready", filename: "Antrag_ENTWURF.docx (Dummy)" }
  }
  return request<ExportDto>(`/api/exports/${encodeURIComponent(exportId)}`)
}
