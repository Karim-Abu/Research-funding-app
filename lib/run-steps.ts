// Mapping zwischen Backend-Workflow (LangGraph-Nodes, Pydantic-Schemas aus
// research-funding-mvp) und den deutschsprachigen UI-Shapes. Reine
// Zuordnung/Konvertierung — keine Netzwerk-Logik, keine UI-Strings ändern.

import type { AnalysisProgressStep } from "./quellen-mock-data"
import type {
  EvidenceChip,
  Requirement,
  RequirementGroup,
} from "./anforderungen-mock-data"
import type { RunPhaseDto, RunPhaseKey } from "./runs"
import type { MachineStatus } from "./types"

// ---------------------------------------------------------------------------
// Persistierte Run-Phasen (GET /runs/{id}/phases) -> deutsche Anzeige.
// Der EINZIGE Katalog für den Live-Pfad — kein erfundener Prozentwert,
// keine Schwellen-Heuristik: Status/Zähler kommen 1:1 aus dem Backend.
// ---------------------------------------------------------------------------

export const RUN_PHASE_LABELS: Record<RunPhaseKey, string> = {
  prepare_documents: "Unterlagen vorbereiten",
  detect_facts: "Fakten und Anforderungen erkennen",
  formal_checks: "Formale Prüfungen",
  web_research: "Recherche vorbereiten und ausführen",
  draft_fields: "Feldvorschläge erstellen",
  quality_review: "Qualität und Konsistenz prüfen",
}

export interface RunPhaseView {
  key: RunPhaseKey
  label: string
  state: "pending" | "running" | "done" | "failed" | "skipped"
  /** Echte Zähler/Skip-Gründe in Klartext (nie Roh-Codes). */
  info?: string
  /** Deutsche Fehlermeldung, nur bei state === "failed". */
  error?: string
  durationSeconds?: number
}

const SKIP_REASON_TEXT: Record<string, string> = {
  web_research_not_requested: "Webrecherche nicht aktiviert",
  web_research_unavailable: "Dienst derzeit nicht verfügbar",
  web_research_class_blocked:
    "Für diese Vertraulichkeitsstufe deaktiviert",
  approval_required: "Freigabe der Suchanfrage erforderlich",
}

const PHASE_ERROR_TEXT: Record<string, string> = {
  a2_all_failed: "Es konnten keine Feldvorschläge erstellt werden.",
  // Anforderung 13: kein Sackgassen-Fehler — der manuelle Weg wird genannt.
  web_research_failed:
    "Die Webrecherche ist fehlgeschlagen. Sie können Quellen manuell hinzufügen (URL oder Datei).",
}

