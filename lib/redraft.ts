// A2 draft-suggestion client (Milestone 9D; extended to Value Creation in 9E).
// createRedraft (202 async) → poll the operation → the suggestion in result.
// Advisory only: accepting is a separate updateField call with source_operation_id.
// Scoped to the A2-enabled fields below; no provider/model details ever surface.

import { getCsrfToken } from "./session"
import { pollOperation, type AsyncOperationDto } from "./operations"

export const SOLUTION_INNOVATION_FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"
export const VALUE_CREATION_FIELD_ID = "VC.BUSINESS_TARGETS_MODEL.EDITOR"

// The explicit set of fields that may request an A2 suggestion. Mirrors the
// backend registry-backed allow-list; the backend stays authoritative.
export const A2_FIELD_IDS: ReadonlySet<string> = new Set([
  SOLUTION_INNOVATION_FIELD_ID,
  VALUE_CREATION_FIELD_ID,
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

export interface A2Suggestion {
  suggestion_id: string
  operation_id: string
  field_id: string
  base_version_id: string
  suggested_text: string
  rationale?: string | null
  evidence: A2EvidenceItem[]
  open_issue_ids: string[]
  placeholders: A2Placeholder[]
  character_count: number
  character_limit: number
  warnings: string[]
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
    text: "Es ist kein freigegebener KI-Provider konfiguriert.",
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
    text: "Für dieses Feld ist noch kein KI-Vorschlag verfügbar.",
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
    "Der KI-Vorschlag konnte nicht erstellt werden."
  return new RedraftError(res.status, code, message, reasonCode)
}

/** Request a suggestion and resolve once the async operation produces it. */
export async function createRedraft(
  runId: string,
  fieldId: string,
  baseVersionId: string,
  guidance?: string
): Promise<A2Suggestion> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/redrafts`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify(
        guidance ? { base_version_id: baseVersionId, guidance } : { base_version_id: baseVersionId }
      ),
    }
  )
  // 503 (unavailable) / 409 (stale base) are surfaced synchronously and safely.
  if (!res.ok) throw await toError(res)
  const accepted = (await res.json()) as { operation_id: string }

  return new Promise<A2Suggestion>((resolve, reject) => {
    pollOperation(accepted.operation_id, {
      onTerminal: (op: AsyncOperationDto) => {
        if (op.status === "succeeded" && op.result) {
          resolve(op.result as unknown as A2Suggestion)
        } else {
          const code = op.error?.code ?? "redraft_failed"
          const reasonCode = op.error?.reason_code ?? null
          reject(
            new RedraftError(
              500,
              code,
              MESSAGES[code] ??
                reasonMessage(reasonCode) ??
                "Der KI-Vorschlag konnte nicht erstellt werden.",
              reasonCode
            )
          )
        }
      },
    })
  })
}
