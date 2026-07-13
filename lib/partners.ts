// Partner client (live v1.1 slice, same-origin BFF). Mirrors the openapi
// Partner / PartnerCreate shapes and the projects-client conventions
// (CSRF + Idempotency-Key on mutations).

import { getCsrfToken } from "./session"

export type PartnerType = "research_partner" | "implementation_partner" | "other"
export type ResearchEligibility =
  | "eligible"
  | "not_eligible"
  | "needs_verification"
export type IndependenceStatus = "confirmed" | "exception" | "needs_input"

export interface PartnerInput {
  name: string
  partner_type: PartnerType
  project_role?: string | null
  country?: string | null
  location?: string | null
  contribution?: string | null
  uid?: string | null
  industry?: string | null
  fte?: number | null
  startup_status?: boolean | null
  swiss_value_creation?: boolean | null
  research_partner_eligibility_status?: ResearchEligibility | null
  personnel_independence_status?: IndependenceStatus | null
  financial_independence_status?: IndependenceStatus | null
  /** Kurze Begründung; Pflicht bei explizit unklar/nicht bestätigt
   *  (Backend-Konsistenzregel «partner_comment_required»). */
  review_comment?: string | null
}

export interface PartnerDto extends PartnerInput {
  partner_id: string
  project_id: string
}

export class PartnerError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "PartnerError"
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

const MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt.",
  404: "Projekt oder Partner wurde nicht gefunden.",
  422: "Bitte prüfen Sie die Partnerangaben.",
}

async function fail(res: Response): Promise<PartnerError> {
  // Backend-Problem-Details sind deutsche, nutzerlesbare Sätze (z. B. die
  // Kommentar-Konsistenzregel) — sie gewinnen vor der Status-Sammelmeldung.
  let detail: string | null = null
  try {
    const body = await res.json()
    if (typeof body?.detail === "string" && body.detail) detail = body.detail
  } catch {
    // non-JSON body
  }
  return new PartnerError(
    res.status,
    detail ?? MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten."
  )
}

export async function listPartners(projectId: string): Promise<PartnerDto[]> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/partners`
  )
  if (!res.ok) throw await fail(res)
  return (await res.json()) as PartnerDto[]
}

export async function createPartner(
  projectId: string,
  input: PartnerInput
): Promise<PartnerDto> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/partners`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify(input),
    }
  )
  if (!res.ok) throw await fail(res)
  return (await res.json()) as PartnerDto
}

export async function updatePartner(
  partnerId: string,
  input: PartnerInput
): Promise<PartnerDto> {
  const res = await fetch(`/api/partners/${encodeURIComponent(partnerId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw await fail(res)
  return (await res.json()) as PartnerDto
}

export async function deletePartner(partnerId: string): Promise<void> {
  const res = await fetch(`/api/partners/${encodeURIComponent(partnerId)}`, {
    method: "DELETE",
    headers: { ...csrfHeaders() },
  })
  if (!res.ok && res.status !== 204) throw await fail(res)
}
