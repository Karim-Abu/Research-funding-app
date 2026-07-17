// A2 draft-suggestion client (Milestone 9D; extended to Value Creation in 9E).
// createRedraft (202 async) → poll the operation → the suggestion in result.
// Advisory only: accepting is a separate updateField call with source_operation_id.
// Scoped to the A2-enabled fields below. DraftProposal ist der neutrale View;
// Provider-/Modellmetadaten gibt es nur im kompatiblen AIProposal nach einem
// echten Modellaufruf und nur unter Technische Details.

import { getCsrfToken } from "./session"
import { pollOperation, type AsyncOperationDto } from "./operations"
import type { GenerationKind } from "./generation-kind"

export const SOLUTION_INNOVATION_FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"
export const VALUE_CREATION_FIELD_ID = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
export const ABSTRACT_FIELD_ID = "INTRO.APP.ABSTRACT"
export const EXECUTIVE_SUMMARY_FIELD_ID = "INTRO.APP.EXECUTIVE_SUMMARY"
export const FINANCIAL_INDEPENDENCE_FIELD_ID = "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS"
export const MANAGEMENT_HOURS_EXPLANATION_FIELD_ID = "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION"

// The explicit set of fields that may request an A2 suggestion. Mirrors the
// backend registry-backed allow-list; the backend stays authoritative.
export const A2_FIELD_IDS: ReadonlySet<string> = new Set([
  SOLUTION_INNOVATION_FIELD_ID,
  VALUE_CREATION_FIELD_ID,
  ABSTRACT_FIELD_ID,
  EXECUTIVE_SUMMARY_FIELD_ID,
  FINANCIAL_INDEPENDENCE_FIELD_ID,
  MANAGEMENT_HOURS_EXPLANATION_FIELD_ID,
])

export function isA2Field(fieldId: string | undefined | null): boolean {
  return fieldId != null && A2_FIELD_IDS.has(fieldId)
}

export interface A2EvidenceItem {
  anchor_id: string
  quote: string
  source_name: string
  verification_status: string
  page?: number | null
  section?: string | null
}

export interface A2Placeholder {
  label: string
  reason?: string | null
}

export interface AIMissingInput {
  label: string
  reason?: string | null
}

// Typisierte Proposal-Views (Spiegel von backend/app/agents/proposal.py).
// human_review_required ist im Typ auf `true` fixiert: keine Auto-Übernahme.
export interface DraftProposal {
  suggestion_text: string
  used_anchor_ids: string[]
  used_research_source_ids: string[]
  missing_inputs: AIMissingInput[]
  profile_id: string
  prompt_version: string | null
  context_hash: string | null
  generation_kind?: GenerationKind | null
  model_ref?: string | null
  created_at: string
  data_mode: string
  provider?: string | null
  model?: string | null
  usage_record_id?: string | null
  safety_notes?: string[]
  human_review_required: true
}

export interface AIProposal extends DraftProposal {
  generation_kind: "model_generated"
  model_ref: string
  provider: string
  model: string
}

export interface SectionResult {
  field_id: string
  target_section: string
  suggested_text: string
  rationale: string
  preserved_facts: string[]
  removed_or_reframed_claims: string[]
  new_claims: string[]
  missing_inputs: AIMissingInput[]
  evidence_anchor_ids: string[]
  research_source_ids: string[]
  open_issue_ids: string[]
}

export interface A2Suggestion {
  suggestion_id: string
  operation_id: string
  field_id: string
  target_section?: string | null
  generation_kind?: GenerationKind | null
  execution_mode?: "live" | "fake_demo"
  base_version_id: string
  suggested_text: string
  rationale?: string | null
  evidence: A2EvidenceItem[]
  research_sources?: Array<{
    source_id: string
    title: string
    url: string
    research_module?: string | null
    support_status: "supports" | "partially_supports"
    content_review_status: "reviewed"
  }>
  open_issue_ids: string[]
  placeholders: A2Placeholder[]
  character_count: number
  character_limit: number
  warnings: string[]
  section_result?: SectionResult | null
  proposal?: DraftProposal
  ai_proposal?: AIProposal
}

export function parseDraftProposal(value: unknown): DraftProposal | null {
  if (typeof value !== "object" || value === null) return null
  const v = value as Record<string, unknown>
  if (typeof v.suggestion_text !== "string" || typeof v.profile_id !== "string") return null
  if (v.human_review_required !== true) return null
  if (!Array.isArray(v.used_anchor_ids) || !Array.isArray(v.missing_inputs)) return null
  if (v.used_research_source_ids != null && !Array.isArray(v.used_research_source_ids)) return null
  if (
    v.generation_kind != null &&
    !["rule_template", "fake_demo", "model_generated"].includes(String(v.generation_kind))
  ) return null
  return v as unknown as DraftProposal
}

