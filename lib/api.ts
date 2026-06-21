// Zentraler API-Layer der UI. Alle Datenzugriffe laufen über diese
// Funktionen; der App-Mode schaltet pro Funktion zwischen Mock-Adapter
// (bestehende Dummy-Daten, simulierte Latenz) und fetch gegen /api/*.
//
// Sicherheitsregeln: keine Secrets/Env-Werte im Client. Die Bridge-URL kennt
// nur der Server (app/api/* liest FASTAPI_BRIDGE_URL); der Client spricht
// ausschließlich relative /api-Pfade an.

import type { Source } from "./quellen-mock-data"
import {
  requirements as mockRequirements,
  type Requirement,
} from "./anforderungen-mock-data"
import { portalSections, draftText } from "./editor-data"
import { currentUser } from "./mock-data"
import { RUN_STEP_TEMPLATE, stepsFromBackendNode } from "./run-steps"
import { isMock } from "./app-mode"
import type {
  EvidenceAnchorDto,
  ExportKind,
  FeedbackDto,
  GateRowDto,
  IssueDto,
  PortalFieldDraftDto,
  ReviewDecisionDto,
  RunFieldsDto,
  RunStartRequestDto,
  RunStatusDto,
} from "./backend-contract"

// Der DTO-Contract lebt in lib/backend-contract.ts; bestehende Importe aus
// "@/lib/api" bleiben über diese Re-Exports gültig.
export type {
  EvidenceAnchorDto,
  ExportKind,
  FeedbackDto,
  FieldDraftStatus,
  GateRowDto,
  IssueDto,
  IssueSeverity,
  PortalFieldDraftDto,
  ReviewDecisionDto,
  RunFieldsDto,
  RunStartRequestDto,
  RunStatus,
  RunStatusDto,
  RunStepDto,
  RunCostDto,
} from "./backend-contract"

// Mock vs. live wird zentral über den serverseitig gesteuerten App-Mode
// entschieden (lib/app-mode.ts). Diese Slices sind in Milestone 1 noch nicht
// live verdrahtet; `isMock("legacy")` ist daher stets true, bis ihr Backend
// folgt. Es gibt bewusst keinen zweiten, unabhängigen USE_MOCKS-Schalter mehr.

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
// UI-seitige DTOs (nicht Teil des Bridge-Contracts)
// ---------------------------------------------------------------------------

export interface ProjectStateDto {
  projectId: string
  requirements: Requirement[]
}

/**
 * Normalisierung für das Fortschritts-Banner: liefert die Bridge `steps[]`,
 * werden sie direkt verwendet; nur als Fallback wird aus `currentNode`
 * gemappt (unbekannte Nodes erscheinen sichtbar als technischer Schritt).
 */
export function normalizeRunStatus(dto: RunStatusDto): RunStatusDto {
  if (dto.steps && dto.steps.length > 0) return dto
  return { ...dto, steps: stepsFromBackendNode(dto.currentNode ?? null) }
}

// ---------------------------------------------------------------------------
// Mock-Run-Engine: dieselbe sichtbare Progression wie die Demo (~1,2 s pro
// Schritt), aber poll-getrieben und pausierbar — damit die Page identisch
// gegen Mock und echtes Backend funktioniert.
// ---------------------------------------------------------------------------

const MOCK_STEP_MS = 1200
/** Simulierte Kosten pro Schritt (CHF) — realistisch: ~CHF 0.60 pro Lauf. */
const MOCK_COST_PER_STEP = 0.15

interface MockRun {
  /** Anzahl abgeschlossener Schritte (0..4). */
  completed: number
  paused: boolean
  /** Zeitpunkt, ab dem der nächste Schritt-Fortschritt gerechnet wird. */
  lastAdvance: number
  /** Kostenlimit aus den Analyse-Einstellungen. */
  costLimit: number
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
  const usedChf =
    Math.round(run.completed * MOCK_COST_PER_STEP * 100) / 100
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
    cost: {
      usedChf: Math.min(usedChf, run.costLimit),
      limitChf: run.costLimit,
      estimated: true,
    },
    ...(run.paused && !finished
      ? { stopReason: "cost_limit" as const, canResume: true }
      : {}),
  }
}

