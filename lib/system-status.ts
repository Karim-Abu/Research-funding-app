import { getCsrfToken } from "./session"

export type SystemServiceState = "available" | "attention" | "unavailable"

export interface SystemServiceStatusDto {
  id: "ai" | "web"
  label: string
  state: SystemServiceState
  message: string
  next_step: string
  checked_at?: string | null
}

export interface SystemStatusDto {
  services: SystemServiceStatusDto[]
  can_run_connection_check: boolean
}

async function readError(response: Response): Promise<Error> {
  try {
    const body = await response.json()
    return new Error(body?.detail ?? body?.error?.message ?? "Systemstatus konnte nicht geladen werden.")
  } catch {
    return new Error("Systemstatus konnte nicht geladen werden.")
  }
}

export async function getSystemStatus(): Promise<SystemStatusDto> {
  const response = await fetch("/api/system-status", { cache: "no-store" })
  if (!response.ok) throw await readError(response)
  return response.json() as Promise<SystemStatusDto>
}

export async function runConnectionCheck(): Promise<SystemStatusDto> {
  const csrf = getCsrfToken()
  const response = await fetch("/api/system-status/connection-check", {
    method: "POST",
    headers: csrf ? { "X-CSRF-Token": csrf } : {},
  })
  if (!response.ok) throw await readError(response)
  return response.json() as Promise<SystemStatusDto>
}