/** Fail-closed AIProposal-Parser: ungültige/fremde Shapes ⇒ null. */
export function parseAIProposal(value: unknown): AIProposal | null {
  if (typeof value !== "object" || value === null) return null
  const v = value as Record<string, unknown>
  const requiredStrings = [
    "suggestion_text", "profile_id", "model_ref", "created_at",
    "data_mode", "provider", "model",
  ] as const
  if (requiredStrings.some((k) => typeof v[k] !== "string")) return null
  if (v.generation_kind !== "model_generated") return null
  if (v.human_review_required !== true) return null
  if (!Array.isArray(v.used_anchor_ids) || !Array.isArray(v.missing_inputs)) return null
  return v as unknown as AIProposal
}

export class RedraftError extends Error {
  readonly status: number
  readonly code: string
  /** R4.2: maschinenlesbarer Verfügbarkeits-Blockgrund (Katalog-Code) oder null. */
  readonly reasonCode: string | null
  constructor(status: number, code: string, message: string, reasonCode: string | null = null) {
    super(message)
    this.name = "RedraftError"
    this.status = status
    this.code = code
    this.reasonCode = reasonCode
  }
}

// R4.2 — Owner-approved Microcopy je Reason-Code (docs/repair/message-catalog.md
// §R4.2). Text und CTA-Label sind freigegeben; Änderungen laufen über den Katalog.
export interface AiReasonInfo {
  text: string
  ctaLabel: string
}

export const AI_REASON_INFO: Record<string, AiReasonInfo> = {
  nda_locked: {
    text: "Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert.",
    ctaLabel: "Verarbeitungsmodus prüfen",
  },
  mode_deterministic_only: {
    text: "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt.",
    ctaLabel: "Verarbeitungsmodus ändern",
  },
  provider_unavailable: {
    text: "Für diese Datenklasse ist aktuell kein freigegebener KI-Provider konfiguriert. Die App führt nur regelbasierte Prüfungen aus.",
    ctaLabel: "Provider-Konfiguration prüfen",
  },
  live_provider_key_missing: {
    text: "Live-KI ist nicht verfügbar. Hinterlegen Sie den API-Schlüssel der konfigurierten Route und führen Sie den Preflight erneut aus.",
    ctaLabel: "Live-Systemstatus prüfen",
  },
  live_fake_conflict: {
    text: "Live-KI ist wegen einer widersprüchlichen Konfiguration nicht verfügbar. Setzen Sie AGENT_FAKE_PROVIDER=false und führen Sie den Preflight erneut aus.",
    ctaLabel: "Konfiguration korrigieren",
  },
  live_eval_mode_disabled: {
    text: "Live-KI ist deaktiviert. Setzen Sie AI_EVAL_MODE=real und führen Sie den synthetischen Preflight erneut aus.",
    ctaLabel: "Live-Modus aktivieren",
  },
  live_model_id_missing: {
    text: "Live-KI ist nicht verfügbar. Hinterlegen Sie die konkrete AGENT_MODEL_*_ID der Route und führen Sie den Preflight erneut aus.",
    ctaLabel: "Modellroute konfigurieren",
  },
  live_price_metadata_missing: {
    text: "Live-KI ist nicht verfügbar. Ergänzen Sie geprüfte Preis-Metadaten für die konkrete Modell-ID.",
    ctaLabel: "Preis-Metadaten prüfen",
  },
  live_preflight_required: {
    text: "Live-KI ist noch nicht freigegeben. Starten Sie im Live-Systemstatus den synthetischen Preflight.",
    ctaLabel: "Live-Systemstatus prüfen",
  },
  live_preflight_expired: {
    text: "Der Live-Preflight ist abgelaufen. Führen Sie ihn im Live-Systemstatus erneut aus.",
    ctaLabel: "Preflight erneut starten",
  },
  live_preflight_failed: {
    text: "Der Live-Preflight ist fehlgeschlagen. Prüfen Sie den konkreten Routenfehler im Live-Systemstatus und wiederholen Sie den Test.",
    ctaLabel: "Routenfehler prüfen",
  },
  live_preflight_stale_model: {
    text: "Die konfigurierte Modell-ID wurde seit dem Preflight geändert. Führen Sie den synthetischen Preflight erneut aus.",
    ctaLabel: "Preflight erneut starten",
  },
  live_actual_model_missing: {
    text: "Der Provider hat im Preflight keine tatsächliche Modell-ID bestätigt. Prüfen Sie die Route im Live-Systemstatus.",
    ctaLabel: "Route prüfen",
  },
  no_approved_model_provider: {
    text: "Es ist kein freigegebener KI-Provider aktiv. Die App führt nur regelbasierte Prüfungen aus.",
    ctaLabel: "Provider-Konfiguration prüfen",
  },
  run_mode_mismatch: {
    text: "Der aktuelle Analysemodus passt nicht zum Feldvorschlag.",
    ctaLabel: "Analysemodus prüfen",
  },
  missing_sources: {
    text: "Für einen belastbaren Vorschlag fehlen passende Quellen.",
    ctaLabel: "Quelle hinzufügen",
  },
  field_not_supported: {
    text: "Für dieses Feld ist noch kein Abschnittsvorschlag verfügbar.",
    ctaLabel: "Strukturvorlage nutzen",
  },
}