const mockDelay = (ms = 150) => new Promise((r) => setTimeout(r, ms))

// ---------------------------------------------------------------------------
// Runs (Slice 1: voll verdrahtet)
// ---------------------------------------------------------------------------

export async function startRun(
  startRequest: RunStartRequestDto
): Promise<{ runId: string }> {
  if (isMock("legacy")) {
    await mockDelay()
    mockRunCounter += 1
    const runId = `mock-run-${mockRunCounter}`
    const { costLimit } = startRequest.settings
    mockRuns.set(runId, {
      completed: 0,
      paused: false,
      lastAdvance: Date.now(),
      costLimit: costLimit > 0 ? costLimit : 2,
    })
    return { runId }
  }
  return request<{ runId: string }>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(startRequest),
  })
}

export async function getRun(runId: string): Promise<RunStatusDto> {
  if (isMock("legacy")) {
    const run = mockRuns.get(runId)
    if (!run) {
      throw new ApiError("run_not_found", BRIDGE_UNREACHABLE_MESSAGE)
    }
    advanceMockRun(run)
    return mockRunDto(runId, run)
  }
  const dto = await request<RunStatusDto>(
    `/api/runs/${encodeURIComponent(runId)}`
  )
  return normalizeRunStatus(dto)
}

export async function stopRun(runId: string): Promise<void> {
  if (isMock("legacy")) {
    const run = mockRuns.get(runId)
    if (run) run.paused = true
    return
  }
  await request(`/api/runs/${encodeURIComponent(runId)}/stop`, {
    method: "POST",
  })
}

export async function resumeRun(runId: string): Promise<void> {
  if (isMock("legacy")) {
    const run = mockRuns.get(runId)
    if (run) {
      run.paused = false
      run.lastAdvance = Date.now()
    }
    return
  }
  await request(`/api/runs/${encodeURIComponent(runId)}/resume`, {
    method: "POST",
  })
}

// ---------------------------------------------------------------------------
// Projekt-State (Slice 1: voll verdrahtet)
// ---------------------------------------------------------------------------

export async function getProjectState(
  projectId: string
): Promise<ProjectStateDto> {
  if (isMock("legacy")) {
    await mockDelay()
    return { projectId, requirements: mockRequirements }
  }
  return request<ProjectStateDto>(
    `/api/projects/${encodeURIComponent(projectId)}/state`
  )
}

// ---------------------------------------------------------------------------
// Review: Feldentwürfe + Issues.
// Mock-Singleton — wird von Review-Entscheidungen mutiert, damit Review und
// Export denselben Stand sehen. Real: GET/POST /api/runs/{id}/fields|review.
// ---------------------------------------------------------------------------

const MOCK_ANCHORS: Record<string, EvidenceAnchorDto> = {
  a1: {
    anchorId: "a1",
    sourceTitle: "McKinsey Materials Report 2023 (Dummy)",
    location: "S. 12, Abb. 4",
    verified: true,
  },
  a2: {
    anchorId: "a2",
    sourceTitle: "Marktstudie Verbundwerkstoffe (Dummy)",
    location: "S. 4",
    verified: false,
  },
  a3: {
    anchorId: "a3",
    sourceTitle: "Interne Wirtschaftlichkeitsrechnung (Dummy)",
    location: "S. 8, Tab. 2",
    verified: true,
  },
  a4: {
    anchorId: "a4",
    sourceTitle: "Pilotbericht Industriekunde (Dummy)",
    location: "Abschnitt 3",
    verified: false,
  },
}

const FIELD_TEXTS: Record<string, string> = {
  "value-creation": draftText,
  // Bewusst über dem Limit von 3000 Zeichen -> Zeichenlimit-Blocker (i1).
  innovation:
    "Die Innovation kombiniert recyclingfähige Matrixwerkstoffe mit einem datengetriebenen Prozessmodell und hebt sich damit vom Stand der Technik ab (Dummy). ".repeat(
      20
    ),
  feasibility:
    "Der Arbeitsplan umfasst vier Arbeitspakete über 18 Monate mit klaren Meilensteinen und definierten Abbruchkriterien (Dummy).",
  team: "Das Kernteam vereint Werkstoffwissenschaft, Datenanalyse und industrielle Fertigung; die Projektleitung hat zwei vergleichbare Vorhaben geführt (Dummy).",
  partners:
    "Der Umsetzungspartner bringt eine Pilotlinie für Verbundwerkstoffe sowie Zugang zu Industriekunden ein (Dummy).",
  budget:
    "Die Mittel verteilen sich auf Personal, Material und Pilotversuche; die Eigenleistung trägt der Umsetzungspartner (Dummy).",
  impact:
    "Das Vorhaben reduziert Materialeinsatz und verbessert die Recyclingfähigkeit in der Zielbranche (Dummy).",
}

