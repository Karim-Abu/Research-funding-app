// Mapping zwischen Backend-Workflow (LangGraph-Nodes, Pydantic-Schemas aus
// research-funding-mvp) und den deutschsprachigen UI-Shapes. Reine
// Zuordnung/Konvertierung — keine Netzwerk-Logik, keine UI-Strings ändern.

import type { AnalysisProgressStep } from "./quellen-mock-data"
import type {
  EvidenceChip,
  Requirement,
  RequirementGroup,
} from "./anforderungen-mock-data"
import type { MachineStatus } from "./types"

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

/** Backend node name -> index into RUN_STEP_TEMPLATE. */
const NODE_TO_STEP_INDEX: Record<string, number> = {
  intake_and_classification: 0,
  normalization: 0,
  external_competence_research: 0,
  requirement_extraction: 1,
  evidence_anchor: 2,
  budget_feasibility: 2,
  fit_gap: 2,
  portal_field_router: 2,
  introduction_public_summary_agent: 2,
  organisations_governance_eligibility_agent: 2,
  value_creation_market_logic_agent: 2,
  solution_innovation_argumentation_agent: 2,
  project_setup_workplan_agent: 2,
  summary_submission_readiness_agent: 2,
  pre_review_gate_evaluation: 3,
  human_review_gate: 3,
}

/**
 * Derive the four banner steps from the backend's current node name.
 * Unknown nodes map to the last step so the banner never goes backwards.
 */
export function stepsFromBackendNode(
  currentNode: string | null
): AnalysisProgressStep[] {
  const runningIndex =
    currentNode === null
      ? RUN_STEP_TEMPLATE.length // finished -> everything done
      : (NODE_TO_STEP_INDEX[currentNode] ?? RUN_STEP_TEMPLATE.length - 1)

  return RUN_STEP_TEMPLATE.map((step, i) => ({
    id: step.id,
    label: step.label,
    state:
      i < runningIndex ? "done" : i === runningIndex ? "running" : "pending",
  }))
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
