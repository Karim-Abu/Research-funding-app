// Single source of truth for the backend mode. The value is server-controlled
// (read from APP_BACKEND_MODE in app/layout.tsx and injected via AppProviders);
// it is never a NEXT_PUBLIC value and never hardcoded as a second flag.
//
// Milestone 1: only the session/me/capabilities/projects resources are live in
// "live" mode. Every other resource stays on its existing mock regardless of
// mode (its fetch branch is simply never reached) — no 501 screens.

export type BackendMode = "mock" | "live"

// Resources wired to the real backend (cumulative across milestones).
const LIVE_RESOURCES: ReadonlySet<string> = new Set([
  "session",
  "me",
  "capabilities",
  "projects",
  "sources",
  "runs",
  "operations",
  "partners",
  "requirements",
  "evidence",
  "fields",
])

let currentMode: BackendMode = "mock"

export function setBackendMode(mode: BackendMode): void {
  currentMode = mode
}

export function getBackendMode(): BackendMode {
  return currentMode
}

/** True when `resource` should talk to the real backend (mode live + in scope). */
export function isLive(resource: string): boolean {
  return currentMode === "live" && LIVE_RESOURCES.has(resource)
}

/** Inverse of {@link isLive} — legacy resources are always mock in Milestone 1. */
export function isMock(resource: string): boolean {
  return !isLive(resource)
}