const FIELD_EVIDENCE: Record<string, EvidenceAnchorDto[]> = {
  "value-creation": [MOCK_ANCHORS.a1, MOCK_ANCHORS.a2],
  innovation: [MOCK_ANCHORS.a1],
  feasibility: [MOCK_ANCHORS.a3],
  team: [],
  partners: [MOCK_ANCHORS.a4],
  budget: [MOCK_ANCHORS.a3],
  impact: [],
}

/** Issues, die der Mock-Re-Check automatisch gegen das Zeichenlimit prüft. */
const CHAR_LIMIT_ISSUE_IDS = new Set(["i1"])

// Mock-Issues bilden echte Innosuisse-Innovationsprojekt-Regeln ab —
// keine erfundenen Kriterien, die ein falsches mentales Modell lehren.
function seedIssues(): IssueDto[] {
  return [
    {
      id: "i1",
      fieldId: "innovation",
      severity: "blocker",
      title: "Zeichenlimit überschritten",
      description:
        "Der Text überschreitet das Zeichenlimit des Portalfelds. Kürzen Sie den Text und wählen Sie danach „Änderungen prüfen“.",
      state: "open",
    },
    {
      id: "i2",
      fieldId: "budget",
      severity: "blocker",
      title: "Cash Contribution unter 5 %",
      description:
        "Die geplante Barleistung des Umsetzungspartners liegt unter der erforderlichen Mindestquote von 5 % der Projektkosten (Dummy).",
      evidence: [MOCK_ANCHORS.a3],
      state: "open",
    },
    {
      id: "i3",
      fieldId: "partners",
      severity: "warning",
      title: "Implementation Partner Contribution: 40–60-%-Quote prüfen",
      description:
        "Der ausgewiesene Beitrag des Umsetzungspartners liegt nahe der Bereichsgrenze von 40–60 % der Projektkosten — bitte Quote prüfen und belegen (Dummy).",
      evidence: [MOCK_ANCHORS.a3],
      state: "open",
    },
    {
      id: "i4",
      fieldId: "value-creation",
      severity: "warning",
      title: "Kernaussage ohne Beleg",
      description:
        "Die Aussage zur Marktgrösse ist nicht mit einem Beleg verknüpft. Für dieses Feld werden Belege erwartet (Dummy).",
      evidence: [MOCK_ANCHORS.a1],
      state: "open",
    },
    {
      id: "i5",
      fieldId: "impact",
      severity: "warning",
      title: "Innovationsnutzen zu forschungslastig formuliert",
      description:
        "Der Abschnitt betont den Forschungsbeitrag; Innosuisse erwartet den wirtschaftlichen Nutzen der Innovation im Vordergrund (Dummy).",
      state: "open",
    },
    {
      id: "i6",
      fieldId: "value-creation",
      severity: "info",
      title: "Formulierung prüfen",
      description:
        "Der Einstiegssatz wiederholt den Feldtitel; eine direktere Formulierung wirkt stärker (Dummy).",
      state: "open",
    },
    {
      id: "i7",
      fieldId: "budget",
      severity: "info",
      title: "Abkürzung einführen",
      description:
        "Die Abkürzung „F&E“ wird verwendet, ohne sie beim ersten Auftreten auszuschreiben (Dummy).",
      state: "open",
    },
  ]
}

interface MockReviewState {
  fields: PortalFieldDraftDto[]
  issues: IssueDto[]
}

let mockReview: MockReviewState | null = null

