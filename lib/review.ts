// Review client (live Milestone 7 slice). Deterministic review package, typed
// human decisions / section comments, role-gated approvals and targeted recheck.
// Mirrors the openapi ReviewPackage / HumanDecisionCreate / ApprovalCreate /
// RecheckCreate shapes. No AI/semantic logic.

import { getCsrfToken } from "./session"
import { pollOperation } from "./operations"
import type { PortalFieldDraftDto } from "./fields"
import type { OpenIssueDto, RequirementAssessmentDto } from "./requirements"

export type FindingSeverity = "blocker" | "warning" | "info"
export type FindingStatus = "open" | "resolved" | "overridden" | "dismissed"
export type ApprovalStatus =
  | "open"
  | "blocked"
  | "approved"
  | "changes_required"
  | "stale"
export type ApprovalScope = "run" | "field"

export interface ReviewFindingDto {
  finding_id: string
  profile_id: string
  field_id?: string | null
  requirement_id?: string | null
  severity: FindingSeverity
  description: string
  suggested_improvement?: string | null
  status: FindingStatus
  advisory: boolean
}

export interface ReviewPackageDto {
  run_id: string
  requirements: RequirementAssessmentDto[]
  fields: PortalFieldDraftDto[]
  findings: ReviewFindingDto[]
  approval_status: ApprovalStatus
  blocker_count: number
  warning_count: number
  open_issues: OpenIssueDto[]
  review_package_version: string
  current_approval_scope_hash: string
  recheck_required: boolean
  stale_finding_count: number
}

export type DecisionTargetType =
  | "requirement_assessment"
  | "evidence_anchor"
  | "review_finding"
  | "portal_field_draft"

export interface HumanDecisionCreate {
  target_type: DecisionTargetType
  target_id: string
  action: string
  comment?: string | null
}

export interface HumanDecisionDto extends HumanDecisionCreate {
  decision_id: string
  user_id: string
  run_id: string
  created_at: string
}

export interface ReviewApprovalDto {
  approval_id: string
  run_id: string
  scope: ApprovalScope
  status: ApprovalStatus
  approval_scope_hash: string
  approved_by?: string | null
  created_at: string
}

export class ReviewError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "ReviewError"
    this.status = status
    this.code = code
  }
}

const MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt.",
  404: "Das Review wurde nicht gefunden.",
  409: "Das Review hat sich zwischenzeitlich geändert. Bitte neu laden.",
  422: "Die Eingabe ist unvollständig.",
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

async function toError(res: Response): Promise<ReviewError> {
  let code = "error"
  let detail = ""
  try {
    const body = await res.json()
    if (body?.code) code = body.code
    if (typeof body?.detail === "string") detail = body.detail
  } catch {
    /* non-JSON */
  }
  return new ReviewError(
    res.status,
    code,
    detail || MESSAGES[res.status] || "Es ist ein Fehler aufgetreten."
  )
}

export async function getReview(runId: string): Promise<ReviewPackageDto> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/review`)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ReviewPackageDto
}

export async function createHumanDecision(
  runId: string,
  decision: HumanDecisionCreate
): Promise<HumanDecisionDto> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/human-decisions`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify(decision),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as HumanDecisionDto
}

export async function createApproval(
  runId: string,
  pkg: Pick<
    ReviewPackageDto,
    "current_approval_scope_hash" | "review_package_version"
  >,
  scope: ApprovalScope,
  scopeId: string
): Promise<ReviewApprovalDto> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/approvals`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey(),
      ...csrfHeaders(),
    },
    body: JSON.stringify({
      scope,
      scope_id: scopeId,
      expected_approval_scope_hash: pkg.current_approval_scope_hash,
      expected_review_package_version: pkg.review_package_version,
      confirm_not_submission_approval: true,
    }),
  })
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ReviewApprovalDto
}

/** Start a targeted recheck and resolve once the async operation is terminal. */
export async function startRecheck(
  runId: string,
  expectedReviewPackageVersion: string
): Promise<void> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/rechecks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey(),
      ...csrfHeaders(),
    },
    body: JSON.stringify({
      expected_review_package_version: expectedReviewPackageVersion,
      changed_target_refs: [],
    }),
  })
  if (!res.ok) throw await toError(res)
  const accepted = (await res.json()) as { operation_id: string }
  await new Promise<void>((resolve, reject) => {
    pollOperation(accepted.operation_id, {
      onTerminal: (op) => {
        if (op.status === "succeeded") resolve()
        else reject(new ReviewError(500, "recheck_failed", "Recheck fehlgeschlagen."))
      },
    })
  })
}
