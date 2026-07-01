// Search Query Firewall client (Milestone 9J, same-origin BFF). Screens a query for a
// confidential (D1/D2) project before web research: returns a sanitized public-safe
// query + a decision, and (when review is required) an approval to confirm. No
// provider/model terminology and no raw query is ever surfaced back here.

import { getCsrfToken } from "./session"

export type FirewallDecision = "allow" | "require_human_approval" | "block"
export type RiskLabel = "low" | "medium" | "high"

export interface RedactionItem {
  category: string
  label: string
  count: number
}

export interface FirewallPreview {
  data_class: string
  decision: FirewallDecision
  risk_label: RiskLabel
  sanitized_query: string
  redaction_summary: RedactionItem[]
  reasons: string[]
  approval_id: string | null
}

export interface ApprovalStatus {
  approval_id: string
  status: "pending" | "approved" | "rejected" | "expired" | "used"
  decision: FirewallDecision
  risk_label: RiskLabel
  sanitized_query: string
  redaction_summary: RedactionItem[]
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist durch die Datenrichtlinie blockiert.",
  404: "Die Freigabe wurde nicht gefunden.",
  409: "Die Freigabe ist nicht mehr gültig. Bitte prüfen Sie die Anfrage erneut.",
  503: "Die öffentliche Recherche ist derzeit nicht verfügbar.",
}

export class FirewallError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "FirewallError"
    this.status = status
    this.code = code
  }
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

async function toError(res: Response): Promise<FirewallError> {
  let code = "error"
  try {
    const body = await res.json()
    if (body?.code) code = body.code
  } catch {
    // non-JSON body
  }
  return new FirewallError(
    res.status,
    code,
    STATUS_MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten."
  )
}

export async function previewSearchQuery(
  projectId: string,
  rawQuery: string
): Promise<FirewallPreview> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/search-query-firewall/preview`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ raw_query: rawQuery }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as FirewallPreview
}

async function decide(
  approvalId: string,
  verb: "approve" | "reject"
): Promise<ApprovalStatus> {
  const res = await fetch(
    `/api/search-query-approvals/${encodeURIComponent(approvalId)}/${verb}`,
    { method: "POST", headers: { ...csrfHeaders() } }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ApprovalStatus
}

export function approveSearchQuery(approvalId: string): Promise<ApprovalStatus> {
  return decide(approvalId, "approve")
}

export function rejectSearchQuery(approvalId: string): Promise<ApprovalStatus> {
  return decide(approvalId, "reject")
}
