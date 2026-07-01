// MAS reliability (M9K) client (same-origin BFF). Read-only Quality Summary for the Review
// Center: run a deterministic reliability pass and read the RunQualitySummary + per-claim
// lineage/sufficiency + reliability findings. No provider/model terminology, no confidence %.

import { getCsrfToken } from "./session"
import { pollOperation } from "./operations"

export interface RunQualitySummaryDto {
  summary_id: string
  run_id: string
  status: string
  stale: boolean
  quality_flag: string
  claim_count: number
  supported_claims: number
  weakly_supported_claims: number
  unsupported_claims: number
  conflicting_claims: number
  evidence_coverage: number
  evidence_correctness_sample_size: number
  evidence_correctness_sample_pass_rate: number
  review_required_count: number
  blocker_count: number
  warning_count: number
  fields_ready: number
  fields_needs_review: number
  false_consensus_risk_count: number
  semantic_drift_count: number
  raw_logging_detected: boolean
  tool_leakage_detected: boolean
  summary_version: string
  generated_at: string
}

export interface ReliabilityClaimDto {
  claim_id: string
  field_id: string
  claim_type: string
  strength: string
  requires_evidence: boolean
  claim_text: string
  lineage_status: string
  sufficiency_status: string
  reason?: string | null
}

export interface ReliabilityFindingDto {
  finding_id: string
  field_id?: string | null
  severity: string
  description: string
  status: string
  finding_code: string
  target_type?: string | null
  target_id?: string | null
}

export interface ReliabilityViewDto {
  run_id: string
  available: boolean
  reliability_stale: boolean
  summary: RunQualitySummaryDto | null
  claims: ReliabilityClaimDto[]
  findings: ReliabilityFindingDto[]
}

export class ReliabilityError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "ReliabilityError"
    this.status = status
  }
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

export async function getReliability(runId: string): Promise<ReliabilityViewDto> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/reliability`)
  if (!res.ok) throw new ReliabilityError(res.status, "Zuverlässigkeitsdaten nicht verfügbar.")
  return (await res.json()) as ReliabilityViewDto
}

// Run the pass and resolve once the async operation reaches a terminal state.
export async function runReliabilityPass(runId: string): Promise<void> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/reliability`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey(), ...csrfHeaders() },
  })
  if (!res.ok) throw new ReliabilityError(res.status, "Zuverlässigkeitsprüfung fehlgeschlagen.")
  const accepted = (await res.json()) as { operation_id: string }
  await new Promise<void>((resolve, reject) => {
    pollOperation(accepted.operation_id, {
      onTerminal: (op) =>
        op.status === "succeeded"
          ? resolve()
          : reject(new ReliabilityError(500, "Zuverlässigkeitsprüfung fehlgeschlagen.")),
    })
  })
}