/** Fail-closed-Anzeige, wenn ein 503 ohne bekannten Code eintrifft. */
export const FALLBACK_AI_REASON = "provider_unavailable"

const MESSAGES: Record<string, string> = {
  stale_base_version: "Dieser Abschnitt wurde zwischenzeitlich geändert.",
}

function reasonMessage(reasonCode: string | null): string | null {
  return reasonCode ? (AI_REASON_INFO[reasonCode]?.text ?? null) : null
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

async function toError(res: Response): Promise<RedraftError> {
  let code = "error"
  let reasonCode: string | null = null
  try {
    const body = await res.json()
    if (body?.code) code = body.code
    if (typeof body?.reason_code === "string") reasonCode = body.reason_code
  } catch {
    /* non-JSON */
  }
  const message =
    MESSAGES[code] ??
    reasonMessage(reasonCode) ??
    "Der Vorschlag konnte nicht erstellt werden."
  return new RedraftError(res.status, code, message, reasonCode)
}

/** Offene (proposed) Suggestion zur aktuellen Basisversion — z. B. aus dem
 *  normalen Analyse-Lauf erzeugt. Read-only; null, wenn keine vorliegt. */
export async function getRunFieldSuggestion(
  runId: string,
  fieldId: string,
  targetSection?: string
): Promise<A2Suggestion | null> {
  const query = targetSection
    ? `?target_section=${encodeURIComponent(targetSection)}`
    : ""
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/suggestion${query}`
  )
  if (!res.ok) throw await toError(res)
  const body = (await res.json()) as { suggestion: Record<string, unknown> | null }
  if (!body.suggestion) return null
  const base = body.suggestion as unknown as A2Suggestion
  const proposal = parseDraftProposal(body.suggestion.proposal)
  const aiProposal = parseAIProposal(body.suggestion.ai_proposal)
  return {
    ...base,
    proposal: proposal ?? undefined,
    ai_proposal: aiProposal ?? undefined,
  }
}

/** Request a suggestion and resolve once the async operation produces it. */
export async function createRedraft(
  runId: string,
  fieldId: string,
  baseVersionId: string,
  guidance?: string,
  targetSection?: string
): Promise<A2Suggestion> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/redrafts`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({
        base_version_id: baseVersionId,
        ...(guidance ? { guidance } : {}),
        ...(targetSection ? { target_section: targetSection } : {}),
      }),
    }
  )
  // 503 (unavailable) / 409 (stale base) are surfaced synchronously and safely.
  if (!res.ok) throw await toError(res)
  const accepted = (await res.json()) as { operation_id: string }

  return new Promise<A2Suggestion>((resolve, reject) => {
    pollOperation(accepted.operation_id, {
      onTerminal: (op: AsyncOperationDto) => {
        if (op.status === "succeeded" && op.result) {
          const base = op.result as unknown as A2Suggestion
          const proposal = parseDraftProposal(
            (op.result as Record<string, unknown>).proposal
          )
          const aiProposal = parseAIProposal(
            (op.result as Record<string, unknown>).ai_proposal
          )
          resolve({
            ...base,
            proposal: proposal ?? undefined,
            ai_proposal: aiProposal ?? undefined,
          })
        } else {
          const code = op.error?.code ?? "redraft_failed"
          const reasonCode = op.error?.reason_code ?? null
          reject(
            new RedraftError(
              500,
              code,
              MESSAGES[code] ??
                reasonMessage(reasonCode) ??
                "Der Vorschlag konnte nicht erstellt werden.",
              reasonCode
            )
          )
        }
      },
    })
  })
}