function fieldStatusFor(
  fieldId: string,
  issues: IssueDto[]
): PortalFieldDraftDto["status"] {
  const open = issues.filter((i) => i.fieldId === fieldId && i.state === "open")
  if (open.some((i) => i.severity === "blocker")) return "blocked"
  if (open.some((i) => i.severity === "warning")) return "needs_review"
  return "ready"
}

function recomputeFieldStatuses(state: MockReviewState) {
  for (const field of state.fields) {
    field.status = fieldStatusFor(field.fieldId, state.issues)
  }
}

/** Mock-Re-Check: Zeichenlimit-Blocker lösen sich auf, wenn der Text passt. */
function recheckCharLimits(state: MockReviewState) {
  for (const issue of state.issues) {
    if (!CHAR_LIMIT_ISSUE_IDS.has(issue.id) || issue.state !== "open") continue
    const field = state.fields.find((f) => f.fieldId === issue.fieldId)
    if (
      field &&
      field.charLimit !== null &&
      field.text.trimEnd().length <= field.charLimit
    ) {
      issue.state = "confirmed"
    }
  }
}

function ensureMockReview(): MockReviewState {
  if (!mockReview) {
    const issues = seedIssues()
    const fields: PortalFieldDraftDto[] = portalSections.map((s) => ({
      fieldId: s.id,
      name: s.name,
      text: FIELD_TEXTS[s.id] ?? "",
      charLimit: s.charLimit,
      status: fieldStatusFor(s.id, issues),
      evidence: FIELD_EVIDENCE[s.id] ?? [],
    }))
    mockReview = { fields, issues }
  }
  return mockReview
}

/**
 * Qualitätsprüfungen aus dem aktuellen Issue-Stand ableiten. Wird vom Mock
 * verwendet UND von der UI als Fallback, wenn die Bridge keine gates[]
 * liefert — so stehen nie erfundene Gate-Ergebnisse neben echten Feldern.
 */
export function deriveGatesFromIssues(issues: IssueDto[]): GateRowDto[] {
  const open = (filter: (i: IssueDto) => boolean) =>
    issues.some((i) => i.state === "open" && filter(i))
  const overridden = (filter: (i: IssueDto) => boolean) =>
    issues.some((i) => i.state === "overridden" && filter(i))

  const isCharLimit = (i: IssueDto) => CHAR_LIMIT_ISSUE_IDS.has(i.id)
  const isBudgetBlocker = (i: IssueDto) =>
    i.severity === "blocker" && i.fieldId === "budget"
  const isEvidenceWarning = (i: IssueDto) =>
    i.severity === "warning" && (i.evidence?.length ?? 0) > 0

  return [
    {
      id: "g1",
      label: "Alle Pflichtfelder ausgefüllt",
      status: "passed",
      result: "Alle Pflichtfelder enthalten Text.",
      detail:
        "Jedes Pflichtfeld des Beta-Profils enthält einen Entwurfstext (Dummy).",
    },
    {
      id: "g2",
      label: "Zeichenlimits eingehalten",
      status: open(isCharLimit) ? "failed" : "passed",
      result: open(isCharLimit)
        ? "Ein Feld überschreitet das Zeichenlimit."
        : "Alle Felder liegen innerhalb der Zeichenlimits.",
      detail:
        "Die Plattform prüft die Textlänge jedes Felds gegen das Portallimit (Dummy).",
    },
    {
      id: "g3",
      label: "Budget im Rahmen",
      status: open(isBudgetBlocker)
        ? "failed"
        : overridden(isBudgetBlocker)
          ? "partial"
          : "passed",
      result: open(isBudgetBlocker)
        ? "Eine Budgetregel ist verletzt."
        : overridden(isBudgetBlocker)
          ? "Budgetregel mit Kommentar überschrieben."
          : "Budgetregeln sind eingehalten.",
      detail:
        "Geprüft werden u. a. die Cash Contribution (mind. 5 %) und die Partner-Quote (Dummy).",
    },
    {
      id: "g4",
      label: "Belege für Kernaussagen vorhanden",
      status: open(isEvidenceWarning) ? "partial" : "passed",
      result: open(isEvidenceWarning)
        ? "Kernaussagen ohne verknüpften Beleg vorhanden."
        : "Kernaussagen sind mit Belegen verknüpft.",
      detail:
        "Felder mit Belegpflicht müssen ihre zentralen Aussagen mit Quellen verknüpfen (Dummy).",
    },
  ]
}

