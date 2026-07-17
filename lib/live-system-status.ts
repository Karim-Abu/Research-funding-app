import { isLive } from "./app-mode"
import { getCsrfToken } from "./session"

export interface LiveRouteStatusDto {
  role_id: string
  route_key: string
  route_alias: string
  provider: string
  requested_model_id?: string | null
  actual_model_id?: string | null
  configuration_status: "configured" | "not_configured" | "evaluation_disabled"
  preflight_status: "pass" | "fail" | "not_run"
  checked_at?: string | null
  expires_at?: string | null
  latency_ms?: number | null
  error_class?: string | null
  capabilities: Record<string, unknown>
  cost_status: string
  readiness_reason?: string | null
  checks: Array<Record<string, unknown>>
}

export interface LiveSystemStatusDto {
  overall_status: "available" | "degraded" | "unavailable"
  registry_version: string
  generation_mode: "unavailable" | "fake_demo" | "real_eval" | "live_unavailable"
  generation_unavailable_reason?: string | null
  routes: LiveRouteStatusDto[]
  firecrawl: {
    mode: "disabled" | "fake" | "live" | "not_configured"
    available: boolean
    preflight_status: "pass" | "fail" | "not_run"
    checked_at?: string | null
    expires_at?: string | null
    latency_ms?: number | null
    error_class?: string | null
    checks: Array<Record<string, unknown>>
  }
}

export class LiveSystemStatusError extends Error {}

async function responseError(response: Response): Promise<LiveSystemStatusError> {
  try {
    const body = await response.json()
    return new LiveSystemStatusError(
      body?.detail ?? body?.error?.message ?? "Live-Systemstatus konnte nicht geladen werden."
    )
  } catch {
    return new LiveSystemStatusError("Live-Systemstatus konnte nicht geladen werden.")
  }
}

export async function getLiveSystemStatus(): Promise<LiveSystemStatusDto> {
  if (!isLive("live-system-status")) {
    throw new LiveSystemStatusError("Nur im Live-Backend verfügbar.")
  }
  const response = await fetch("/api/admin/live-system-status", { cache: "no-store" })
  if (!response.ok) throw await responseError(response)
  return (await response.json()) as LiveSystemStatusDto
}

export async function runLiveSystemPreflight(): Promise<LiveSystemStatusDto> {
  if (!isLive("live-system-status")) {
    throw new LiveSystemStatusError("Nur im Live-Backend verfügbar.")
  }
  const csrf = getCsrfToken()
  const response = await fetch("/api/admin/live-system-status", {
    method: "POST",
    headers: csrf ? { "X-CSRF-Token": csrf } : {},
  })
  if (!response.ok) throw await responseError(response)
  const body = (await response.json()) as { status: LiveSystemStatusDto }
  return body.status
}