function num(detail: Record<string, unknown>, key: string): number | null {
  const value = detail[key]
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function phaseInfo(phase: RunPhaseDto): string | undefined {
  const detail = phase.detail ?? {}
  if (phase.status === "skipped") {
    const reason = String(detail.reason ?? "")
    return SKIP_REASON_TEXT[reason] ?? "Übersprungen"
  }
  switch (phase.phase_key) {
    case "prepare_documents": {
      const sources = num(detail, "sources_frozen")
      if (sources === null) return undefined
      const base = sources === 1 ? "1 Quelle" : `${sources} Quellen`
      return detail.intake_description && sources === 0
        ? "Projektbeschreibung aus dem Intake"
        : base
    }
    case "detect_facts": {
      const facts = num(detail, "facts_created")
      return facts === null
        ? undefined
        : `${facts} ${facts === 1 ? "Fakt" : "Fakten"} erkannt`
    }
    case "formal_checks": {
      const blocker = num(detail, "blocker")
      const warning = num(detail, "warning")
      if (blocker === null && warning === null) return undefined
      return `${blocker ?? 0} Blocker, ${warning ?? 0} Hinweise`
    }
    case "web_research": {
      const queries = num(detail, "web_queries")
      const results = num(detail, "results_found")
      if (queries === null) return undefined
      return `${queries} Suchanfragen, ${results ?? 0} Treffer`
    }
    case "draft_fields": {
      const suggestions = num(detail, "suggestions_created")
      if (suggestions === null) return undefined
      if (detail.a2_status === "skipped") return "ohne KI-Vorschläge"
      const base = `${suggestions} ${suggestions === 1 ? "Vorschlag" : "Vorschläge"} erstellt`
      return detail.budget_stop
        ? `${base} — Limit erreicht, weitere Felder übersprungen`
        : base
    }
    case "quality_review": {
      if (detail.a3_status === "skipped") return "ohne KI-Prüfung"
      const findings = num(detail, "agent_findings")
      return findings === null
        ? undefined
        : `${findings} ${findings === 1 ? "Hinweis" : "Hinweise"} der KI-Prüfung`
    }
  }
}

function phaseError(phase: RunPhaseDto): string | undefined {
  if (phase.status !== "failed") return undefined
  const mapped = PHASE_ERROR_TEXT[phase.error_code ?? ""]
  if (mapped) return mapped
  if (phase.phase_key === "quality_review") {
    return "Die KI-Qualitätsprüfung ist fehlgeschlagen — die Feldvorschläge bleiben erhalten."
  }
  return "Dieser Schritt ist fehlgeschlagen."
}

function phaseDuration(phase: RunPhaseDto): number | undefined {
  if (!phase.started_at || !phase.ended_at) return undefined
  const seconds =
    (new Date(phase.ended_at).getTime() -
      new Date(phase.started_at).getTime()) /
    1000
  return Number.isFinite(seconds) && seconds >= 0
    ? Math.round(seconds)
    : undefined
}

const PHASE_STATE: Record<RunPhaseDto["status"], RunPhaseView["state"]> = {
  pending: "pending",
  running: "running",
  succeeded: "done",
  failed: "failed",
  skipped: "skipped",
}

/** Map die persistierten Backend-Phasen auf die Anzeige — 1:1, ohne Raten. */
export function phasesToView(phases: RunPhaseDto[]): RunPhaseView[] {
  return phases.map((phase) => ({
    key: phase.phase_key,
    label: RUN_PHASE_LABELS[phase.phase_key] ?? phase.phase_key,
    state: PHASE_STATE[phase.status] ?? "pending",
    info: phaseInfo(phase),
    error: phaseError(phase),
    durationSeconds: phaseDuration(phase),
  }))
}

/** Label der fehlgeschlagenen Phase (für «Teilweise abgeschlossen — …»). */
export function failedPhaseLabel(phases: RunPhaseDto[]): string | null {
  const failed = phases.find((p) => p.status === "failed")
  return failed ? (RUN_PHASE_LABELS[failed.phase_key] ?? null) : null
}

// ---------------------------------------------------------------------------
// Backend-Node -> Klartext-Schritt
// Die 15 Pre-Review-Nodes werden auf die 4 Banner-Schritte abgebildet.
// Granularität ist bewusst grob; Vollständigkeit ist ein bekanntes Risiko
// für den nächsten Slice (Nodes können im Backend dazukommen).
// ---------------------------------------------------------------------------

export const RUN_STEP_TEMPLATE: ReadonlyArray<{ id: string; label: string }> = [
  { id: "as1", label: "Quellen werden aufbereitet" },
  { id: "as2", label: "Anforderungen werden erkannt" },
  { id: "as3", label: "Belege werden verknüpft" },
  { id: "as4", label: "Qualität wird geprüft" },
]

/**
 * Backend node name -> index into RUN_STEP_TEMPLATE.
 * Beta-Node-Set (laut beta_architecture); die alte 16-Agenten-Liste ist
 * entfernt. Nur Fallback — die Bridge liefert bevorzugt steps[] direkt.
 */
const NODE_TO_STEP_INDEX: Record<string, number> = {
  // Schritt 1: Quellen werden aufbereitet
  intake: 0,
  intake_and_classification: 0,
  source_load: 0,
  source_ingestion: 0,
  // Schritt 2: Anforderungen werden erkannt
  requirement_loader: 1,
  requirement_mapper: 1,
  rule_engine: 1,
  budget_rule_engine: 1,
  eligibility_rule_engine: 1,
  // Schritt 3: Belege werden verknüpft
  evidence_anchor: 2,
  evidence_anchor_builder: 2,
  portal_field_dispatcher: 2,
  dispatcher: 2,
  field_drafting_agent: 2,
  critic_verifier_agent: 2,
  innovation_challenger_profile: 2,
  // Schritt 4: Qualität wird geprüft
  hitl_review_gate: 3,
  gates: 3,
  export: 3,
}

/**
 * Fallback-Mapping, nur wenn die Bridge keine steps[] liefert.
 * Bekannte Nodes werden auf die vier Klartext-Schritte gelegt; UNBEKANNTE
 * Nodes werden nicht still einsortiert, sondern als sichtbarer technischer
 * Schritt angehängt — die UI zeigt damit ehrlich einen unkartierten
 * Backend-Schritt an.
 */
export function stepsFromBackendNode(
  currentNode: string | null
): AnalysisProgressStep[] {
  const baseSteps = (runningIndex: number): AnalysisProgressStep[] =>
    RUN_STEP_TEMPLATE.map((step, i) => ({
      id: step.id,
      label: step.label,
      state:
        i < runningIndex ? "done" : i === runningIndex ? "running" : "pending",
    }))

  if (currentNode === null) {
    // finished -> everything done
    return baseSteps(RUN_STEP_TEMPLATE.length)
  }

  const knownIndex = NODE_TO_STEP_INDEX[currentNode]
  if (knownIndex !== undefined) {
    return baseSteps(knownIndex)
  }

  return [
    ...baseSteps(RUN_STEP_TEMPLATE.length),
    {
      id: "fallback",
      label: `Technischer Schritt: ${currentNode}`,
      state: "running",
    },
  ]
}

// ---------------------------------------------------------------------------
// Backend-WorkflowState -> UI-Requirements
// Toleranter Mapper gegen die dokumentierten Pydantic-Felder
// (requirement_matrix.eligibility_criteria / budget_rules, evidence_anchors).
// Felder, die der Bridge-Contract noch nicht garantiert, fallen sicher zurück.
// ---------------------------------------------------------------------------

interface BackendCriterion {
  id?: string
  requirement_id?: string
  title?: string
  name?: string
  reason?: string
  summary?: string
  detail?: string
  description?: string
  status?: string
  group?: string
}

interface BackendEvidenceAnchor {
  anchor_id?: string
  requirement_id?: string
  claim?: string
  source_id?: string
  verified?: boolean
}

const BACKEND_STATUS_TO_MACHINE: Record<string, MachineStatus> = {
  verified: "verified",
  passed: "verified",
  plausible: "verified",
  partial: "partial",
  warning: "partial",
  unclear: "partial",
  open: "open",
  needs_review: "open",
  blocker: "blocker",
  blocked: "blocker",
}

function toMachineStatus(value: string | undefined): MachineStatus {
  return BACKEND_STATUS_TO_MACHINE[(value ?? "").toLowerCase()] ?? "open"
}

const BACKEND_GROUP_TO_UI: Record<string, RequirementGroup> = {
  eligibility: "Fördervoraussetzungen",
  portal_fields: "Pflichtfelder des Beta-Profils",
  budget: "Budget-Prüfung",
  fit_gap: "Passung & Lücken",
}

function toGroup(value: string | undefined): RequirementGroup {
  return BACKEND_GROUP_TO_UI[(value ?? "").toLowerCase()] ?? "Passung & Lücken"
}

/**
 * Map a bridge project-state payload to the UI Requirement shape.
 * Anchors are matched to criteria by requirement_id; without a match the row
 * shows the existing "Kein Beleg gefunden" treatment (evidence: null).
 */
export function mapBackendRequirements(payload: {
  requirement_matrix?: {
    eligibility_criteria?: BackendCriterion[]
    budget_rules?: BackendCriterion[]
  }
  evidence_anchors?: BackendEvidenceAnchor[]
}): Requirement[] {
  const anchors = payload.evidence_anchors ?? []

  function evidenceFor(requirementId: string): EvidenceChip | null {
    const anchor = anchors.find((a) => a.requirement_id === requirementId)
    if (!anchor) return null
    return {
      label: anchor.claim ? `Beleg: ${anchor.claim}` : "Beleg",
      evidenceCardId: anchor.anchor_id ?? "",
    }
  }

  function mapCriterion(
    c: BackendCriterion,
    index: number,
    fallbackGroup: RequirementGroup
  ): Requirement {
    const id = c.id ?? c.requirement_id ?? `req-${index}`
    return {
      id,
      group: c.group ? toGroup(c.group) : fallbackGroup,
      title: c.title ?? c.name ?? "Anforderung",
      reason: c.reason ?? c.summary ?? "",
      detail: c.detail ?? c.description ?? c.summary ?? "",
      machineStatus: toMachineStatus(c.status),
      evidence: evidenceFor(id),
    }
  }

  const eligibility = (payload.requirement_matrix?.eligibility_criteria ?? []).map(
    (c, i) => mapCriterion(c, i, "Fördervoraussetzungen")
  )
  const budget = (payload.requirement_matrix?.budget_rules ?? []).map((c, i) =>
    mapCriterion(c, eligibility.length + i, "Budget-Prüfung")
  )
  return [...eligibility, ...budget]
}