function cloneReview(runId: string, state: MockReviewState): RunFieldsDto {
  return structuredClone({
    runId,
    fields: state.fields,
    issues: state.issues,
    gates: deriveGatesFromIssues(state.issues),
  })
}

/** Offene, nicht überschriebene Blocker — Gating für Freigabe und Export. */
export function countOpenBlockers(issues: IssueDto[]): number {
  return issues.filter((i) => i.severity === "blocker" && i.state === "open")
    .length
}

export async function getRunFields(runId: string): Promise<RunFieldsDto> {
  if (isMock("legacy")) {
    await mockDelay(250)
    return cloneReview(runId, ensureMockReview())
  }
  return request<RunFieldsDto>(
    `/api/runs/${encodeURIComponent(runId)}/fields`
  )
}

export async function submitReview(
  runId: string,
  decision: ReviewDecisionDto
): Promise<RunFieldsDto> {
  if (isMock("legacy")) {
    await mockDelay(800)
    const state = ensureMockReview()
    for (const edit of decision.fieldEdits ?? []) {
      const field = state.fields.find((f) => f.fieldId === edit.fieldId)
      if (field) field.text = edit.text
    }
    for (const d of decision.decisions) {
      const issue = state.issues.find((i) => i.id === d.issueId)
      if (!issue) continue
      if (d.action === "confirm") {
        issue.state = "confirmed"
      } else {
        issue.state = "overridden"
        issue.overrideComment = d.comment
        // Mock-only: im Real-Modus liefert das Backend den Namen oder
        // lässt das Feld weg.
        issue.overriddenBy = currentUser.name
      }
    }
    recheckCharLimits(state)
    recomputeFieldStatuses(state)
    return cloneReview(runId, state)
  }
  return request<RunFieldsDto>(
    `/api/runs/${encodeURIComponent(runId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    }
  )
}

export async function redraftField(
  runId: string,
  fieldId: string
): Promise<RunFieldsDto> {
  if (isMock("legacy")) {
    await mockDelay(900)
    const state = ensureMockReview()
    const field = state.fields.find((f) => f.fieldId === fieldId)
    if (field) {
      field.text = `Neuer Entwurf (Dummy): ${FIELD_TEXTS[fieldId] ?? field.text}`
      field.status = "needs_review"
    }
    return cloneReview(runId, state)
  }
  return request<RunFieldsDto>(
    `/api/runs/${encodeURIComponent(runId)}/redraft`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fieldId }),
    }
  )
}

// ---------------------------------------------------------------------------
// Beta-Feedback (keine personenbezogenen Daten; Mock speichert nichts)
// ---------------------------------------------------------------------------

export async function submitFeedback(feedback: FeedbackDto): Promise<void> {
  if (isMock("legacy")) {
    await mockDelay(400)
    return
  }
  await request("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(feedback),
  })
}

// ---------------------------------------------------------------------------
// Spätere Slices: Signaturen + Mock-Verhalten, Route-Handler sind 501-Stubs.
// ---------------------------------------------------------------------------

export async function uploadSource(file: File): Promise<Source> {
  if (isMock("legacy")) {
    await mockDelay(400)
    return {
      id: `upload-${Date.now()}`,
      name: `${file.name} (Dummy)`,
      type: "Text",
      status: "processing",
      // Mock-only: im Real-Modus liefert das Backend die Person.
      addedBy: currentUser.name,
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
  if (isMock("legacy")) {
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
  if (isMock("legacy")) {
    await mockDelay()
    return { suggestionId }
  }
  return request(`/api/suggestions/${encodeURIComponent(suggestionId)}/accept`, {
    method: "POST",
  })
}

// Ein Export-Pfad: GET /api/runs/{id}/export liefert das Binary direkt —
// es gibt bewusst kein POST /api/exports und keinen Generating-Status.
/** Download-URL für den Binary-Export (Real-Modus: Anchor auf diese URL). */
export function exportDownloadUrl(runId: string, kind: ExportKind): string {
  return `/api/runs/${encodeURIComponent(runId)}/export?kind=${encodeURIComponent(kind)}`
}
